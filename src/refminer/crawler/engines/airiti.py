"""Tuned Airiti Library crawler (web scraping)."""

from __future__ import annotations

import json
import logging
import re
import urllib.parse
from typing import Any, Iterable, Optional

from bs4 import BeautifulSoup

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
            while next_url and page_count < self.MAX_PAGES:
                page_count += 1
                response = await self._fetch(next_url)
                soup = BeautifulSoup(response.text, "html.parser")
                page_results = self._parse_results(
                    soup, include_abstract=query.include_abstract
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
                    {
                        "FieldName": 49,
                        "SearchKeyWord": query.query,
                        "FieldQuery": True
                    }
                ],
                "IsFuzzySearch": False
            },
            "BSF": {
                "SearchFiledList": [
                    {
                        "FieldName": 0,
                        "SearchKeyWord": query.query,
                        "FieldQuery": True,
                        "FieldLogic": 0
                    }
                ]
            }
        }

        encoded_json = urllib.parse.quote(json.dumps(query_json, ensure_ascii=False))
        return f"{self.base_url}/Article/Query?queryString={encoded_json}"

    def _parse_results(
        self, soup: BeautifulSoup, include_abstract: bool
    ) -> list[SearchResult]:
        """Parse search results from HTML."""
        results: list[SearchResult] = []

        for entry in self._extract_json_ld(soup):
            result = self._parse_json_ld_entry(entry, include_abstract=include_abstract)
            if result:
                results.append(result)
        return results

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

    def _extract_title(self, entry: dict[str, Any]) -> Optional[str]:
        """Extract title from JSON-LD."""
        title = entry.get("name") or entry.get("headline") or entry.get("alternativeHeadline")
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
        encoding = entry.get("encoding") or entry.get("associatedMedia") or entry.get("distribution")
        if isinstance(encoding, dict):
            encoding = [encoding]

        if isinstance(encoding, list):
            for item in encoding:
                if not isinstance(item, dict):
                    continue
                file_format = item.get("fileFormat") or item.get("encodingFormat") or ""
                content_url = item.get("contentUrl") or item.get("url") or item.get("@id")
                if isinstance(content_url, str):
                    content_lower = content_url.lower()
                    if "pdf" in str(file_format).lower() or content_lower.endswith(
                        ".pdf"
                    ) or "pdf" in content_lower or "/pdf/" in content_lower:
                        return content_url

        return None

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
                "abstract" in value.lower() or "摘要" in value or "摘要" in value.lower()
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
        for meta_name in ("citation_doi", "dc.identifier", "DC.Identifier", "prism.doi"):
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
        meta = soup.find("meta", attrs={"name": "citation_pdf_url"})
        if meta:
            content = self._coerce_attr_value(meta.get("content"))
            if isinstance(content, str) and content:
                return urllib.parse.urljoin(self.base_url, content.strip())

        for link in soup.find_all("a", href=True):
            href = self._coerce_attr_value(link.get("href"))
            if not isinstance(href, str) or not href:
                continue
            lower = href.lower()
            text = link.get_text(strip=True).lower()
            if ".pdf" in lower or "download" in lower or "pdf" in text:
                return urllib.parse.urljoin(self.base_url, href)

        for link in soup.find_all("a", href=True):
            href = self._coerce_attr_value(link.get("href"))
            if not isinstance(href, str) or not href:
                continue
            lower = href.lower()
            text = link.get_text(strip=True).lower()
            if any(keyword in lower or keyword in text for keyword in ["fulltext", "full-text", "full_text", "article.pdf", "download.pdf"]):
                return urllib.parse.urljoin(self.base_url, href)

        return None

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
