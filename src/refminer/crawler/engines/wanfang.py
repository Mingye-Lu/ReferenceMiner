"""Wanfang Data crawler using web scraping."""

from __future__ import annotations

import asyncio
import logging
import re
import urllib.parse
from typing import Any, Optional

import httpx
from bs4 import BeautifulSoup

from refminer.crawler.base import BaseCrawler
from refminer.crawler.models import SearchQuery, SearchResult

logger = logging.getLogger(__name__)


class WanfangCrawler(BaseCrawler):
    """Wanfang Data crawler using web scraping."""

    MAX_PAGES = 5
    ENRICH_LIMIT = 10

    @property
    def name(self) -> str:
        return "wanfang"

    @property
    def base_url(self) -> str:
        return "https://s.wanfangdata.com.cn"

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        """Search Wanfang for papers."""
        results: list[SearchResult] = []
        seen: set[str] = set()

        try:
            current_page = 1
            while current_page <= self.MAX_PAGES and self._should_continue(results, query.max_results):
                page_url = self._build_search_url(query, current_page)
                response = await self._fetch(page_url)
                page_results = self._parse_results(
                    self._decode_response(response), query
                )
                if not page_results:
                    break
                self._extend_results(results, seen, page_results, query.max_results)
                current_page += 1

            if results:
                await self._enrich_results(results, query)

            logger.info(f"[{self.name}] Found {len(results)} results")
        except Exception as e:
            logger.error(f"[{self.name}] Search failed: {e}", exc_info=True)

        return results

    def _build_search_url(self, query: SearchQuery, page: int) -> str:
        params = {
            "q": query.query,
            "p": str(page),
        }
        query_str = urllib.parse.urlencode(params)
        return urllib.parse.urljoin(self.base_url, f"/paper?{query_str}")

    def _decode_response(self, response: httpx.Response) -> str:
        if response.encoding is None:
            response.encoding = "utf-8"
        text = response.text
        if "\ufffd" not in text:
            return text

        for encoding in ("utf-8", "gb18030", "gbk"):
            try:
                decoded = response.content.decode(encoding)
            except Exception:
                continue
            if "\ufffd" not in decoded:
                return decoded
            text = decoded
        return text

    def _parse_results(
        self, html_text: str, query: SearchQuery
    ) -> list[SearchResult]:
        soup = BeautifulSoup(html_text, "html.parser")
        items = soup.select(".search-result-item")
        if not items:
            items = soup.select(".item")
        if not items:
            items = soup.select("div[class*='result']")
        if not items:
            items = soup.select(".paper-item")
        if not items:
            items = soup.select(".list-item")

        results: list[SearchResult] = []
        for item in items:
            try:
                result = self._parse_result_item(item, query)
                if result:
                    results.append(result)
            except Exception as exc:
                logger.debug(f"[{self.name}] Failed to parse item: {exc}")

        return results

    def _parse_result_item(
        self, item: Any, query: SearchQuery
    ) -> Optional[SearchResult]:
        title, detail_url = self._extract_title_and_url(item)
        if not title:
            return None

        authors = self._extract_authors(item)
        year = self._extract_year(item)
        if year is not None:
            if query.year_from and year < query.year_from:
                return None
            if query.year_to and year > query.year_to:
                return None

        abstract = self._extract_abstract(item) if query.include_abstract else None
        pdf_url = self._extract_pdf_url(item)
        journal = self._extract_journal(item)
        doi = self._extract_doi(item)
        metadata = {}
        wanfang_id = self._extract_wanfang_id(detail_url)
        if wanfang_id:
            metadata["wanfang_id"] = wanfang_id

        return SearchResult(
            title=title,
            authors=authors,
            year=year,
            doi=doi,
            abstract=abstract,
            source=self.name,
            url=detail_url,
            pdf_url=pdf_url,
            journal=journal,
            volume=None,
            issue=None,
            pages=None,
            citation_count=None,
            metadata=metadata,
        )

    def _extract_title_and_url(self, item: Any) -> tuple[Optional[str], Optional[str]]:
        link = item.select_one("a[href*='details']") if hasattr(item, "select_one") else None
        if not link and hasattr(item, "select_one"):
            link = item.select_one("h3 a[href]")
        if not link and hasattr(item, "select_one"):
            link = item.select_one(".title a")
        if not link and hasattr(item, "select_one"):
            link = item.select_one("a[href]")

        title = None
        detail_url = None
        if link and hasattr(link, "get"):
            title = self._normalize_text(link.get_text(" ", strip=True))
            href = link.get("href")
            if isinstance(href, str):
                detail_url = urllib.parse.urljoin(self.base_url, href)

        if not title and hasattr(item, "select_one"):
            title_elem = item.select_one(".title")
            if title_elem:
                title = self._normalize_text(title_elem.get_text(" ", strip=True))

        return title, detail_url

    def _extract_authors(self, item: Any) -> list[str]:
        authors: list[str] = []
        if hasattr(item, "select"):
            for link in item.select(".author a"):
                name = self._normalize_text(link.get_text(" ", strip=True))
                if name:
                    authors.append(name)
            if not authors:
                author_elem = item.select_one(".author")
                if author_elem:
                    text = self._normalize_text(author_elem.get_text(" ", strip=True))
                    if text:
                        authors = self._split_author_string(text)

        if not authors and hasattr(item, "get_text"):
            text = item.get_text(" ", strip=True)
            match = re.search(r"作者[:：]\s*([^\n]+)", text)
            if match:
                authors = self._split_author_string(match.group(1))

        return [author for author in authors if author]

    def _extract_year(self, item: Any) -> Optional[int]:
        if not hasattr(item, "get_text"):
            return None
        text = item.get_text(" ", strip=True)
        match = re.search(r"\b(19\d{2}|20\d{2})\b", text)
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None

    def _extract_abstract(self, item: Any) -> Optional[str]:
        if not hasattr(item, "find_all"):
            return None
        for node in item.find_all("p"):
            text = node.get_text(" ", strip=True)
            if not text:
                continue
            if "摘要" in text or "Abstract" in text:
                return self._strip_label(text, ("摘要", "Abstract"))
        return None

    def _extract_pdf_url(self, item: Any) -> Optional[str]:
        if not hasattr(item, "find_all"):
            return None
        for link in item.find_all("a", href=True):
            href = link.get("href")
            if isinstance(href, str) and (".pdf" in href.lower() or "download" in href.lower()):
                return urllib.parse.urljoin(self.base_url, href)
        return None

    def _extract_journal(self, item: Any) -> Optional[str]:
        if not hasattr(item, "select_one"):
            return None
        journal_elem = item.select_one(".journal")
        if not journal_elem:
            journal_elem = item.select_one(".source")
        if journal_elem:
            return self._normalize_text(journal_elem.get_text(" ", strip=True))
        return None

    def _extract_doi(self, item: Any) -> Optional[str]:
        if not hasattr(item, "find_all"):
            return None
        for link in item.find_all("a", href=True):
            href = link.get("href")
            if isinstance(href, str) and "doi.org" in href:
                return self._normalize_doi(href)
        return None

    def _extract_wanfang_id(self, detail_url: Optional[str]) -> Optional[str]:
        if not detail_url:
            return None
        match = re.search(r"/details/([A-Za-z0-9\-_]+)", detail_url)
        if match:
            return match.group(1)
        return None

    def _extend_results(
        self,
        results: list[SearchResult],
        seen: set[str],
        page_results: list[SearchResult],
        max_results: int,
    ) -> None:
        for result in page_results:
            result_key = result.get_hash()
            if result_key in seen:
                continue
            seen.add(result_key)
            results.append(result)
            if max_results > 0 and len(results) >= max_results:
                break

    def _should_continue(self, results: list[SearchResult], max_results: int) -> bool:
        return max_results <= 0 or len(results) < max_results

    def _split_author_string(self, author: str) -> list[str]:
        cleaned = author.strip()
        if not cleaned:
            return []
        for sep in (";", "，", ",", "、"):
            if sep in cleaned:
                return [part.strip() for part in cleaned.split(sep) if part.strip()]
        if " and " in cleaned:
            return [part.strip() for part in cleaned.split(" and ") if part.strip()]
        return [cleaned]

    def _normalize_text(self, value: Any) -> Optional[str]:
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        if isinstance(value, int):
            return str(value)
        if isinstance(value, float):
            if value.is_integer():
                return str(int(value))
            return str(value)
        return None

    def _strip_label(self, text: str, labels: tuple[str, ...]) -> str:
        cleaned = text.strip()
        for label in labels:
            if label in cleaned:
                cleaned = cleaned.replace(label, "")
        return cleaned.strip(" ：: ")

    def _normalize_doi(self, value: Any) -> Optional[str]:
        if not isinstance(value, str):
            return None
        cleaned = value.strip()
        cleaned = cleaned.replace("doi:", "").replace("DOI:", "")
        cleaned = cleaned.replace("https://doi.org/", "")
        cleaned = cleaned.replace("http://doi.org/", "")
        cleaned = cleaned.replace("https://dx.doi.org/", "")
        cleaned = cleaned.replace("http://dx.doi.org/", "")
        return cleaned if "/" in cleaned else None

    async def _enrich_results(
        self, results: list[SearchResult], query: SearchQuery
    ) -> None:
        if not results:
            return

        limit = self.ENRICH_LIMIT
        if query.max_results > 0:
            limit = min(limit, query.max_results)

        for result in results[:limit]:
            if not result.url:
                continue
            needs_abstract = query.include_abstract and not result.abstract
            needs_doi = not result.doi
            needs_pdf = not result.pdf_url
            needs_authors = not result.authors
            needs_year = result.year is None
            if not (
                needs_abstract or needs_doi or needs_pdf or needs_authors or needs_year
            ):
                continue

            try:
                response = await self._fetch(result.url)
            except Exception as exc:
                logger.debug(
                    f"[{self.name}] Detail fetch failed for {result.url}: {exc}"
                )
                continue

            soup = BeautifulSoup(self._decode_response(response), "html.parser")
            detail = self._extract_detail_data(soup)

            if needs_abstract and detail.get("abstract"):
                result.abstract = detail["abstract"]
            if needs_doi and detail.get("doi"):
                result.doi = detail["doi"]
            if needs_pdf and detail.get("pdf_url"):
                result.pdf_url = detail["pdf_url"]
            if needs_authors and detail.get("authors"):
                result.authors = detail["authors"]
            if needs_year and detail.get("year"):
                result.year = detail["year"]

    def _extract_detail_data(self, soup: BeautifulSoup) -> dict[str, Any]:
        abstract = self._extract_detail_abstract(soup)
        authors = self._extract_detail_authors(soup)
        year = self._extract_detail_year(soup)
        pdf_url = self._extract_detail_pdf_url(soup)
        doi = self._extract_detail_doi(soup)

        return {
            "abstract": abstract,
            "authors": authors,
            "year": year,
            "pdf_url": pdf_url,
            "doi": doi,
        }

    def _extract_detail_abstract(self, soup: BeautifulSoup) -> Optional[str]:
        for node in soup.find_all("b"):
            text = node.get_text(" ", strip=True)
            if "摘要" in text:
                if node.parent:
                    parent_text = node.parent.get_text(" ", strip=True)
                    if parent_text:
                        return self._strip_label(parent_text, ("摘要", "Abstract"))

        for node in soup.select(".abstract"):
            text = node.get_text(" ", strip=True)
            if text:
                return self._strip_label(text, ("摘要", "Abstract"))
        return None

    def _extract_detail_authors(self, soup: BeautifulSoup) -> list[str]:
        authors: list[str] = []
        for link in soup.select(".author a"):
            name = self._normalize_text(link.get_text(" ", strip=True))
            if name:
                authors.append(name)
        return authors

    def _extract_detail_year(self, soup: BeautifulSoup) -> Optional[int]:
        for node in soup.select(".year, .publish-date"):
            text = node.get_text(" ", strip=True)
            match = re.search(r"\b(19\d{2}|20\d{2})\b", text)
            if match:
                return int(match.group(1))
        return None

    def _extract_detail_pdf_url(self, soup: BeautifulSoup) -> Optional[str]:
        for link in soup.select("a[href]"):
            href = link.get("href")
            if isinstance(href, str) and (".pdf" in href.lower() or "download" in href.lower()):
                return urllib.parse.urljoin(self.base_url, href)
        return None

    def _extract_detail_doi(self, soup: BeautifulSoup) -> Optional[str]:
        for link in soup.select("a[href*='doi.org']"):
            href = link.get("href")
            doi = self._normalize_doi(href)
            if doi:
                return doi
            text = link.get_text(" ", strip=True)
            doi = self._normalize_doi(text)
            if doi:
                return doi
        return None
