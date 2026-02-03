"""Tuned Airiti Library crawler (web scraping)."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import urllib.parse
from typing import Any, Iterable, Optional

from bs4 import BeautifulSoup
import httpx

from refminer.crawler.base import BaseCrawler
from refminer.crawler.models import SearchQuery, SearchResult

logger = logging.getLogger(__name__)


class AiritiCrawler(BaseCrawler):
    """Airiti Library crawler using web scraping."""

    MAX_PAGES = 10

    @property
    def name(self) -> str:
        return "airiti"

    @property
    def base_url(self) -> str:
        return "https://www.airitilibrary.com"

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        """Search Airiti Library for papers."""
        results: list[SearchResult] = []
        seen: set[str] = set()
        page_count = 0

        try:
            next_url = self._build_search_url(query)
            logger.debug(f"[{self.name}] search url={next_url}")
            while next_url and page_count < self.MAX_PAGES:
                page_count += 1
                response = await self._fetch(next_url)
                logger.debug(
                    f"[{self.name}] fetched page={page_count} status={response.status_code} url={next_url}"
                )
                logger.debug(
                    f"[{self.name}] response size={len(response.text)} content_type={response.headers.get('content-type')!r}"
                )
                soup = BeautifulSoup(response.text, "html.parser")
                page_results = self._parse_results(
                    soup, include_abstract=query.include_abstract
                )
                logger.debug(
                    f"[{self.name}] parsed page={page_count} results={len(page_results)}"
                )
                for result in page_results:
                    result_key = result.get_hash()
                    if result_key in seen:
                        continue
                    seen.add(result_key)
                    results.append(result)
                    if query.max_results > 0 and len(results) >= query.max_results:
                        break
                if query.max_results > 0 and len(results) >= query.max_results:
                    break
                next_url = self._extract_next_url(soup, current_url=next_url)

            if results:
                await self._enrich_results(results, query)

            logger.info(f"[{self.name}] Found {len(results)} results")
        except Exception as e:
            logger.error(f"[{self.name}] Search failed: {e}", exc_info=True)

        return results

    def _build_search_url(self, query: SearchQuery) -> str:
        """Build Airiti Library search URL."""
        from datetime import datetime

        query_json = {
            "查詢時間": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
            "查詢歷史類型代碼": "ADLang",
            "是否關鍵字統計": True,
            "DSF": {
                "SearchFileds": [
                    {"FieldName": 49, "SearchKeyWord": query.query, "FieldQuery": True}
                ],
                "IsFuzzySearch": False,
            },
            "BSF": {
                "SearchFiledList": [
                    {
                        "FieldName": 0,
                        "SearchKeyWord": query.query,
                        "FieldQuery": True,
                        "FieldLogic": 0,
                    }
                ]
            },
        }

        encoded_json = urllib.parse.quote(json.dumps(query_json, ensure_ascii=False))
        return f"{self.base_url}/Article/Query?queryString={encoded_json}"

    def _parse_results(
        self, soup: BeautifulSoup, include_abstract: bool
    ) -> list[SearchResult]:
        """Parse search results from HTML."""
        results: list[SearchResult] = []
        seen: set[str] = set()

        json_ld_scripts = soup.find_all("script", type="application/ld+json")
        logger.debug(
            f"[{self.name}] json-ld scripts={len(json_ld_scripts)} links={len(soup.find_all('a'))}"
        )

        json_ld_count = 0
        for entry in self._extract_json_ld(soup):
            json_ld_count += 1
            result = self._parse_json_ld_entry(entry, include_abstract=include_abstract)
            if result:
                result_key = result.get_hash()
                if result_key in seen:
                    continue
                seen.add(result_key)
                results.append(result)

        if json_ld_count == 0:
            logger.debug(f"[{self.name}] no json-ld entries found")

        html_results = self._parse_html_results(soup, include_abstract=include_abstract)
        if html_results:
            logger.debug(f"[{self.name}] html fallback results={len(html_results)}")

        for result in html_results:
            result_key = result.get_hash()
            if result_key in seen:
                continue
            seen.add(result_key)
            results.append(result)

        return results

    def _parse_html_results(
        self, soup: BeautifulSoup, include_abstract: bool
    ) -> list[SearchResult]:
        """Fallback parser for result cards without JSON-LD."""
        results: list[SearchResult] = []
        candidates: list[tuple[str, Any]] = []
        groups = soup.find_all("div", class_="searchResultGroup")
        if groups:
            for group in groups:
                result = self._parse_result_group(
                    group, include_abstract=include_abstract
                )
                if result:
                    results.append(result)
            return results

        for link in soup.find_all("a", href=True):
            href = self._coerce_attr_value(link.get("href"))
            if not isinstance(href, str) or not href:
                continue
            lower = href.lower()
            if "/article/detail" in lower or "article/detail" in lower:
                candidates.append((href, link))

        if not candidates:
            sample_hrefs: list[str] = []
            for link in soup.find_all("a", href=True):
                href = self._coerce_attr_value(link.get("href"))
                if isinstance(href, str) and href:
                    sample_hrefs.append(href)
                if len(sample_hrefs) >= 5:
                    break
            logger.debug(
                f"[{self.name}] no html candidates found (sample_hrefs={sample_hrefs})"
            )

        for href, link in candidates:
            container = link.find_parent(["li", "div", "article", "section"]) or link
            title = self._extract_title_from_node(container) or link.get_text(
                " ", strip=True
            )
            if not title or len(title) < 4:
                continue

            authors = self._extract_authors_from_node(container)
            year = self._extract_year_from_text(container.get_text(" ", strip=True))
            abstract = (
                self._extract_abstract_from_node(container)
                if include_abstract
                else None
            )

            url = self._normalize_pdf_url(href)
            pdf_url = self._extract_pdf_from_node(container)

            results.append(
                SearchResult(
                    title=title,
                    authors=authors,
                    year=year,
                    doi=None,
                    abstract=abstract,
                    source=self.name,
                    url=url,
                    pdf_url=pdf_url,
                    journal=None,
                    volume=None,
                    issue=None,
                    pages=None,
                    citation_count=None,
                )
            )

        return results

    def _parse_result_group(
        self, group: Any, include_abstract: bool
    ) -> Optional[SearchResult]:
        doc_id = self._coerce_attr_value(group.get("key"))
        title_node = group.select_one("h3 a") if hasattr(group, "select_one") else None
        title = title_node.get_text(" ", strip=True) if title_node else None
        if title_node and not doc_id:
            onclick = self._coerce_attr_value(title_node.get("onclick"))
            doc_id = self._extract_doc_id_from_onclick(onclick)

        if not title or not doc_id:
            return None

        authors = []
        author_node = (
            group.select_one("span.author") if hasattr(group, "select_one") else None
        )
        if author_node:
            for link in author_node.find_all("a"):
                author_text = link.get_text(" ", strip=True)
                if author_text:
                    authors.append(author_text)
            if not authors:
                authors = self._split_author_string(
                    author_node.get_text(" ", strip=True)
                )

        year = None
        journal = None
        volume = None
        issue = None
        pages = None

        source_node = (
            group.select_one("span.source") if hasattr(group, "select_one") else None
        )
        if source_node:
            journal_node = source_node.select_one("span.sourceTitleName")
            if journal_node:
                journal_text = journal_node.get_text(" ", strip=True)
                journal = journal_text or None
            pub_node = source_node.select_one("span.sourcePub")
            if pub_node:
                pub_text = pub_node.get_text(" ", strip=True)
                volume, issue = self._split_volume_issue(pub_text)
            date_node = source_node.select_one("span.sourcedate")
            if date_node:
                year = self._extract_year_from_text(date_node.get_text(" ", strip=True))
            pages_node = source_node.select_one("span.sourcePageRange")
            if pages_node:
                pages_text = pages_node.get_text(" ", strip=True)
                pages = pages_text or None

        abstract = self._extract_abstract_from_node(group) if include_abstract else None

        url = self._normalize_pdf_url(f"/Article/Detail?DocID={doc_id}")
        pdf_url = self._extract_pdf_from_node(group)

        metadata: dict[str, Any] = {}
        download_info = self._extract_download_info(group)
        if download_info:
            metadata["airiti_download"] = download_info

        return SearchResult(
            title=title,
            authors=authors,
            year=year,
            doi=None,
            abstract=abstract,
            source=self.name,
            url=url,
            pdf_url=pdf_url,
            journal=journal,
            volume=volume,
            issue=issue,
            pages=pages,
            citation_count=None,
            metadata=metadata,
        )

    def _extract_next_url(self, soup: BeautifulSoup, current_url: str) -> Optional[str]:
        link = soup.find("a", attrs={"rel": "next"})
        if link:
            href = self._coerce_attr_value(link.get("href"))
            if isinstance(href, str) and href:
                return urllib.parse.urljoin(self.base_url, href)

        link = soup.find("a", attrs={"aria-label": re.compile(r"next", re.I)})
        if link:
            href = self._coerce_attr_value(link.get("href"))
            if isinstance(href, str) and href:
                return urllib.parse.urljoin(self.base_url, href)

        for candidate in soup.find_all("a", href=True):
            text = candidate.get_text(strip=True).lower()
            if text in {">", "next", "next page", "下一頁", "下頁"}:
                href = self._coerce_attr_value(candidate.get("href"))
                if isinstance(href, str) and href:
                    return urllib.parse.urljoin(self.base_url, href)

        current = urllib.parse.urlparse(current_url)
        query = urllib.parse.parse_qs(current.query)
        page_value = query.get("page") or query.get("p")
        if page_value and page_value[0].isdigit():
            next_page = str(int(page_value[0]) + 1)
            query["page"] = [next_page]
            new_query = urllib.parse.urlencode(query, doseq=True)
            return current._replace(query=new_query).geturl()

        return None

    def _extract_json_ld(self, soup: BeautifulSoup) -> Iterable[dict[str, Any]]:
        """Extract JSON-LD entries from page."""
        scripts = soup.find_all("script", type="application/ld+json")
        for script in scripts:
            content = script.string or script.get_text(strip=True)
            if not content:
                continue
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                continue

            yield from self._normalize_json_ld(data)

    def _normalize_json_ld(self, data: Any) -> Iterable[dict[str, Any]]:
        """Normalize JSON-LD payloads into a list of objects."""
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    yield item
            return

        if isinstance(data, dict):
            graph = data.get("@graph")
            if isinstance(graph, list):
                for item in graph:
                    if isinstance(item, dict):
                        yield item
                return

            item_list = data.get("itemListElement")
            if isinstance(item_list, list):
                for item in item_list:
                    if not isinstance(item, dict):
                        continue
                    payload = item.get("item") or item.get("result") or item
                    if isinstance(payload, dict):
                        yield payload
                return

            yield data

    def _parse_json_ld_entry(
        self, entry: dict[str, Any], include_abstract: bool
    ) -> Optional[SearchResult]:
        """Parse a JSON-LD entry into a SearchResult."""
        entry_type = entry.get("@type")
        types: list[str] = []
        if isinstance(entry_type, list):
            types = [str(item) for item in entry_type]
        elif isinstance(entry_type, str):
            types = [entry_type]
        if types and not any("Article" in value for value in types):
            return None

        title = self._extract_title(entry)
        if not title:
            return None

        authors = self._extract_authors(entry)
        year = self._extract_year(entry)
        doi = self._extract_doi(entry)
        url = self._extract_url(entry)
        pdf_url = self._extract_pdf_url(entry)
        journal = self._extract_journal(entry)

        abstract = None
        if include_abstract:
            abstract = self._extract_abstract(entry)

        return SearchResult(
            title=title,
            authors=authors,
            year=year,
            doi=doi,
            abstract=abstract,
            source=self.name,
            url=url,
            pdf_url=pdf_url,
            journal=journal,
            volume=None,
            issue=None,
            pages=None,
            citation_count=None,
        )

    async def _enrich_results(
        self, results: list[SearchResult], query: SearchQuery
    ) -> None:
        for result in results:
            if not result.url:
                continue
            needs_abstract = query.include_abstract and not result.abstract
            needs_doi = not result.doi
            needs_pdf = not result.pdf_url
            if not (needs_abstract or needs_doi or needs_pdf):
                continue

            try:
                response = await self._fetch(result.url)
            except Exception as exc:
                logger.debug(
                    f"[{self.name}] Detail fetch failed for {result.url}: {exc}"
                )
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            if needs_abstract:
                result.abstract = self._extract_abstract_from_html(soup)
            if needs_doi:
                result.doi = self._extract_doi_from_html(soup)
            if needs_pdf:
                result.pdf_url = self._extract_pdf_from_html(soup)

            if needs_abstract or needs_doi or needs_pdf:
                for entry in self._extract_json_ld(soup):
                    if not (needs_abstract or needs_doi or needs_pdf):
                        break
                    if needs_abstract and not result.abstract:
                        result.abstract = self._extract_abstract(entry)
                        needs_abstract = result.abstract is None
                    if needs_doi and not result.doi:
                        result.doi = self._extract_doi(entry)
                        needs_doi = result.doi is None
                    if needs_pdf and not result.pdf_url:
                        result.pdf_url = self._extract_pdf_url(entry)
                        needs_pdf = result.pdf_url is None

            if needs_pdf and not result.pdf_url:
                download_info = result.metadata.get("airiti_download")
                if isinstance(download_info, dict):
                    result.pdf_url = await self._resolve_download_pdf(download_info)

    def _extract_title(self, entry: dict[str, Any]) -> Optional[str]:
        """Extract title from JSON-LD."""
        title = (
            entry.get("name")
            or entry.get("headline")
            or entry.get("alternativeHeadline")
        )
        if isinstance(title, list):
            title = title[0] if title else None
        return title.strip() if isinstance(title, str) else None

    def _extract_authors(self, entry: dict[str, Any]) -> list[str]:
        """Extract authors from JSON-LD."""
        authors: list[str] = []
        raw_authors = entry.get("author") or []
        if isinstance(raw_authors, dict):
            raw_authors = [raw_authors]
        elif isinstance(raw_authors, str):
            raw_authors = [raw_authors]

        if isinstance(raw_authors, list):
            for author in raw_authors:
                name = self._extract_author_name(author)
                if name:
                    authors.extend(name)

        return authors

    def _extract_author_name(self, author: Any) -> list[str]:
        if isinstance(author, str):
            return self._split_author_string(author)
        if isinstance(author, dict):
            name = author.get("name")
            if isinstance(name, str) and name.strip():
                return [name.strip()]
            given = author.get("givenName")
            family = author.get("familyName")
            if isinstance(given, str) or isinstance(family, str):
                parts = [value for value in [given, family] if isinstance(value, str)]
                combined = " ".join(part.strip() for part in parts if part.strip())
                return [combined] if combined else []
        return []

    def _split_author_string(self, author: str) -> list[str]:
        cleaned = author.strip()
        if not cleaned:
            return []
        if ";" in cleaned:
            return [part.strip() for part in cleaned.split(";") if part.strip()]
        if " and " in cleaned:
            return [part.strip() for part in cleaned.split(" and ") if part.strip()]
        return [cleaned]

    def _extract_year(self, entry: dict[str, Any]) -> Optional[int]:
        """Extract publication year from JSON-LD."""
        date_value = entry.get("datePublished") or entry.get("dateCreated")
        if isinstance(date_value, int):
            return date_value
        if not isinstance(date_value, str):
            return None

        match = re.search(r"\b(\d{4})\b", date_value)
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None

    def _extract_doi(self, entry: dict[str, Any]) -> Optional[str]:
        """Extract DOI from JSON-LD."""
        identifier = entry.get("identifier")
        doi = self._normalize_identifier(identifier)
        if doi:
            return doi

        same_as = entry.get("sameAs")
        return self._normalize_identifier(same_as)

    def _extract_abstract(self, entry: dict[str, Any]) -> Optional[str]:
        abstract = entry.get("abstract") or entry.get("description")
        if isinstance(abstract, list):
            abstract = abstract[0] if abstract else None
        if isinstance(abstract, str):
            cleaned = abstract.strip()
            return cleaned if cleaned else None
        return None

    def _extract_url(self, entry: dict[str, Any]) -> Optional[str]:
        """Extract landing page URL from JSON-LD."""
        url = entry.get("url") or entry.get("@id")
        if not url:
            url = entry.get("mainEntityOfPage") or entry.get("mainEntity")
        if isinstance(url, dict):
            url = url.get("@id") or url.get("url")
        if isinstance(url, str):
            return urllib.parse.urljoin(self.base_url, url)
        return None

    def _extract_pdf_url(self, entry: dict[str, Any]) -> Optional[str]:
        """Extract PDF URL from JSON-LD."""
        encoding = (
            entry.get("encoding")
            or entry.get("associatedMedia")
            or entry.get("distribution")
        )
        if isinstance(encoding, dict):
            encoding = [encoding]

        if isinstance(encoding, list):
            for item in encoding:
                if not isinstance(item, dict):
                    continue
                file_format = item.get("fileFormat") or item.get("encodingFormat") or ""
                content_url = self._coerce_attr_value(
                    item.get("contentUrl") or item.get("url") or item.get("@id")
                )
                if isinstance(content_url, str) and self._looks_like_pdf_url(
                    content_url, file_format
                ):
                    return self._normalize_pdf_url(content_url)

        for key in ("pdfUrl", "pdf", "fileUrl", "contentUrl"):
            content_url = self._coerce_attr_value(entry.get(key))
            if isinstance(content_url, str) and self._looks_like_pdf_url(content_url):
                return self._normalize_pdf_url(content_url)

        return None

    def _looks_like_pdf_url(self, url: str, file_format: Optional[str] = None) -> bool:
        if file_format and "pdf" in file_format.lower():
            return True
        lower = url.strip().lower()
        if not lower:
            return False
        if re.search(r"\.pdf(?:[?#]|$)", lower):
            return True
        if "/pdf/" in lower:
            return True
        if "pdf=" in lower or "format=pdf" in lower:
            return True
        return any(
            keyword in lower
            for keyword in (
                "download",
                "fulltext",
                "full-text",
                "full_text",
                "getpdf",
                "viewpdf",
                "articlepdf",
                "pdffile",
                "file=pdf",
            )
        )

    def _looks_like_pdf_text(self, text: str) -> bool:
        lower = text.strip().lower()
        if not lower:
            return False
        return any(
            keyword in lower
            for keyword in (
                "pdf",
                "full text",
                "fulltext",
                "download",
                "全文",
                "全文下載",
                "下載全文",
                "下載",
            )
        )

    def _normalize_pdf_url(self, url: str) -> str:
        return urllib.parse.urljoin(self.base_url, url.strip())

    def _coerce_attr_value(self, value: Any) -> Optional[str]:
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item:
                    return item
        return None

    def _extract_abstract_from_html(self, soup: BeautifulSoup) -> Optional[str]:
        for meta_name in (
            "citation_abstract",
            "dcterms.abstract",
            "dc.description",
            "DC.Description",
            "description",
            "og:description",
            "twitter:description",
        ):
            meta = soup.find("meta", attrs={"name": meta_name})
            if meta:
                content = self._coerce_attr_value(meta.get("content"))
                value = content.strip() if isinstance(content, str) else ""
                if value:
                    return value
            meta = soup.find("meta", attrs={"property": meta_name})
            if meta:
                content = self._coerce_attr_value(meta.get("content"))
                value = content.strip() if isinstance(content, str) else ""
                if value:
                    return value

        for node in soup.find_all(True):
            node_id_value = node.get("id")
            node_id = node_id_value if isinstance(node_id_value, str) else ""
            classes_value = node.get("class")
            if isinstance(classes_value, list):
                classes = classes_value
            elif isinstance(classes_value, str):
                classes = [classes_value]
            else:
                classes = []
            if any(
                "abstract" in value.lower()
                or "摘要" in value
                or "摘要" in value.lower()
                for value in [node_id, *classes]
                if isinstance(value, str) and value
            ):
                text = node.get_text(" ", strip=True)
                if len(text) > 40:
                    return text

        for node in soup.find_all(["div", "section", "article"]):
            node_id_value = node.get("id")
            node_id = node_id_value if isinstance(node_id_value, str) else ""
            classes_value = node.get("class")
            if isinstance(classes_value, list):
                classes = classes_value
            elif isinstance(classes_value, str):
                classes = [classes_value]
            else:
                classes = []
            if any(
                "content" in value.lower() or "body" in value.lower()
                for value in [node_id, *classes]
                if isinstance(value, str) and value
            ):
                text = node.get_text(" ", strip=True)
                if len(text) > 100 and len(text) < 2000:
                    return text

        return None

    def _extract_doi_from_html(self, soup: BeautifulSoup) -> Optional[str]:
        for meta_name in (
            "citation_doi",
            "dc.identifier",
            "DC.Identifier",
            "prism.doi",
        ):
            meta = soup.find("meta", attrs={"name": meta_name})
            if meta:
                content = self._coerce_attr_value(meta.get("content"))
                doi = self._normalize_identifier(content)
                if doi:
                    return doi
            meta = soup.find("meta", attrs={"property": meta_name})
            if meta:
                content = self._coerce_attr_value(meta.get("content"))
                doi = self._normalize_identifier(content)
                if doi:
                    return doi

        text = soup.get_text(" ", strip=True)
        match = re.search(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", text, re.I)
        if match:
            return self._normalize_identifier(match.group(0))

        for link in soup.find_all("a", href=True):
            href = self._coerce_attr_value(link.get("href"))
            if not isinstance(href, str) or not href:
                continue
            match = re.search(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", href, re.I)
            if match:
                return self._normalize_identifier(match.group(0))

        return None

    def _extract_pdf_from_html(self, soup: BeautifulSoup) -> Optional[str]:
        meta_names = (
            "citation_pdf_url",
            "citation_fulltext_url",
            "citation_fulltext_pdf_url",
            "dc.relation",
            "DC.Relation",
            "dcterms.relation",
        )
        for meta_name in meta_names:
            meta = soup.find("meta", attrs={"name": meta_name})
            if meta:
                content = self._coerce_attr_value(meta.get("content"))
                if isinstance(content, str) and self._looks_like_pdf_url(content):
                    return self._normalize_pdf_url(content)
            meta = soup.find("meta", attrs={"property": meta_name})
            if meta:
                content = self._coerce_attr_value(meta.get("content"))
                if isinstance(content, str) and self._looks_like_pdf_url(content):
                    return self._normalize_pdf_url(content)

        for link in soup.find_all("a", href=True):
            href = self._coerce_attr_value(link.get("href"))
            if not isinstance(href, str) or not href:
                continue
            lower = href.lower()
            text = link.get_text(strip=True).lower()
            if self._looks_like_pdf_url(href):
                return self._normalize_pdf_url(href)
            if self._looks_like_pdf_text(text) and (
                "download" in lower or "fulltext" in lower or "pdf" in lower
            ):
                return self._normalize_pdf_url(href)

        for link in soup.find_all("a", href=True):
            href = self._coerce_attr_value(link.get("href"))
            if not isinstance(href, str) or not href:
                continue
            lower = href.lower()
            text = link.get_text(strip=True).lower()
            if any(
                keyword in lower or keyword in text
                for keyword in [
                    "fulltext",
                    "full-text",
                    "full_text",
                    "article.pdf",
                    "download.pdf",
                ]
            ):
                return self._normalize_pdf_url(href)

        data_attrs = (
            "data-pdf",
            "data-pdf-url",
            "data-url",
            "data-href",
            "data-download",
            "data-file",
        )
        for node in soup.find_all(True):
            for attr in data_attrs:
                value = self._coerce_attr_value(node.get(attr))
                if isinstance(value, str) and self._looks_like_pdf_url(value):
                    return self._normalize_pdf_url(value)

        for node in soup.find_all(True):
            for attr in ("onclick", "data-onclick", "data-action"):
                value = self._coerce_attr_value(node.get(attr))
                if isinstance(value, str):
                    extracted = self._extract_pdf_url_from_text(value)
                    if extracted:
                        return self._normalize_pdf_url(extracted)

        for node in soup.find_all(["iframe", "embed", "object"]):
            value = self._coerce_attr_value(node.get("src") or node.get("data"))
            if isinstance(value, str) and self._looks_like_pdf_url(value):
                return self._normalize_pdf_url(value)

        for link in soup.find_all("link", href=True):
            href = self._coerce_attr_value(link.get("href"))
            if isinstance(href, str) and self._looks_like_pdf_url(href):
                return self._normalize_pdf_url(href)

        return None

    def _extract_pdf_from_node(self, node: Any) -> Optional[str]:
        if not node:
            return None

        for link in node.find_all("a", href=True):
            href = self._coerce_attr_value(link.get("href"))
            if not isinstance(href, str) or not href:
                continue
            if self._looks_like_pdf_url(href):
                return self._normalize_pdf_url(href)
            text = link.get_text(strip=True).lower()
            if self._looks_like_pdf_text(text) and (
                "download" in href.lower()
                or "fulltext" in href.lower()
                or "pdf" in href.lower()
            ):
                return self._normalize_pdf_url(href)

        data_attrs = (
            "data-pdf",
            "data-pdf-url",
            "data-url",
            "data-href",
            "data-download",
            "data-file",
        )
        for element in node.find_all(True):
            for attr in data_attrs:
                value = self._coerce_attr_value(element.get(attr))
                if isinstance(value, str) and self._looks_like_pdf_url(value):
                    return self._normalize_pdf_url(value)

        for element in node.find_all(True):
            for attr in ("onclick", "data-onclick", "data-action"):
                value = self._coerce_attr_value(element.get(attr))
                if isinstance(value, str):
                    extracted = self._extract_pdf_url_from_text(value)
                    if extracted:
                        return self._normalize_pdf_url(extracted)

        return None

    def _extract_title_from_node(self, node: Any) -> Optional[str]:
        for header in node.find_all(["h1", "h2", "h3", "h4", "h5"]):
            text = header.get_text(" ", strip=True)
            if text:
                return text
        for tag in node.find_all(["a", "span", "div"], attrs={"class": True}):
            classes = tag.get("class")
            if isinstance(classes, list) and any(
                "title" in value.lower() for value in classes if isinstance(value, str)
            ):
                text = tag.get_text(" ", strip=True)
                if text:
                    return text
        return None

    def _extract_authors_from_node(self, node: Any) -> list[str]:
        authors: list[str] = []
        for tag in node.find_all(["span", "div", "p"], attrs={"class": True}):
            classes = tag.get("class")
            if isinstance(classes, list) and any(
                "author" in value.lower() or "作者" in value
                for value in classes
                if isinstance(value, str)
            ):
                text = tag.get_text(" ", strip=True)
                authors.extend(self._split_author_string(text))

        if not authors:
            text = node.get_text(" ", strip=True)
            match = re.search(r"作者[:：]\s*([^\n]+)", text)
            if match:
                authors.extend(self._split_author_string(match.group(1)))

        return [author for author in authors if author]

    def _extract_abstract_from_node(self, node: Any) -> Optional[str]:
        for tag in node.find_all(["div", "section", "p"], attrs={"class": True}):
            classes = tag.get("class")
            if isinstance(classes, list) and any(
                "abstract" in value.lower() or "摘要" in value
                for value in classes
                if isinstance(value, str)
            ):
                text = tag.get_text(" ", strip=True)
                if len(text) > 40:
                    return text
        return None

    def _extract_year_from_text(self, text: str) -> Optional[int]:
        match = re.search(r"\b(19\d{2}|20\d{2})\b", text)
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None

    def _extract_pdf_url_from_text(self, text: str) -> Optional[str]:
        if not text:
            return None

        candidates: list[str] = []
        for match in re.findall(r"https?://[^\s'\"<>]+", text):
            candidates.append(match)
        for match in re.findall(r"/[^\s'\"<>]+", text):
            candidates.append(match)
        for match in re.findall(r"[\"']([^\"']+)[\"']", text):
            candidates.append(match)

        for candidate in candidates:
            if self._looks_like_pdf_url(candidate):
                return candidate

        return None

    def _extract_doc_id_from_onclick(self, onclick: Optional[str]) -> Optional[str]:
        if not onclick:
            return None
        match = re.search(r"_文章書目_點擊篇名\('([^']+)'", onclick)
        if match:
            return match.group(1)
        match = re.search(r"DocID=([^'\"&]+)", onclick)
        if match:
            return match.group(1)
        return None

    def _split_volume_issue(
        self, text: Optional[str]
    ) -> tuple[Optional[str], Optional[str]]:
        if not text:
            return None, None
        volume = None
        issue = None
        match = re.search(r"(\d+)\s*卷", text)
        if match:
            volume = match.group(1)
        match = re.search(r"(\d+)\s*期", text)
        if match:
            issue = match.group(1)
        if not (volume or issue):
            match = re.search(r"Vol\.\s*(\d+)", text, re.I)
            if match:
                volume = match.group(1)
            match = re.search(r"No\.\s*(\d+)", text, re.I)
            if match:
                issue = match.group(1)
        return volume, issue

    def _extract_download_info(self, node: Any) -> Optional[dict[str, Any]]:
        download = None
        if hasattr(node, "find"):
            download = node.find(
                lambda tag: tag.has_attr("class")
                and any(
                    isinstance(value, str) and value.lower() == "downloadpoint"
                    for value in tag.get("class")
                )
            )

        if not download and hasattr(node, "find_next_sibling"):
            sibling = node.find_next_sibling()
            while sibling is not None:
                sibling_classes = (
                    sibling.get("class") if hasattr(sibling, "get") else None
                )
                if (
                    isinstance(sibling_classes, list)
                    and "searchResultGroup" in sibling_classes
                ):
                    break
                if sibling.name != "script":
                    download = sibling.find(
                        lambda tag: tag.has_attr("class")
                        and any(
                            isinstance(value, str) and value.lower() == "downloadpoint"
                            for value in tag.get("class")
                        )
                    )
                    if download:
                        break
                sibling = sibling.find_next_sibling()

        if not download:
            return None

        classes_value = download.get("class")
        need_points = ""
        if isinstance(classes_value, list):
            need_points = (
                "" if any("可全文下載" in value for value in classes_value) else "true"
            )

        onclick = self._coerce_attr_value(download.get("onclick"))
        if not isinstance(onclick, str):
            return None
        match = re.search(r"Common_點擊全文下載\((.+)\)", onclick)
        if not match:
            return None
        args = re.findall(r"'([^']*)'", match.group(1))
        if len(args) < 6:
            return None
        doc_id, title, _, token, doc_type, action = args[:6]
        order_id = args[6] if len(args) > 6 else None
        return {
            "doc_id": doc_id,
            "title": urllib.parse.unquote_plus(title),
            "need_points": need_points,
            "token": token,
            "doc_type": doc_type,
            "action": action,
            "order_id": order_id,
        }

    async def _resolve_download_pdf(
        self, download_info: dict[str, Any]
    ) -> Optional[str]:
        doc_id = download_info.get("doc_id")
        token = download_info.get("token")
        if not doc_id or not token:
            return None

        action = download_info.get("action") or "TextDownload"
        endpoint = "/Article/TextDownloadWindowNew"
        if action == "BuyTextDownload":
            endpoint = "/Article/TextDownloadWindow"

        payload = {
            "文章代碼": doc_id,
            "文章篇名": download_info.get("title", ""),
            "需扣除點數": download_info.get("need_points", ""),
            "文獻類型代碼": download_info.get("doc_type", ""),
            "ActionName": action,
        }
        order_id = download_info.get("order_id")
        if order_id:
            payload["OrderID"] = order_id

        js_string = urllib.parse.quote(json.dumps(payload, ensure_ascii=False))
        try:
            response = await self._post_form(
                endpoint,
                data={"jsString": js_string},
                headers={"AjaxRequestVerificationToken": token},
            )
        except Exception as exc:
            logger.debug(f"[{self.name}] download window fetch failed: {exc}")
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        pdf_url = self._extract_pdf_from_html(soup)
        if pdf_url:
            return pdf_url
        return self._extract_download_stage2_url(response.text, download_info)

    def _extract_download_stage2_url(
        self, text: str, download_info: dict[str, Any]
    ) -> Optional[str]:
        url_match = re.search(r"xhr1\.open\('post',\s*'([^']+)'", text)
        token_match = re.search(
            r"var\s+ajaxRequestVerificationToken_DownloadWindow\s*=\s*'([^']+)'",
            text,
        )
        send_match = re.search(r"xhr1\.send\('docID='\s*\+\s*([^\)]+)\)", text)
        if not (url_match and token_match and send_match):
            return None

        var_name = send_match.group(1).strip()
        doc_id_match = re.search(
            r"var\s+" + re.escape(var_name) + r"\s*=\s*'([^']+)'", text
        )
        if not doc_id_match:
            return None

        download_info["download_url"] = urllib.parse.urljoin(
            self.base_url, url_match.group(1)
        )
        download_info["download_token"] = token_match.group(1)
        download_info["download_doc_id"] = doc_id_match.group(1)
        return download_info["download_url"]

    async def _post_form(
        self,
        path: str,
        data: dict[str, str],
        headers: Optional[dict[str, str]] = None,
    ) -> httpx.Response:
        await self.rate_limiter.acquire()
        client = await self._get_client()
        request_headers = self._get_headers()
        if headers:
            request_headers.update(headers)

        last_error = None
        url = urllib.parse.urljoin(self.base_url, path)
        for attempt in range(self.config.max_retries):
            try:
                response = await client.post(url, data=data, headers=request_headers)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as exc:
                last_error = exc
                logger.warning(
                    f"[{self.name}] HTTP error on attempt {attempt + 1}: {exc.response.status_code}"
                )
                if exc.response.status_code in {429, 503, 504}:
                    await asyncio.sleep(2**attempt)
                else:
                    break
            except (httpx.RequestError, asyncio.TimeoutError) as exc:
                last_error = exc
                logger.warning(
                    f"[{self.name}] Request error on attempt {attempt + 1}: {exc}"
                )
                await asyncio.sleep(2**attempt)

        raise RuntimeError(f"Failed to fetch {url}: {last_error}") from last_error

    def _extract_journal(self, entry: dict[str, Any]) -> Optional[str]:
        """Extract journal title from JSON-LD."""
        for key in ("isPartOf", "publication", "periodical"):
            is_part_of = entry.get(key)
            if isinstance(is_part_of, dict):
                journal = is_part_of.get("name") or is_part_of.get("headline")
                if isinstance(journal, str) and journal.strip():
                    return journal.strip()
            if isinstance(is_part_of, list):
                for item in is_part_of:
                    if not isinstance(item, dict):
                        continue
                    journal = item.get("name") or item.get("headline")
                    if isinstance(journal, str) and journal.strip():
                        return journal.strip()
        return None

    def _normalize_identifier(self, identifier: Any) -> Optional[str]:
        """Normalize identifier values into a DOI string."""
        if isinstance(identifier, list):
            for value in identifier:
                doi = self._normalize_identifier(value)
                if doi:
                    return doi
            return None

        if isinstance(identifier, dict):
            value = identifier.get("value") or identifier.get("@id")
            property_id_value = identifier.get("propertyID")
            if isinstance(property_id_value, str):
                if property_id_value.lower() == "doi":
                    value = identifier.get("value") or value
            type_value = identifier.get("type")
            if isinstance(type_value, str):
                if type_value.lower() == "doi":
                    value = identifier.get("identifier") or value
            return self._normalize_identifier(value)

        if isinstance(identifier, str):
            value = identifier.strip()
            value = value.replace("doi:", "").replace("DOI:", "")
            value = value.replace("https://doi.org/", "")
            value = value.replace("http://doi.org/", "")
            value = value.replace("https://dx.doi.org/", "")
            value = value.replace("http://dx.doi.org/", "")
            return value if "/" in value else None

        return None
