"""ChinaXiv crawler using web scraping."""

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


class ChinaXivCrawler(BaseCrawler):
    """ChinaXiv crawler using web scraping."""

    MAX_PAGES = 5
    ENRICH_LIMIT = 10

    @property
    def name(self) -> str:
        return "chinaxiv"

    @property
    def base_url(self) -> str:
        return "https://chinaxiv.org"

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        """Search ChinaXiv for papers."""
        results: list[SearchResult] = []
        seen: set[str] = set()

        try:
            response = await self._post_search(query)
            page_results, page_id = self._parse_results(
                self._decode_response(response), query
            )
            self._extend_results(results, seen, page_results, query.max_results)

            current_page = 1
            while (
                page_id
                and current_page < self.MAX_PAGES
                and self._should_continue(results, query.max_results)
            ):
                current_page += 1
                page_url = self._build_paged_url(page_id, current_page)
                response = await self._fetch(page_url)
                page_results, _ = self._parse_results(
                    self._decode_response(response), query
                )
                if not page_results:
                    break
                self._extend_results(results, seen, page_results, query.max_results)

            if results:
                await self._enrich_results(results, query)

            logger.info(f"[{self.name}] Found {len(results)} results")
        except Exception as e:
            logger.error(f"[{self.name}] Search failed: {e}", exc_info=True)

        return results

    async def _post_search(self, query: SearchQuery) -> httpx.Response:
        await self.rate_limiter.acquire()
        client = await self._get_client()
        url = urllib.parse.urljoin(self.base_url, "/user/search.htm")
        data = {"keywordbanner": query.query}
        headers = self._get_headers()
        headers["Accept-Language"] = "zh-CN,zh;q=0.9,en;q=0.5"
        headers["Referer"] = urllib.parse.urljoin(self.base_url, "/user/search.htm")

        last_error: Exception | None = None
        for attempt in range(self.config.max_retries):
            try:
                response = await client.post(url, data=data, headers=headers)
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

    def _decode_response(self, response: httpx.Response) -> str:
        if response.encoding is None:
            response.encoding = "utf-8"
        text = response.text
        if "\ufffd" not in text:
            return text

        for encoding in ("utf-8", "gb18030"):
            try:
                decoded = response.content.decode(encoding)
            except UnicodeDecodeError:
                continue
            if "\ufffd" not in decoded:
                return decoded
            text = decoded
        return text

    def _parse_results(
        self, html_text: str, query: SearchQuery
    ) -> tuple[list[SearchResult], Optional[str]]:
        soup = BeautifulSoup(html_text, "html.parser")
        items = soup.select(".list ul li")
        if not items:
            items = soup.select(".list li")

        results: list[SearchResult] = []
        for item in items:
            try:
                result = self._parse_result_item(item, query)
                if result:
                    results.append(result)
            except Exception as exc:
                logger.debug(f"[{self.name}] Failed to parse item: {exc}")

        page_id = self._extract_page_id(soup)
        return results, page_id

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
        metadata = {}
        chinaxiv_id = self._extract_chinaxiv_id(detail_url)
        if chinaxiv_id:
            metadata["chinaxiv_id"] = chinaxiv_id

        return SearchResult(
            title=title,
            authors=authors,
            year=year,
            doi=None,
            abstract=abstract,
            source=self.name,
            url=detail_url,
            pdf_url=pdf_url,
            journal=None,
            volume=None,
            issue=None,
            pages=None,
            citation_count=None,
            metadata=metadata,
        )

    def _extract_title_and_url(self, item: Any) -> tuple[Optional[str], Optional[str]]:
        link = item.select_one("h3 a[href]") if hasattr(item, "select_one") else None
        if not link and hasattr(item, "select_one"):
            link = item.select_one("a[href^='/abs/']")

        title = None
        detail_url = None
        if link and hasattr(link, "get"):
            title = self._normalize_text(link.get_text(" ", strip=True))
            href = link.get("href")
            if isinstance(href, str):
                detail_url = urllib.parse.urljoin(self.base_url, href)

        if not title and hasattr(item, "find"):
            header = item.find(["h3", "h2", "h4"])
            if header:
                title = self._normalize_text(header.get_text(" ", strip=True))

        return title, detail_url

    def _extract_authors(self, item: Any) -> list[str]:
        authors: list[str] = []
        if hasattr(item, "select"):
            for link in item.select(".name a"):
                name = self._normalize_text(link.get_text(" ", strip=True))
                if name:
                    authors.append(name)
            if not authors:
                for link in item.select("a[href*='field=author']"):
                    name = self._normalize_text(link.get_text(" ", strip=True))
                    if name:
                        authors.append(name)

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
            if isinstance(href, str) and "/user/download.htm" in href:
                return urllib.parse.urljoin(self.base_url, href)
        return None

    def _extract_page_id(self, soup: BeautifulSoup) -> Optional[str]:
        page_id = None
        for link in soup.find_all("a", href=True):
            href = link.get("href")
            if not isinstance(href, str):
                continue
            match = re.search(r"pageId=(\d+)", href)
            if match:
                page_id = match.group(1)
                break
        return page_id

    def _build_paged_url(self, page_id: str, page: int) -> str:
        params = {
            "pageId": page_id,
            "setId": "recordList",
            "currentPage": str(page),
        }
        query = urllib.parse.urlencode(params)
        return urllib.parse.urljoin(self.base_url, f"/user/search.htm?{query}")

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

    def _extract_chinaxiv_id(self, detail_url: Optional[str]) -> Optional[str]:
        if not detail_url:
            return None
        match = re.search(r"/abs/([\w.\-]+)", detail_url)
        if match:
            return match.group(1)
        return None

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
            if not (needs_abstract or needs_doi or needs_pdf or needs_authors or needs_year):
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
        label = soup.find("b", string=re.compile(r"摘要"))
        if label and label.parent:
            text = label.parent.get_text(" ", strip=True)
            if text:
                return self._strip_label(text, ("摘要", "Abstract"))

        for node in soup.select("div.paper div.content div.bd"):
            text = node.get_text(" ", strip=True)
            if "摘要" in text:
                return self._strip_label(text, ("摘要", "Abstract"))
        return None

    def _extract_detail_authors(self, soup: BeautifulSoup) -> list[str]:
        authors: list[str] = []
        for link in soup.select("div.paper div.content div.bd ul li a[href*='field=author']"):
            name = self._normalize_text(link.get_text(" ", strip=True))
            if name:
                authors.append(name)
        return authors

    def _extract_detail_year(self, soup: BeautifulSoup) -> Optional[int]:
        for node in soup.select("div.paper div.content div.bd ul li"):
            text = node.get_text(" ", strip=True)
            if "提交时间" in text:
                match = re.search(r"\b(19\d{2}|20\d{2})\b", text)
                if match:
                    return int(match.group(1))
        for node in soup.select("div.paper div.content div.ft td"):
            text = node.get_text(" ", strip=True)
            match = re.search(r"\b(19\d{2}|20\d{2})\b", text)
            if match:
                return int(match.group(1))
        return None

    def _extract_detail_pdf_url(self, soup: BeautifulSoup) -> Optional[str]:
        for link in soup.select("div.paper div.content div.ft a[href*='/user/download.htm']"):
            href = link.get("href")
            if isinstance(href, str):
                return urllib.parse.urljoin(self.base_url, href)
        return None

    def _extract_detail_doi(self, soup: BeautifulSoup) -> Optional[str]:
        for link in soup.select("div.paper div.content div.bd a[href*='doi.org']"):
            href = link.get("href")
            doi = self._normalize_doi(href)
            if doi:
                return doi
            text = link.get_text(" ", strip=True)
            doi = self._normalize_doi(text)
            if doi:
                return doi
        return None

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
