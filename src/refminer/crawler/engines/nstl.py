"""NSTL crawler (web scraping)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
import urllib.parse
import uuid
from typing import Any, Iterable, Optional

import httpx
from bs4 import BeautifulSoup

from refminer.crawler.base import BaseCrawler
from refminer.crawler.models import SearchQuery, SearchResult

logger = logging.getLogger(__name__)


class NstlCrawler(BaseCrawler):
    """NSTL crawler using web scraping."""

    @property
    def name(self) -> str:
        return "nstl"

    @property
    def base_url(self) -> str:
        return "https://www.nstl.gov.cn"

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        """Search NSTL for papers."""
        results: list[SearchResult] = []

        try:
            results = await self._search_api(query)
            if results:
                logger.info(f"[{self.name}] Found {len(results)} results via API")
                return results
        except Exception as e:
            logger.warning(f"[{self.name}] API search failed: {e}")

        try:
            search_url = self._build_search_url(query)
            response = await self._fetch(search_url)
            soup = BeautifulSoup(response.text, "html.parser")
            results = self._parse_results(soup, query)
            logger.info(f"[{self.name}] Found {len(results)} results via HTML")
        except Exception as e:
            logger.error(f"[{self.name}] Search failed: {e}", exc_info=True)

        return results

    async def _search_api(self, query: SearchQuery) -> list[SearchResult]:
        await self._warm_api_session()
        nck = await self._ensure_tracking_cookies()

        api_url = f"{self.base_url}/api/service/nstl/web/execute"
        params = self._build_api_params()
        page_size = self._normalize_page_size(query.max_results)
        query_payload = self._build_query_payload(query, page_size)
        query_string = json.dumps(query_payload, ensure_ascii=True, separators=(",", ":"))
        search_word = urllib.parse.quote(query.query, safe="")
        search_word_id, search_id = self._build_search_ids(search_word, nck)
        payload = self._build_api_payload(query_string, search_word_id, search_id, page_size)
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/search.html",
            "X-Requested-With": "XMLHttpRequest",
        }

        try:
            response = await self._post_form(
                api_url, params=params, data=payload, headers=headers
            )
            data = response.json()
            results = self._parse_api_results(data, query)
        except RuntimeError as e:
            logger.warning(f"[{self.name}] API form search failed: {e}")
            results = await self._search_api_execute_post(
                query,
                params,
                query_payload,
                search_word_id,
                search_id,
                page_size,
            )
        if query.max_results > 0:
            return results[: query.max_results]
        return results

    async def _warm_api_session(self) -> None:
        try:
            await self._fetch(self.base_url)
            await self._fetch(f"{self.base_url}/index.html")
            await self._fetch(
                f"{self.base_url}/href.html?timestamp={int(time.time() * 1000)}"
            )
            await self._fetch(f"{self.base_url}/search.html")
        except Exception:
            return

    def _build_api_params(self) -> dict[str, Any]:
        timestamp = int(time.time() * 1000)
        seed = f"{timestamp}istic2009nstlweb"
        tid = hashlib.md5(seed.encode("utf-8")).hexdigest()
        return {
            "target": "nstl4.search4",
            "function": "paper/pc/list/pl",
            "time": str(timestamp),
            "tid": tid,
        }

    def _build_query_payload(self, query: SearchQuery, page_size: int) -> dict[str, Any]:
        return {
            "c": page_size,
            "st": "",
            "f": [],
            "p": "",
            "q": [
                {
                    "k": "",
                    "v": query.query,
                    "e": 1,
                    "o": "AND",
                    "a": 0,
                }
            ],
            "op": "AND",
            "s": ["nstl", "haveAbsAuK:desc", "yea:desc", "score"],
            "t": ["JournalPaper", "ProceedingsPaper", "DegreePaper"],
        }

    def _build_api_payload(
        self,
        query_string: str,
        search_word_id: str,
        search_id: str,
        page_size: int,
    ) -> dict[str, Any]:
        return {
            "query": query_string,
            "webDisplayId": "11",
            "sl": 1,
            "searchWordId": search_word_id,
            "searchId": search_id,
            "facetRelation": "{}",
            "pageSize": page_size,
            "pageNumber": 1,
        }

    async def _search_api_execute_post(
        self,
        query: SearchQuery,
        params: dict[str, Any],
        query_payload: dict[str, Any],
        search_word_id: str,
        search_id: str,
        page_size: int,
    ) -> list[SearchResult]:
        api_url = f"{self.base_url}/api/service/nstl/web/execute_post"
        payload = {
            "query": query_payload,
            "webDisplayId": "11",
            "sl": 1,
            "searchWordId": search_word_id,
            "searchId": search_id,
            "facetRelation": {},
            "pageSize": page_size,
            "pageNumber": 1,
        }
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/search.html",
            "X-Requested-With": "XMLHttpRequest",
        }

        response = await self._fetch(
            api_url, method="POST", params=params, data=payload, headers=headers
        )
        data = response.json()
        return self._parse_api_results(data, query)

    def _build_search_ids(
        self, search_word: str, nck_cookie: Optional[str]
    ) -> tuple[str, str]:
        token = self._build_guid()
        nck_value = nck_cookie if nck_cookie is not None else "null"
        first_time = int(time.time() * 1000)
        search_word_id = hashlib.md5(
            f"{search_word}{token}{first_time}{nck_value}".encode("utf-8")
        ).hexdigest()
        second_time = int(time.time() * 1000)
        search_id = hashlib.md5(
            f"{search_word_id}{token}{second_time}{nck_value}".encode("utf-8")
        ).hexdigest()
        return search_word_id, search_id

    def _build_guid(self) -> str:
        return str(uuid.uuid4()).lower()

    def _normalize_page_size(self, max_results: int) -> int:
        page_size = max_results if max_results > 0 else 10
        return min(max(page_size, 1), 50)

    async def _ensure_tracking_cookies(self) -> Optional[str]:
        nck = self._get_cookie_value("NCK")
        token = self._get_cookie_value("nstl_token")
        if nck and token:
            return nck

        try:
            await self._fetch(f"{self.base_url}/security/captcha.html")
        except Exception:
            nck = self._get_cookie_value("NCK")
            token = self._get_cookie_value("nstl_token")
        else:
            nck = self._get_cookie_value("NCK")
            token = self._get_cookie_value("nstl_token")

        client = await self._get_client()
        if not nck:
            nck = self._build_guid()
            client.cookies.set("NCK", nck, domain="nstl.gov.cn", path="/")
        if not token:
            token = self._build_guid()
            client.cookies.set("nstl_token", token, domain="nstl.gov.cn", path="/")

        return nck

    def _get_cookie_value(self, name: str) -> Optional[str]:
        if not self._client:
            return None
        value = self._client.cookies.get(name)
        return value if isinstance(value, str) else None

    async def _post_form(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> httpx.Response:
        await self.rate_limiter.acquire()

        client = await self._get_client()
        request_headers = self._get_headers()
        if headers:
            request_headers.update(headers)

        last_error: Exception | None = None
        for attempt in range(self.config.max_retries):
            try:
                response = await client.post(
                    url, params=params, data=data, headers=request_headers
                )
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location", "")
                    if "captcha" in location or "500" in location:
                        raise httpx.HTTPStatusError(
                            f"Blocked by redirect to {location}",
                            request=response.request,
                            response=response,
                        )
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as e:
                last_error = e
                location = e.response.headers.get("location", "")
                logger.warning(
                    f"[{self.name}] HTTP error on attempt {attempt + 1}: {e.response.status_code} {location}"
                )
                if e.response.status_code in {429, 503, 504, 302}:
                    await asyncio.sleep(2**attempt)
                else:
                    break
            except (httpx.RequestError, asyncio.TimeoutError) as e:
                last_error = e
                logger.warning(
                    f"[{self.name}] Request error on attempt {attempt + 1}: {e}"
                )
                await asyncio.sleep(2**attempt)

        raise RuntimeError(f"Failed to fetch {url}: {last_error}") from last_error

    def _parse_api_results(
        self, payload: dict[str, Any], query: SearchQuery
    ) -> list[SearchResult]:
        results: list[SearchResult] = []
        rows = self._coerce_api_rows(payload.get("data"))
        for row in rows:
            fields = {
                str(item.get("f")): item.get("v")
                for item in row
                if isinstance(item, dict) and isinstance(item.get("f"), str)
            }
            result = self._parse_api_row(fields, query)
            if result:
                results.append(result)
        return results

    def _coerce_api_rows(self, data: Any) -> list[list[dict[str, Any]]]:
        if isinstance(data, dict):
            data = data.get("list") or data.get("data")

        if not isinstance(data, list) or not data:
            return []

        if isinstance(data[0], list):
            rows = []
            for row in data:
                if isinstance(row, list):
                    rows.append([item for item in row if isinstance(item, dict)])
            return rows

        if all(isinstance(item, dict) for item in data):
            if all("f" in item and "v" in item for item in data):
                return [data]
            rows = []
            for row in data:
                if not isinstance(row, dict):
                    continue
                rows.append(
                    [
                        {"f": key, "v": value}
                        for key, value in row.items()
                        if value is not None
                    ]
                )
            return rows

        return []

    def _parse_api_row(
        self, fields: dict[str, Any], query: SearchQuery
    ) -> Optional[SearchResult]:
        title = self._normalize_text(
            fields.get("titl")
            or fields.get("title")
            or fields.get("tit")
            or fields.get("C_TITLE")
            or fields.get("name")
        )
        if not title:
            return None

        authors = self._normalize_authors(
            fields.get("hasAut")
            or fields.get("aut")
            or fields.get("author")
            or fields.get("authors")
        )
        year = self._normalize_int(
            fields.get("yea") or fields.get("year") or fields.get("pubYear")
        )
        if year is not None:
            if query.year_from and year < query.year_from:
                return None
            if query.year_to and year > query.year_to:
                return None

        doi = self._normalize_identifier(fields.get("doi") or fields.get("DOI"))
        abstract = None
        if query.include_abstract:
            abstract = self._normalize_text(
                fields.get("abs") or fields.get("abstract")
            )

        journal = self._normalize_text(
            fields.get("hasSotit")
            or fields.get("journal")
            or fields.get("sourceTitle")
        )
        volume = self._normalize_text(fields.get("vol") or fields.get("volume"))
        issue = self._normalize_text(fields.get("iss") or fields.get("issue"))
        pages = self._normalize_text(
            fields.get("pageRange") or fields.get("pages") or fields.get("pag")
        )
        citation_count = self._normalize_int(
            fields.get("citationCount")
            or fields.get("cited")
            or fields.get("cit")
        )

        url = self._normalize_text(
            fields.get("url") or fields.get("detailUrl") or fields.get("link")
        )
        if url:
            url = urllib.parse.urljoin(self.base_url, url)

        pdf_url = self._normalize_text(
            fields.get("pdf")
            or fields.get("pdfUrl")
            or fields.get("downloadUrl")
            or fields.get("fileUrl")
        )
        if pdf_url:
            pdf_url = urllib.parse.urljoin(self.base_url, pdf_url)

        metadata = {}
        nstl_id = fields.get("id") or fields.get("ID") or fields.get("paperId")
        nstl_type = fields.get("type") or fields.get("docType")
        if nstl_id:
            metadata["nstl_id"] = nstl_id
        if nstl_type:
            metadata["nstl_type"] = nstl_type

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
            volume=volume,
            issue=issue,
            pages=pages,
            citation_count=citation_count,
            metadata=metadata,
        )

    def _normalize_authors(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            authors: list[str] = []
            for item in value:
                if isinstance(item, str):
                    authors.extend(self._split_author_string(item))
                elif isinstance(item, dict):
                    name = item.get("name")
                    if isinstance(name, str) and name.strip():
                        authors.append(name.strip())
            return authors
        if isinstance(value, dict):
            name = value.get("name")
            if isinstance(name, str) and name.strip():
                return [name.strip()]
        if isinstance(value, str):
            return self._split_author_string(value)
        return []

    def _build_search_url(self, query: SearchQuery) -> str:
        """Build NSTL search URL."""
        params = {
            "keyword": query.query,
        }

        if query.year_from:
            params["year_from"] = str(query.year_from)
        if query.year_to:
            params["year_to"] = str(query.year_to)

        encoded_params = urllib.parse.urlencode(params)
        return f"{self.base_url}/search?{encoded_params}"

    def _parse_results(
        self, soup: BeautifulSoup, query: SearchQuery
    ) -> list[SearchResult]:
        """Parse search results from HTML."""
        results: list[SearchResult] = []

        for entry in self._extract_json_ld(soup):
            result = self._parse_json_ld_entry(entry, query)
            if result:
                results.append(result)

        if query.max_results > 0:
            return results[: query.max_results]
        return results

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
        self, entry: dict[str, Any], query: SearchQuery
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
        volume = self._extract_volume(entry)
        issue = self._extract_issue(entry)
        pages = self._extract_pages(entry)
        citation_count = self._extract_citation_count(entry)

        abstract = None
        if query.include_abstract:
            abstract = entry.get("abstract") or entry.get("description")

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
            volume=volume,
            issue=issue,
            pages=pages,
            citation_count=citation_count,
        )

    def _extract_title(self, entry: dict[str, Any]) -> Optional[str]:
        """Extract title from JSON-LD."""
        title = entry.get("name") or entry.get("headline") or entry.get("alternativeHeadline")
        if isinstance(title, list):
            title = title[0] if title else None
        return title.strip() if isinstance(title, str) else None

    def _extract_authors(self, entry: dict[str, Any]) -> list[str]:
        """Extract authors from JSON-LD."""
        authors: list[str] = []
        raw_authors = entry.get("author") or entry.get("creator") or entry.get("authors") or []
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
        doi_value = entry.get("doi")
        doi = self._normalize_identifier(doi_value)
        if doi:
            return doi

        identifier = entry.get("identifier")
        doi = self._normalize_identifier(identifier)
        if doi:
            return doi

        same_as = entry.get("sameAs")
        return self._normalize_identifier(same_as)

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
        encoding = entry.get("encoding") or entry.get("associatedMedia")
        if isinstance(encoding, dict):
            encoding = [encoding]

        if isinstance(encoding, list):
            for item in encoding:
                if not isinstance(item, dict):
                    continue
                file_format = item.get("fileFormat") or item.get("encodingFormat") or ""
                content_url = item.get("contentUrl") or item.get("url")
                if isinstance(content_url, str):
                    content_lower = content_url.lower()
                    if "pdf" in str(file_format).lower() or content_lower.endswith(
                        ".pdf"
                    ) or "pdf" in content_lower:
                        return urllib.parse.urljoin(self.base_url, content_url)

        return None

    def _extract_volume(self, entry: dict[str, Any]) -> Optional[str]:
        """Extract volume from JSON-LD."""
        value = entry.get("volumeNumber") or entry.get("volume")
        if value:
            return self._normalize_text(value)

        return self._extract_part_of_field(entry, ("volumeNumber", "volume"))

    def _extract_issue(self, entry: dict[str, Any]) -> Optional[str]:
        """Extract issue from JSON-LD."""
        value = entry.get("issueNumber") or entry.get("issue")
        if value:
            return self._normalize_text(value)

        return self._extract_part_of_field(entry, ("issueNumber", "issue"))

    def _extract_pages(self, entry: dict[str, Any]) -> Optional[str]:
        """Extract page range from JSON-LD."""
        pagination = entry.get("pagination") or entry.get("pageRange") or entry.get(
            "pages"
        )
        normalized = self._normalize_text(pagination)
        if normalized:
            return normalized

        page_start = self._normalize_text(entry.get("pageStart"))
        page_end = self._normalize_text(entry.get("pageEnd"))
        if page_start and page_end:
            return f"{page_start}-{page_end}"
        if page_start:
            return page_start
        if page_end:
            return page_end
        return None

    def _extract_citation_count(self, entry: dict[str, Any]) -> Optional[int]:
        """Extract citation count from JSON-LD."""
        value = entry.get("citationCount")
        if value is None:
            value = entry.get("citedByCount")
        if value is None:
            value = self._extract_interaction_statistic(
                entry.get("interactionStatistic")
            )
        return self._normalize_int(value)

    def _extract_interaction_statistic(self, payload: Any) -> Optional[int]:
        if isinstance(payload, list):
            for item in payload:
                value = self._extract_interaction_statistic(item)
                if value is not None:
                    return value
            return None

        if isinstance(payload, dict):
            value = payload.get("userInteractionCount")
            if value is None:
                value = payload.get("interactionCount") or payload.get("value")
            if value is not None:
                return self._normalize_int(value)

        return None

    def _extract_part_of_field(
        self, entry: dict[str, Any], keys: tuple[str, ...]
    ) -> Optional[str]:
        for key in ("isPartOf", "publication", "periodical"):
            is_part_of = entry.get(key)
            if isinstance(is_part_of, dict):
                value = self._extract_from_dict(is_part_of, keys)
                if value:
                    return value
            if isinstance(is_part_of, list):
                for item in is_part_of:
                    if not isinstance(item, dict):
                        continue
                    value = self._extract_from_dict(item, keys)
                    if value:
                        return value
        return None

    def _extract_from_dict(
        self, data: dict[str, Any], keys: tuple[str, ...]
    ) -> Optional[str]:
        for key in keys:
            value = data.get(key)
            normalized = self._normalize_text(value)
            if normalized:
                return normalized
        return None

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

    def _normalize_int(self, value: Any) -> Optional[int]:
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            match = re.search(r"\b(\d+)\b", value)
            if match:
                return int(match.group(1))
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
            property_id = identifier.get("propertyID")
            if isinstance(property_id, str) and property_id.lower() == "doi":
                value = identifier.get("value") or value
            identifier_type = identifier.get("type")
            if isinstance(identifier_type, str) and identifier_type.lower() == "doi":
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
