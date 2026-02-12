"""Wanfang Data crawler using web scraping."""

from __future__ import annotations

import base64
import logging
import re
import urllib.parse
from typing import Any, Optional

import httpx
from bs4 import BeautifulSoup

from refminer.crawler.base import BaseCrawler
from refminer.crawler.models import SearchQuery, SearchResult

logger = logging.getLogger(__name__)


class BlockedBySiteError(RuntimeError):
    pass


class WanfangCrawler(BaseCrawler):
    """Wanfang Data crawler using web scraping."""

    MAX_PAGES = 5
    ENRICH_LIMIT = 10
    BLOCKED_MARKERS = (
        "浏览器版本过低",
        "Safari",
        "建议升级您的浏览器",
        "检测到您正在使用",
        "万方数据知识服务平台",
    )
    GRPC_SEARCH_URL = "https://s.wanfangdata.com.cn/SearchService.SearchService/search"
    GRPC_PAGE_SIZE = 20

    @property
    def name(self) -> str:
        return "wanfang"

    @property
    def base_url(self) -> str:
        return "https://s.wanfangdata.com.cn"

    def _get_headers(self) -> dict[str, str]:
        headers = super()._get_headers()
        headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/132.0.0.0 Safari/537.36"
                ),
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,image/apng,*/*;q=0.8,"
                    "application/signed-exchange;v=b3;q=0.7"
                ),
                "Accept-Encoding": "gzip, deflate, br",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "sec-ch-ua": '"Not A(Brand";v="8", "Chromium";v="132", "Google Chrome";v="132"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "Referer": "https://s.wanfangdata.com.cn/",
                "Origin": "https://s.wanfangdata.com.cn",
            }
        )
        return headers

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        """Search Wanfang for papers."""
        try:
            await self._warmup_session()
            grpc_results = await self._search_grpc(query)
            if grpc_results:
                logger.info(f"[{self.name}] Found {len(grpc_results)} results via grpc")
                return grpc_results
            html_results = await self._search_html(query)
            logger.info(f"[{self.name}] Found {len(html_results)} results")
            return html_results
        except BlockedBySiteError:
            raise
        except Exception as e:
            logger.error(f"[{self.name}] Search failed: {e}", exc_info=True)
        return []

    async def _search_grpc(self, query: SearchQuery) -> list[SearchResult]:
        results: list[SearchResult] = []
        seen: set[str] = set()

        try:
            current_page = 1
            while current_page <= self.MAX_PAGES and self._should_continue(results, query.max_results):
                response = await self._grpc_search_page(query, current_page)
                count, page_results = self._parse_grpc_search_response(response.content, query)
                if not page_results:
                    break
                self._extend_results(results, seen, page_results, query.max_results)
                if count > 0 and len(results) >= count:
                    break
                current_page += 1
            return results
        except Exception as exc:
            logger.debug(f"[{self.name}] grpc search failed, falling back to html: {exc}")
            return []

    async def _search_html(self, query: SearchQuery) -> list[SearchResult]:
        results: list[SearchResult] = []
        seen: set[str] = set()
        current_page = 1
        while current_page <= self.MAX_PAGES and self._should_continue(results, query.max_results):
            page_url = self._build_search_url(query, current_page)
            response = await self._fetch(page_url)
            html_text = self._decode_response(response)
            self._raise_if_blocked_interstitial(html_text)
            page_results = self._parse_results(html_text, query)
            if not page_results:
                break
            self._extend_results(results, seen, page_results, query.max_results)
            current_page += 1

        if results:
            await self._enrich_results(results, query)
        return results

    async def _grpc_search_page(self, query: SearchQuery, current_page: int) -> httpx.Response:
        await self.rate_limiter.acquire()
        client = await self._get_client()
        message = self._build_grpc_search_request_message(query.query, current_page, self.GRPC_PAGE_SIZE)
        framed_body = b"\x00" + len(message).to_bytes(4, "big") + message
        headers = self._build_grpc_headers(client)
        response = await client.post(self.GRPC_SEARCH_URL, content=framed_body, headers=headers)
        response.raise_for_status()
        grpc_status = response.headers.get("grpc-status")
        if grpc_status and grpc_status != "0":
            grpc_message = response.headers.get("grpc-message", "")
            raise RuntimeError(f"grpc-status={grpc_status} grpc-message={grpc_message}")
        return response

    def _build_grpc_headers(self, client: httpx.AsyncClient) -> dict[str, str]:
        cookies = self._cookie_header(client)
        return {
            "Accept": "*/*",
            "Content-Type": "application/grpc-web+proto",
            "X-Grpc-Web": "1",
            "X-User-Agent": "grpc-web-javascript/0.1",
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/",
            "httphost": "s.wanfangdata.com.cn",
            "httpreferer": f"{self.base_url}/",
            "Cookies": cookies,
        }

    def _cookie_header(self, client: httpx.AsyncClient) -> str:
        pairs = [f"{name}={value}" for name, value in client.cookies.items()]
        return "; ".join(pairs)

    def _build_grpc_search_request_message(
        self, search_word: str, current_page: int, page_size: int
    ) -> bytes:
        common_parts = [
            self._encode_length_delimited_field(1, self._encode_utf8("paper")),
            self._encode_length_delimited_field(2, self._encode_utf8(search_word)),
            self._encode_varint_field(5, current_page),
            self._encode_varint_field(6, page_size),
            self._encode_varint_field(7, 0),
            self._encode_length_delimited_field(8, self._encode_packed_varints([0])),
            self._encode_varint_field(9, 1),
        ]
        common_request = b"".join(common_parts)
        request_parts = [
            self._encode_length_delimited_field(1, common_request),
            self._encode_varint_field(2, 0),
        ]
        return b"".join(request_parts)

    def _parse_grpc_search_response(
        self, response_body: bytes, query: SearchQuery
    ) -> tuple[int, list[SearchResult]]:
        count = 0
        results: list[SearchResult] = []
        for frame_type, payload in self._parse_grpc_web_frames(response_body):
            if frame_type != 0x00:
                continue
            count, resources = self._decode_search_response_message(payload)
            for resource in resources:
                parsed = self._resource_to_search_result(resource, query)
                if parsed:
                    results.append(parsed)
        return count, results

    def _parse_grpc_web_frames(self, body: bytes) -> list[tuple[int, bytes]]:
        if not body:
            return []
        if body.startswith(b"AAAA"):
            body = base64.b64decode(body)

        frames: list[tuple[int, bytes]] = []
        offset = 0
        body_len = len(body)
        while offset + 5 <= body_len:
            frame_type = body[offset]
            size = int.from_bytes(body[offset + 1 : offset + 5], "big")
            offset += 5
            if offset + size > body_len:
                break
            payload = body[offset : offset + size]
            offset += size
            frames.append((frame_type, payload))
        return frames

    def _decode_search_response_message(self, payload: bytes) -> tuple[int, list[dict[str, Any]]]:
        count = 0
        resources: list[dict[str, Any]] = []
        fields = self._decode_wire_fields(payload)
        status = self._first_varint(fields, 1)
        if status == 0:
            message = self._first_string(fields, 2)
            raise RuntimeError(message or "wanfang grpc returned status=false")
        maybe_count = self._first_varint(fields, 3)
        if maybe_count is not None:
            count = maybe_count
        for raw_resource in self._length_delimited_values(fields, 4):
            resources.append(self._decode_resource(raw_resource))
        return count, resources

    def _decode_resource(self, payload: bytes) -> dict[str, Any]:
        fields = self._decode_wire_fields(payload)
        periodical_data: dict[str, Any] = {}
        periodical_raw = self._first_length_delimited(fields, 101)
        if periodical_raw is not None:
            periodical_data = self._decode_periodical(periodical_raw)
        return {
            "type": self._first_string(fields, 1),
            "uid": self._first_string(fields, 3),
            "periodical": periodical_data,
        }

    def _decode_periodical(self, payload: bytes) -> dict[str, Any]:
        fields = self._decode_wire_fields(payload)
        return {
            "title": self._string_values(fields, 2),
            "creator": self._string_values(fields, 3),
            "abstract": self._string_values(fields, 20),
            "publishyear": self._first_varint(fields, 33),
            "doi": self._first_string(fields, 41),
            "fulltextpath": self._first_string(fields, 40),
            "hasfulltext": self._first_varint(fields, 32),
        }

    def _resource_to_search_result(
        self, resource: dict[str, Any], query: SearchQuery
    ) -> Optional[SearchResult]:
        uid = self._normalize_text(resource.get("uid"))
        periodical = resource.get("periodical")
        if not isinstance(periodical, dict):
            return None

        titles = periodical.get("title")
        authors = periodical.get("creator")
        abstracts = periodical.get("abstract")
        year = periodical.get("publishyear")
        doi = periodical.get("doi")
        fulltext_path = periodical.get("fulltextpath")
        has_fulltext = periodical.get("hasfulltext")

        title = self._first_non_empty_str(titles)
        if title:
            title = self._strip_html_text(title)
        if not title or not uid:
            return None

        year_int: Optional[int] = None
        if isinstance(year, int):
            year_int = year
        if year_int is not None:
            if query.year_from and year_int < query.year_from:
                return None
            if query.year_to and year_int > query.year_to:
                return None

        abstract: Optional[str] = None
        if query.include_abstract:
            abstract = self._first_non_empty_str(abstracts)
            if abstract:
                abstract = self._strip_html_text(abstract)

        author_list = []
        if isinstance(authors, list):
            author_list = [
                self._strip_html_text(a)
                for a in authors
                if isinstance(a, str) and a.strip()
            ]

        detail_url = urllib.parse.urljoin(self.base_url, f"/periodical/{uid}")
        pdf_url: Optional[str] = None
        if has_fulltext and isinstance(fulltext_path, str) and fulltext_path.strip():
            pdf_url = urllib.parse.urljoin(self.base_url, fulltext_path)

        metadata = {"wanfang_id": uid}
        return SearchResult(
            title=title,
            authors=author_list,
            year=year_int,
            doi=self._normalize_doi(doi),
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

    def _strip_html_text(self, text: str) -> str:
        stripped = re.sub(r"<[^>]+>", "", text)
        stripped = re.sub(r"\s+", " ", stripped)
        return stripped.strip()

    def _first_non_empty_str(self, value: Any) -> Optional[str]:
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.strip():
                    return item.strip()
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    def _decode_wire_fields(self, payload: bytes) -> dict[int, list[tuple[int, Any]]]:
        fields: dict[int, list[tuple[int, Any]]] = {}
        offset = 0
        while offset < len(payload):
            key, offset = self._decode_varint(payload, offset)
            field_number = key >> 3
            wire_type = key & 0x07
            if wire_type == 0:
                value, offset = self._decode_varint(payload, offset)
            elif wire_type == 2:
                length, offset = self._decode_varint(payload, offset)
                value = payload[offset : offset + length]
                offset += length
            else:
                raise RuntimeError(f"Unsupported wire type: {wire_type}")
            fields.setdefault(field_number, []).append((wire_type, value))
        return fields

    def _first_varint(
        self, fields: dict[int, list[tuple[int, Any]]], field_number: int
    ) -> Optional[int]:
        for wire_type, value in fields.get(field_number, []):
            if wire_type == 0 and isinstance(value, int):
                return value
        return None

    def _first_string(
        self, fields: dict[int, list[tuple[int, Any]]], field_number: int
    ) -> Optional[str]:
        raw = self._first_length_delimited(fields, field_number)
        if raw is None:
            return None
        try:
            decoded = raw.decode("utf-8", errors="ignore").strip()
        except Exception:
            return None
        return decoded or None

    def _first_length_delimited(
        self, fields: dict[int, list[tuple[int, Any]]], field_number: int
    ) -> Optional[bytes]:
        for wire_type, value in fields.get(field_number, []):
            if wire_type == 2 and isinstance(value, bytes):
                return value
        return None

    def _string_values(
        self, fields: dict[int, list[tuple[int, Any]]], field_number: int
    ) -> list[str]:
        values: list[str] = []
        for raw in self._length_delimited_values(fields, field_number):
            try:
                decoded = raw.decode("utf-8", errors="ignore").strip()
            except Exception:
                continue
            if decoded:
                values.append(decoded)
        return values

    def _length_delimited_values(
        self, fields: dict[int, list[tuple[int, Any]]], field_number: int
    ) -> list[bytes]:
        values: list[bytes] = []
        for wire_type, value in fields.get(field_number, []):
            if wire_type == 2 and isinstance(value, bytes):
                values.append(value)
        return values

    def _encode_varint_field(self, field_number: int, value: int) -> bytes:
        key = (field_number << 3) | 0
        return self._encode_varint(key) + self._encode_varint(value)

    def _encode_length_delimited_field(self, field_number: int, data: bytes) -> bytes:
        key = (field_number << 3) | 2
        return self._encode_varint(key) + self._encode_varint(len(data)) + data

    def _encode_utf8(self, value: str) -> bytes:
        return value.encode("utf-8")

    def _encode_packed_varints(self, values: list[int]) -> bytes:
        return b"".join(self._encode_varint(v) for v in values)

    def _encode_varint(self, value: int) -> bytes:
        if value < 0:
            raise ValueError("Negative varint is not supported")
        encoded = bytearray()
        current = value
        while True:
            to_write = current & 0x7F
            current >>= 7
            if current:
                encoded.append(to_write | 0x80)
            else:
                encoded.append(to_write)
                break
        return bytes(encoded)

    def _decode_varint(self, data: bytes, offset: int) -> tuple[int, int]:
        shift = 0
        result = 0
        pos = offset
        while pos < len(data):
            byte = data[pos]
            pos += 1
            result |= (byte & 0x7F) << shift
            if (byte & 0x80) == 0:
                return result, pos
            shift += 7
            if shift >= 64:
                break
        raise RuntimeError("Invalid varint payload")

    async def _warmup_session(self) -> None:
        try:
            await self._fetch(self.base_url)
        except Exception as exc:
            logger.debug(f"[{self.name}] Warmup request failed: {exc}")

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
        self._raise_if_blocked_interstitial(html_text)
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

    def _raise_if_blocked_interstitial(self, html_text: str) -> None:
        for marker in self.BLOCKED_MARKERS:
            if marker in html_text:
                raise BlockedBySiteError(
                    f"Wanfang blocked/interstitial page detected: {marker}"
                )

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
