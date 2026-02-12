"""CNKI crawler using web scraping."""

from __future__ import annotations

import asyncio
import logging
import re
import urllib.parse
from typing import Any, Optional

import httpx
from bs4 import BeautifulSoup

from refminer.crawler.base import BaseCrawler
from refminer.crawler.models import EngineConfig, SearchQuery, SearchResult

logger = logging.getLogger(__name__)


class CnkiCrawler(BaseCrawler):
    """CNKI crawler using web scraping of the public search interface."""

    MAX_PAGES = 3
    RESULTS_PER_PAGE = 20
    ENRICH_LIMIT = 20

    def __init__(
        self,
        config: Optional[EngineConfig] = None,
        auth_profile: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(config, auth_profile)
        self._session_warmed = False

    @property
    def name(self) -> str:
        return "cnki"

    @property
    def base_url(self) -> str:
        return "https://kns.cnki.net"

    @property
    def requires_api_key(self) -> bool:
        return False

    def _get_headers(self) -> dict[str, str]:
        """Get headers for CNKI requests."""
        headers = super()._get_headers()
        headers.update(
            {
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Referer": "https://kns.cnki.net/kns8/defaultresult/index",
                "Origin": "https://kns.cnki.net",
            }
        )
        return headers

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        """Search CNKI for papers via web scraping."""
        results: list[SearchResult] = []
        seen: set[str] = set()

        try:
            # First establish a search session
            search_sql, query_id = await self._init_search(query)
            if not search_sql and not query_id:
                logger.warning(f"[{self.name}] Failed to initialize search session")
                return []

            # Fetch first page of results
            page_results = await self._fetch_results_page(
                search_sql, query_id, 1, query
            )
            self._extend_results(results, seen, page_results, query.max_results)

            # Fetch additional pages if needed
            current_page = 1
            while (
                current_page < self.MAX_PAGES
                and self._should_continue(results, query.max_results)
                and len(page_results) >= self.RESULTS_PER_PAGE
            ):
                current_page += 1
                page_results = await self._fetch_results_page(
                    search_sql, query_id, current_page, query
                )
                if not page_results:
                    break
                self._extend_results(results, seen, page_results, query.max_results)

            # Enrich results with detail page data
            if results:
                await self._enrich_results(results, query)

            logger.info(f"[{self.name}] Found {len(results)} results")
        except Exception as e:
            logger.error(f"[{self.name}] Search failed: {e}", exc_info=True)

        return results

    async def _init_search(
        self, query: SearchQuery
    ) -> tuple[Optional[str], Optional[str]]:
        """Initialize a search session and get the search SQL and query ID."""
        await self.rate_limiter.acquire()
        client = await self._get_client()

        await self._warmup_session(client)

        # Build search parameters
        search_params = self._build_search_params(query)

        url = urllib.parse.urljoin(self.base_url, "/kns8/Brief/GetGridTableHtml")
        headers = self._get_headers()
        headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        headers["X-Requested-With"] = "XMLHttpRequest"

        try:
            payload = await self._post_form_for_html(
                client, url, search_params, headers
            )
            if not payload:
                logger.warning(f"[{self.name}] Init search failed: empty response")
                return None, None

            html = self._extract_html_payload(payload)

            # Extract search SQL from the response for pagination
            search_sql = self._extract_search_sql(payload) or self._extract_search_sql(
                html
            )
            query_id = (
                self._extract_query_id(payload)
                or self._extract_query_id(html)
                or search_params.get("QueryID", "")
            )

            if not search_sql:
                logger.debug(
                    f"[{self.name}] SearchSql not found. Payload head: {payload[:200]!r}"
                )

            return search_sql, query_id
        except Exception as e:
            logger.warning(f"[{self.name}] Init search failed: {e}")
            return None, None

    def _build_search_params(self, query: SearchQuery) -> dict[str, str]:
        """Build search parameters for CNKI API."""
        # Use theme/keyword search across all fields
        search_term = query.query.strip()

        params = {
            "IsSearch": "true",
            "QueryJson": self._build_query_json(search_term, query),
            "PageName": "defaultresult",
            "DBCode": "CFLS",  # All databases
            "KuaKuCode": "CJFQ,CDMD,CIPD,CCND,CISD,SNAD,BDZK,CCJD,CCVD,CJFN",
            "CurPage": "1",
            "RecordsCntPerPage": str(self.RESULTS_PER_PAGE),
            "CurDisplayMode": "listmode",
            "CurrSortField": "",
            "CurrSortFieldType": "desc",
            "IsSentenceSearch": "false",
            "Subject": "",
            "DisplayMode": "listmode",
            "QueryID": "0",
        }

        return params

    def _build_query_json(self, search_term: str, query: SearchQuery) -> str:
        """Build the QueryJson parameter for CNKI search."""
        import json

        query_group = {
            "Platform": "",
            "DBCode": "CFLS",
            "KuaKuCode": "CJFQ,CDMD,CIPD,CCND,CISD,SNAD,BDZK,CCJD,CCVD,CJFN",
            "QNode": {
                "QGroup": [
                    {
                        "Key": "Subject",
                        "Title": "",
                        "Logic": 0,
                        "Items": [
                            {
                                "Key": "input[data-tipid=gra498-1]",
                                "Title": "主题",
                                "Logic": 0,
                                "Name": "SU",
                                "Operate": "%=",
                                "Value": search_term,
                                "ExtendType": 0,
                                "ExtendValue": "",
                                "Value2": "",
                            }
                        ],
                        "ChildItems": [],
                    }
                ]
            },
        }

        # Add year filter if specified
        if query.year_from or query.year_to:
            year_from = query.year_from or 1900
            year_to = query.year_to or 2099
            query_group["QNode"]["QGroup"].append(
                {
                    "Key": "ControlGroup",
                    "Title": "",
                    "Logic": 1,
                    "Items": [],
                    "ChildItems": [
                        {
                            "Key": "Year",
                            "Title": "发表时间",
                            "Logic": 0,
                            "Items": [
                                {
                                    "Key": "Year",
                                    "Title": "发表时间",
                                    "Logic": 0,
                                    "Name": "Year",
                                    "Operate": "between",
                                    "Value": f"{year_from}-{year_to}",
                                    "ExtendType": 0,
                                    "ExtendValue": "",
                                    "Value2": "",
                                }
                            ],
                            "ChildItems": [],
                        }
                    ],
                }
            )

        return json.dumps(query_group, ensure_ascii=False)

    async def _fetch_results_page(
        self,
        search_sql: Optional[str],
        query_id: Optional[str],
        page: int,
        query: SearchQuery,
    ) -> list[SearchResult]:
        """Fetch a page of search results."""
        await self.rate_limiter.acquire()
        client = await self._get_client()

        params = {
            "IsSearch": "false" if page > 1 else "true",
            "QueryJson": self._build_query_json(query.query, query),
            "PageName": "defaultresult",
            "DBCode": "CFLS",
            "KuaKuCode": "CJFQ,CDMD,CIPD,CCND,CISD,SNAD,BDZK,CCJD,CCVD,CJFN",
            "CurPage": str(page),
            "RecordsCntPerPage": str(self.RESULTS_PER_PAGE),
            "CurDisplayMode": "listmode",
            "CurrSortField": "",
            "CurrSortFieldType": "desc",
            "IsSentenceSearch": "false",
            "Subject": "",
            "DisplayMode": "listmode",
            "QueryID": query_id or "0",
        }

        if search_sql:
            params["SearchSql"] = search_sql

        url = urllib.parse.urljoin(self.base_url, "/kns8/Brief/GetGridTableHtml")
        headers = self._get_headers()
        headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        headers["X-Requested-With"] = "XMLHttpRequest"

        try:
            html = await self._post_form_for_html(client, url, params, headers)
            if not html:
                logger.warning(
                    f"[{self.name}] Failed to fetch page {page}: empty response"
                )
                return []
            html = self._extract_html_payload(html)
            return self._parse_results(html, query)
        except Exception as e:
            logger.warning(f"[{self.name}] Failed to fetch page {page}: {e}")
            return []

    async def _post_form_for_html(
        self,
        client: httpx.AsyncClient,
        url: str,
        data: dict[str, str],
        headers: dict[str, str],
    ) -> Optional[str]:
        """POST a form request with retries and return decoded HTML."""
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries):
            try:
                response = await client.post(url, data=data, headers=headers)
                response.raise_for_status()
                await response.aread()
                return self._decode_response(response)
            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(
                    f"[{self.name}] HTTP error on attempt {attempt + 1}: {e.response.status_code}"
                )
                if e.response.status_code in {429, 503, 504}:
                    await asyncio.sleep(2**attempt)
                else:
                    break
            except (
                httpx.RequestError,
                httpx.RemoteProtocolError,
                asyncio.TimeoutError,
            ) as e:
                last_error = e
                logger.warning(
                    f"[{self.name}] Request error on attempt {attempt + 1}: {e}"
                )
                await asyncio.sleep(2**attempt)

        if last_error:
            logger.warning(f"[{self.name}] Request failed: {last_error}")
        return None

    def _extract_search_sql(self, html: str) -> Optional[str]:
        """Extract SearchSql parameter from response for pagination."""
        match = re.search(r'var\s+SearchSql\s*=\s*["\']([^"\']+)["\']', html)
        if match:
            return match.group(1)
        match = re.search(r'["\']SearchSql["\']\s*[:=]\s*["\']([^"\']+)["\']', html)
        if match:
            return match.group(1)
        match = re.search(r'name=["\']SearchSql["\']\s+value=["\']([^"\']+)["\']', html)
        if match:
            return match.group(1)
        return None

    def _extract_query_id(self, html: str) -> Optional[str]:
        """Extract QueryID parameter from response for pagination."""
        match = re.search(r'QueryID\s*[=:]\s*["\']?(\d+)["\']?', html)
        if match:
            return match.group(1)
        match = re.search(r'name=["\']QueryID["\']\s+value=["\'](\d+)["\']', html)
        if match:
            return match.group(1)
        return None

    def _extract_html_payload(self, payload: str) -> str:
        """Extract embedded HTML when response is JSON-like."""
        trimmed = payload.lstrip()
        if not trimmed.startswith("{"):
            return payload

        try:
            import json

            data = json.loads(payload)
        except Exception:
            return payload

        for key in ("Html", "HTML", "html", "content", "data"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return payload

    def _decode_response(self, response: httpx.Response) -> str:
        """Decode response with fallback encodings."""
        if response.encoding is None:
            response.encoding = "utf-8"
        text = response.text
        if "\ufffd" not in text:
            return text

        for encoding in ("utf-8", "gb18030", "gbk", "gb2312"):
            try:
                decoded = response.content.decode(encoding)
            except UnicodeDecodeError:
                continue
            if "\ufffd" not in decoded:
                return decoded
            text = decoded
        return text

    def _parse_results(self, html: str, query: SearchQuery) -> list[SearchResult]:
        """Parse search results from HTML."""
        soup = BeautifulSoup(html, "html.parser")
        results: list[SearchResult] = []

        # Find result items - CNKI uses table rows
        rows = soup.select("table.result-table-list tbody tr")
        if not rows:
            # Try alternate selector
            rows = soup.select(".result-list tr")
        if not rows:
            # Try finding any links to article detail pages
            rows = soup.select("tr[data-dbcode], tr[data-filename]")
        if not rows:
            rows = [
                row
                for row in soup.select("table tbody tr, tr")
                if row.select_one("a.fz14") or row.select_one("a[href*='Detail']")
            ]

        for row in rows:
            try:
                result = self._parse_result_row(row, query)
                if result:
                    results.append(result)
            except Exception as e:
                logger.debug(f"[{self.name}] Failed to parse row: {e}")

        if not results:
            for link in soup.select("a.fz14"):
                result = self._parse_result_link(link, query)
                if result:
                    results.append(result)

        return results

    def _parse_result_row(self, row: Any, query: SearchQuery) -> Optional[SearchResult]:
        """Parse a single result row."""
        # Extract title and URL
        title_link = row.select_one("td.name a.fz14")
        if not title_link:
            title_link = row.select_one("a.fz14")
        if not title_link:
            title_link = row.select_one("td.name a")
        if not title_link:
            return None

        title = self._normalize_text(title_link.get_text(" ", strip=True))
        if not title:
            return None

        # Build detail URL
        href = title_link.get("href", "")
        if href:
            detail_url = urllib.parse.urljoin(self.base_url, href)
        else:
            detail_url = None

        detail_metadata = self._extract_metadata_from_url(detail_url)

        # Extract authors
        authors = self._extract_authors(row)

        # Extract journal/source
        journal = self._extract_journal(row)

        # Extract year
        year = self._extract_year(row)
        if year is not None:
            if query.year_from and year < query.year_from:
                return None
            if query.year_to and year > query.year_to:
                return None

        # Extract database code for metadata
        db_code = row.get("data-dbcode", "")
        metadata = {}
        if db_code:
            metadata["db_code"] = db_code

        db_name = row.get("data-dbname", "")
        if db_name:
            metadata["db_name"] = db_name

        # Extract filename for constructing download URL
        filename = self._extract_filename(row)
        if filename:
            metadata["filename"] = filename

        for key in ("db_code", "db_name", "filename"):
            detail_value = detail_metadata.get(key)
            if detail_value:
                metadata[key] = detail_value

        pdf_url = self._extract_pdf_link(row)
        if not pdf_url:
            pdf_url = self._build_pdf_url(metadata)
        pdf_metadata = self._extract_metadata_from_url(pdf_url)
        for key, value in pdf_metadata.items():
            if key == "tablename":
                metadata.setdefault(key, value)
            elif key not in metadata and value:
                metadata[key] = value

        return SearchResult(
            title=title,
            authors=authors,
            year=year,
            doi=None,
            abstract=None,  # Will be enriched later
            source=self.name,
            url=detail_url,
            pdf_url=pdf_url,
            journal=journal,
            volume=None,
            issue=None,
            pages=None,
            citation_count=self._extract_citation_count(row),
            metadata=metadata,
        )

    def _parse_result_link(
        self, link: Any, query: SearchQuery
    ) -> Optional[SearchResult]:
        """Parse a minimal result from a title link."""
        title = self._normalize_text(link.get_text(" ", strip=True))
        if not title:
            return None

        href = link.get("href", "")
        detail_url = urllib.parse.urljoin(self.base_url, href) if href else None

        return SearchResult(
            title=title,
            authors=[],
            year=None,
            doi=None,
            abstract=None,
            source=self.name,
            url=detail_url,
            pdf_url=None,
            journal=None,
            volume=None,
            issue=None,
            pages=None,
            citation_count=None,
            metadata={},
        )

    async def _warmup_session(self, client: httpx.AsyncClient) -> None:
        """Warm up session cookies for CNKI."""
        if self._session_warmed:
            return

        url = urllib.parse.urljoin(self.base_url, "/kns8/defaultresult/index")
        headers = self._get_headers()
        headers["Referer"] = "https://kns.cnki.net"
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            self._session_warmed = True
        except Exception as e:
            logger.debug(f"[{self.name}] Session warmup failed: {e}")

    def _extract_authors(self, row: Any) -> list[str]:
        """Extract authors from result row."""
        authors: list[str] = []

        # Try author cell
        author_cell = row.select_one("td.author")
        if author_cell:
            for link in author_cell.select("a"):
                name = self._normalize_text(link.get_text(" ", strip=True))
                if name:
                    authors.append(name)

        if not authors:
            # Try alternate selector
            for link in row.select("a[href*='author']"):
                name = self._normalize_text(link.get_text(" ", strip=True))
                if name and len(name) < 20:  # Filter out non-author links
                    authors.append(name)

        return authors

    def _extract_journal(self, row: Any) -> Optional[str]:
        """Extract journal/source name."""
        source_cell = row.select_one("td.source")
        if source_cell:
            link = source_cell.select_one("a")
            if link:
                return self._normalize_text(link.get_text(" ", strip=True))
            return self._normalize_text(source_cell.get_text(" ", strip=True))
        return None

    def _extract_year(self, row: Any) -> Optional[int]:
        """Extract publication year."""
        date_cell = row.select_one("td.date")
        if date_cell:
            text = date_cell.get_text(" ", strip=True)
            match = re.search(r"\b(19\d{2}|20\d{2})\b", text)
            if match:
                return int(match.group(1))

        # Try to find year in row text
        text = row.get_text(" ", strip=True)
        match = re.search(r"\b(19\d{2}|20\d{2})\b", text)
        if match:
            return int(match.group(1))

        return None

    def _extract_citation_count(self, row: Any) -> Optional[int]:
        """Extract citation count if available."""
        cite_cell = row.select_one("td.quote")
        if cite_cell:
            text = cite_cell.get_text(" ", strip=True)
            if text.isdigit():
                return int(text)
        return None

    def _extract_filename(self, row: Any) -> Optional[str]:
        """Extract CNKI filename for article identification."""
        # Try data attribute
        filename = row.get("data-filename")
        if filename:
            return filename

        # Try from link href
        link = row.select_one("a.fz14")
        if link:
            href = link.get("href", "")
            match = re.search(r"filename=([^&]+)", href)
            if match:
                return match.group(1)
            match = re.search(r"FileName=([^&]+)", href)
            if match:
                return match.group(1)

        return None

    def _normalize_text(self, value: Any) -> Optional[str]:
        """Normalize text value."""
        if isinstance(value, str):
            # Remove extra whitespace and normalize
            cleaned = re.sub(r"\s+", " ", value.strip())
            return cleaned or None
        return None

    def _extend_results(
        self,
        results: list[SearchResult],
        seen: set[str],
        page_results: list[SearchResult],
        max_results: int,
    ) -> None:
        """Add new results avoiding duplicates."""
        for result in page_results:
            result_key = result.get_hash()
            if result_key in seen:
                continue
            seen.add(result_key)
            results.append(result)
            if max_results > 0 and len(results) >= max_results:
                break

    def _should_continue(self, results: list[SearchResult], max_results: int) -> bool:
        """Check if we should fetch more pages."""
        return max_results <= 0 or len(results) < max_results

    async def _enrich_results(
        self, results: list[SearchResult], query: SearchQuery
    ) -> None:
        """Enrich results with data from detail pages."""
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
            needs_authors = not result.authors
            if not (needs_abstract or needs_doi or needs_authors):
                continue

            try:
                response = await self._fetch(result.url)
            except Exception as e:
                logger.debug(f"[{self.name}] Detail fetch failed for {result.url}: {e}")
                continue

            soup = BeautifulSoup(self._decode_response(response), "html.parser")
            detail = self._extract_detail_data(soup)

            if needs_abstract and detail.get("abstract"):
                result.abstract = detail["abstract"]
            if needs_doi and detail.get("doi"):
                result.doi = detail["doi"]
            if needs_authors and detail.get("authors"):
                result.authors = detail["authors"]
            if not result.journal and detail.get("journal"):
                result.journal = detail["journal"]
            for key in ("db_code", "db_name", "filename"):
                value = detail.get(key)
                if value and key not in result.metadata:
                    result.metadata[key] = value
            if not result.pdf_url and detail.get("pdf_url"):
                result.pdf_url = detail["pdf_url"]
            if not result.pdf_url:
                pdf_url = self._build_pdf_url(result.metadata)
                if pdf_url:
                    result.pdf_url = pdf_url

    def _extract_detail_data(self, soup: BeautifulSoup) -> dict[str, Any]:
        """Extract data from article detail page."""
        detail_metadata = self._extract_detail_metadata(soup)
        return {
            "abstract": self._extract_detail_abstract(soup),
            "doi": self._extract_detail_doi(soup),
            "authors": self._extract_detail_authors(soup),
            "journal": self._extract_detail_journal(soup),
            "pdf_url": self._extract_detail_pdf_url(soup),
            **detail_metadata,
        }

    def _extract_detail_abstract(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract abstract from detail page."""
        # Try the abstract section
        abstract_div = soup.select_one("#ChDivSummary")
        if abstract_div:
            text = abstract_div.get_text(" ", strip=True)
            if text:
                return text

        # Try alternate selectors
        for selector in [".abstract-text", ".summary", "div[id*='abstract']"]:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(" ", strip=True)
                if text and len(text) > 50:
                    return text

        # Try finding by label
        for label in soup.find_all(["span", "label", "b"]):
            label_text = label.string
            if not label_text or not re.search(r"摘要|Abstract", str(label_text)):
                continue

            parent = label.parent
            if parent:
                text = parent.get_text(" ", strip=True)
                # Remove the label
                text = re.sub(r"^(摘要|Abstract)[：:\s]*", "", text)
                if text and len(text) > 50:
                    return text

        return None

    def _extract_detail_doi(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract DOI from detail page."""
        # Look for DOI link
        for link in soup.select("a[href*='doi.org']"):
            href = link.get("href")
            doi = self._parse_doi(str(href) if href else None)
            if doi:
                return doi

        # Look for DOI text
        for elem in soup.find_all(string=re.compile(r"10\.\d{4,}")):
            text = str(elem)
            match = re.search(r"(10\.\d{4,}/[^\s<>\"]+)", text)
            if match:
                return match.group(1).rstrip(".,;")

        return None

    def _parse_doi(self, value: Optional[str]) -> Optional[str]:
        """Parse DOI from URL or text."""
        if not value:
            return None
        # Remove common prefixes
        for prefix in [
            "https://doi.org/",
            "http://doi.org/",
            "https://dx.doi.org/",
            "http://dx.doi.org/",
            "doi:",
            "DOI:",
        ]:
            if value.startswith(prefix):
                value = value[len(prefix) :]
        # Validate DOI format
        if re.match(r"10\.\d{4,}/", value):
            return value.rstrip(".,;")
        return None

    def _extract_detail_authors(self, soup: BeautifulSoup) -> list[str]:
        """Extract authors from detail page."""
        authors: list[str] = []

        # Try author section
        author_div = soup.select_one("#authorpart")
        if author_div:
            for link in author_div.select("a"):
                name = self._normalize_text(link.get_text(" ", strip=True))
                if name:
                    authors.append(name)

        if not authors:
            # Try alternate selector
            for link in soup.select(".author a"):
                name = self._normalize_text(link.get_text(" ", strip=True))
                if name:
                    authors.append(name)

        return authors

    def _extract_detail_journal(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract journal name from detail page."""
        # Try journal link
        journal_link = soup.select_one("a.KnsLian, a.journal")
        if journal_link:
            return self._normalize_text(journal_link.get_text(" ", strip=True))

        # Try publication info section
        pub_info = soup.select_one(".top-tip")
        if pub_info:
            text = pub_info.get_text(" ", strip=True)
            # Usually format is "Journal Name, Year, Volume(Issue): Pages"
            match = re.match(r"^([^,]+)", text)
            if match:
                return self._normalize_text(match.group(1))

        return None

    def _extract_detail_metadata(self, soup: BeautifulSoup) -> dict[str, str]:
        """Extract hidden metadata fields from detail page."""
        metadata: dict[str, str] = {}
        for key, input_id in (
            ("db_code", "param-dbcode"),
            ("db_name", "param-dbname"),
            ("filename", "param-filename"),
        ):
            elem = soup.select_one(f"input#{input_id}")
            if not elem:
                continue
            value = elem.get("value")
            if isinstance(value, str) and value.strip():
                metadata[key] = value.strip()
        return metadata

    def _extract_detail_pdf_url(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract PDF download URL from detail page."""
        for selector in [
            "meta[name='citation_pdf_url']",
            "meta[property='citation_pdf_url']",
        ]:
            meta = soup.select_one(selector)
            if meta:
                content = meta.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()

        for selector in [
            "#pdfDown",
            "li.btn-download-pdf a",
            "a[href$='.pdf']",
            "a[href*='.pdf?']",
            "a[href*='download']",
            "a[id*='download']",
            "a[class*='download']",
            "a[onclick*='download']",
        ]:
            link = soup.select_one(selector)
            if not link:
                continue
            href_value = link.get("href") or link.get("data-href")
            href = href_value if isinstance(href_value, str) else ""
            if not href:
                continue
            return urllib.parse.urljoin(self.base_url, href)

        for script in soup.find_all("script"):
            script_text = script.string or ""
            if not script_text:
                continue
            match = re.search(r"(https?://[^\"'\s]+\.pdf)", script_text)
            if match:
                return match.group(1)
            match = re.search(r"(https?://[^\"'\s]+download[^\"'\s]+)", script_text)
            if match:
                return match.group(1)
            match = re.search(r"(/kcms2/download[^\"'\s]+)", script_text)
            if match:
                return urllib.parse.urljoin(self.base_url, match.group(1))

        return None

    def _extract_pdf_link(self, row: Any) -> Optional[str]:
        """Extract a PDF link from a result row if available."""
        for selector in [
            "a[href$='.pdf']",
            "a[href*='.pdf?']",
            "a[href*='download']",
        ]:
            link = row.select_one(selector)
            if not link:
                continue
            href_value = link.get("href")
            href = href_value if isinstance(href_value, str) else ""
            if href:
                return urllib.parse.urljoin(self.base_url, href)
        return None

    def _extract_metadata_from_url(self, url: Optional[str]) -> dict[str, str]:
        """Extract DB metadata from a URL query string."""
        if not url:
            return {}

        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        normalized = {key.lower(): value for key, value in params.items()}

        def _get_param(name: str) -> str:
            value = normalized.get(name.lower())
            if value:
                return str(value[0])
            return ""

        metadata = {
            "db_code": _get_param("dbcode"),
            "db_name": _get_param("dbname"),
            "filename": _get_param("filename"),
            "tablename": _get_param("tablename"),
        }
        return {key: value for key, value in metadata.items() if value}

    def _build_pdf_url(self, metadata: dict[str, Any]) -> Optional[str]:
        """Build a CNKI PDF download URL from metadata."""
        filename = metadata.get("filename")
        db_code = metadata.get("db_code") or metadata.get("dbcode")
        db_name = metadata.get("db_name") or metadata.get("dbname")

        if not filename or not db_code:
            return None

        base = f"{self.base_url}/kcms2/download"
        params = {"filename": filename, "dbcode": db_code}
        if db_name:
            params["dbname"] = db_name
        return f"{base}?{urllib.parse.urlencode(params)}"
