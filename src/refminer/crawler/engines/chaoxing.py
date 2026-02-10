"""Chaoxing (超星期刊) crawler using web scraping."""

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


class ChaoxingCrawler(BaseCrawler):
    """Chaoxing (超星期刊) crawler using web scraping."""

    MAX_PAGES = 5
    ENRICH_LIMIT = 30

    @property
    def name(self) -> str:
        return "chaoxing"

    @property
    def base_url(self) -> str:
        return "https://qikan.chaoxing.com"

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        """Search Chaoxing for papers."""
        results: list[SearchResult] = []
        seen: set[str] = set()

        try:
            response = await self._post_search(query)
            page_results = self._parse_results(
                self._decode_response(response), query
            )
            self._extend_results(results, seen, page_results, query.max_results)

            current_page = 1
            while (
                current_page < self.MAX_PAGES
                and self._should_continue(results, query.max_results)
            ):
                current_page += 1
                page_url = self._build_paged_url(query, current_page)
                response = await self._fetch(page_url)
                page_results = self._parse_results(
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
        url = urllib.parse.urljoin(self.base_url, "/search")
        data = {
            "sw": query.query,
            "isort": "0",
            "allnum": str(query.max_results),
            "channelkey": "qikan",
            "showmode": "list",
        }
        headers = self._get_headers()
        headers["Accept-Language"] = "zh-CN,zh;q=0.9,en;q=0.5"
        headers["Referer"] = urllib.parse.urljoin(self.base_url, "/")

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
        """Decode response with multi-candidate strategy and mojibake detection.
        
        Tries multiple encodings and scores each for mojibake indicators.
        Returns the candidate with the lowest mojibake score.
        """
        candidates = [
            ("utf-8", "strict"),
            ("utf-8-sig", "strict"),
            ("gb18030", "strict"),
            ("gbk", "strict"),
        ]
        
        results = []
        
        for encoding, errors in candidates:
            try:
                decoded = response.content.decode(encoding, errors=errors)
                score = self._mojibake_score(decoded)
                results.append((score, encoding, decoded))
                has_replacement = "\ufffd" in decoded
                logger.debug(
                    f"[{self.name}] {encoding}: mojibake_score={score:.2f}, "
                    f"length={len(decoded)}, has_replacement={has_replacement}"
                )
            except (UnicodeDecodeError, LookupError) as e:
                logger.debug(f"[{self.name}] {encoding}: decode failed ({type(e).__name__})")
                continue
        
        if not results:
            # All candidates failed - fall back to response.text
            if response.encoding is None:
                response.encoding = "utf-8"
            text = response.text
            score = self._mojibake_score(text)
            logger.warning(
                f"[{self.name}] All decode candidates failed, using response.text "
                f"(mojibake_score={score:.2f})"
            )
            return text
        
        # Sort by score (lower is better) and pick best
        results.sort(key=lambda x: x[0])
        best_score, best_encoding, best_text = results[0]
        
        logger.debug(
            f"[{self.name}] Selected {best_encoding} with mojibake_score={best_score:.2f}"
        )
        
        return best_text
    
    def _mojibake_score(self, text: str) -> float:
        """Score text for mojibake indicators. Lower is better (0 = perfect).
        
        Checks for:
        - Replacement characters (U+FFFD)
        - Latin-1 Supplement chars in CJK context
        - Common mojibake patterns
        """
        if not text:
            return 0.0
        
        score = 0.0
        char_count = len(text)
        if char_count == 0:
            return 0.0
        
        # Strong penalty for replacement characters
        replacement_count = text.count('\ufffd')
        score += replacement_count * 10.0
        
        # Detect suspicious Latin-1 chars in CJK context
        latin1_suspicious = 0
        cjk_count = 0
        
        for char in text:
            code = ord(char)
            # CJK Unified Ideographs (most common Chinese chars)
            if 0x4E00 <= code <= 0x9FFF:
                cjk_count += 1
            # Latin-1 Supplement (0x80-0xFF) - suspicious if in CJK text
            elif 0x80 <= code <= 0xFF:
                latin1_suspicious += 1
        
        # If we have CJK content, penalize Latin-1 Supplement chars
        if cjk_count > 10:  # Likely Chinese content
            latin1_ratio = latin1_suspicious / char_count
            # If >5% Latin-1 Supplement chars, likely mojibake
            if latin1_ratio > 0.05:
                score += latin1_ratio * 100.0
        
        # Common mojibake patterns (GB18030/GBK decoded as Latin-1 or wrong encoding)
        mojibake_patterns = [
            'Â', 'Ã', 'Å', 'Æ', 'È', 'É',  # Common in GB18030 -> Latin-1
            '¿', '½', 'Ð', 'Ñ',  # More mojibake indicators
        ]
        for pattern in mojibake_patterns:
            score += text.count(pattern) * 2.0
        
        return score

    def _parse_results(
        self, html_text: str, query: SearchQuery
    ) -> list[SearchResult]:
        soup = BeautifulSoup(html_text, "html.parser")
        
        # Layered selector fallback for list items
        items = soup.select("ul.list02 li")
        if not items:
            items = soup.select("ul.list li")
        if not items:
            items = soup.select(".list-item")
        if not items:
            items = soup.select(".result-item")

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
        
        if self._is_noise_record(title):
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
        chaoxing_id = self._extract_chaoxing_id(detail_url)
        if chaoxing_id:
            metadata["chaoxing_id"] = chaoxing_id

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
        link = item.select_one("h3 a[href]") if hasattr(item, "select_one") else None
        if not link and hasattr(item, "select_one"):
            link = item.select_one("a[href*='detail']")
        if not link and hasattr(item, "select_one"):
            link = item.select_one(".a-title")
        if not link and hasattr(item, "select_one"):
            link = item.select_one(".title a")

        title = None
        detail_url = None
        if link and hasattr(link, "get"):
            title_text = link.get_text(" ", strip=True)
            title = self._normalize_text(title_text)
            href = link.get("href")
            if isinstance(href, str):
                if href.startswith("/"):
                    detail_url = f"{self.base_url}{href}"
                else:
                    detail_url = href

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
            
            if not authors:
                author_elem = item.select_one(".authors")
                if author_elem:
                    text = self._normalize_text(author_elem.get_text(" ", strip=True))
                    if text:
                        authors = self._split_author_string(text)
            
            if not authors:
                author_elem = item.select_one("[class*='author']")
                if author_elem:
                    text = self._normalize_text(author_elem.get_text(" ", strip=True))
                    if text:
                        authors = self._split_author_string(text)

        if not authors and hasattr(item, "get_text"):
            text = item.get_text(" ", strip=True)
            match = re.search(r"作者[:：]\s*([^\n]+)", text)
            if match:
                authors = self._split_author_string(match.group(1))
            
            if not authors:
                match = re.search(r"([^\n]{2,30})\s*[（(]\d{4}[—\-]\d{0,4}[）)]", text)
                if match:
                    author_text = match.group(1).strip()
                    if author_text and not any(kw in author_text for kw in ["摘要", "关键词", "doi", "DOI"]):
                        authors = self._split_author_string(author_text)

        return [author for author in authors if author and self._is_valid_author(author)]

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
        if not journal_elem:
            journal_elem = item.select_one(".publication")
        if not journal_elem:
            journal_elem = item.select_one("[class*='journal']")
        if not journal_elem:
            journal_elem = item.select_one("[class*='source']")
        if not journal_elem:
            journal_elem = item.select_one("[class*='publication']")
        
        if journal_elem:
            journal = self._normalize_text(journal_elem.get_text(" ", strip=True))
            if journal and self._is_valid_journal(journal):
                return journal
        
        return None

    def _extract_doi(self, item: Any) -> Optional[str]:
        if not hasattr(item, "find_all"):
            return None
        for link in item.find_all("a", href=True):
            href = link.get("href")
            if isinstance(href, str) and "doi.org" in href:
                return self._normalize_doi_doi(href)
        return None

    def _extract_chaoxing_id(self, detail_url: Optional[str]) -> Optional[str]:
        if not detail_url:
            return None
        match = re.search(r"/detail/([A-Za-z0-9\-_]+)", detail_url)
        if match:
            return match.group(1)
        return None

    def _build_paged_url(self, query: SearchQuery, page: int) -> str:
        params = {
            "sw": query.query,
            "isort": "0",
            "allnum": str(query.max_results),
            "page": str(page),
            "channelkey": "qikan",
            "showmode": "list",
        }
        query_str = urllib.parse.urlencode(params)
        return urllib.parse.urljoin(self.base_url, f"/search?{query_str}")

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

    def _normalize_doi_doi(self, value: Any) -> Optional[str]:
        if not isinstance(value, str):
            return None
        cleaned = value.strip()
        cleaned = cleaned.replace("doi:", "").replace("DOI:", "")
        cleaned = cleaned.replace("https://doi.org/", "")
        cleaned = cleaned.replace("http://doi.org/", "")
        cleaned = cleaned.replace("https://dx.doi.org/", "")
        cleaned = cleaned.replace("http://dx.doi.org/", "")
        return cleaned if "/" in cleaned else None
    
    def _is_noise_record(self, title: str) -> bool:
        if len(title) < 5:
            return True
        
        return False
    
    def _is_valid_author(self, author: str) -> bool:
        if len(author) < 2:
            return False
        if len(author) > 100:
            return False
        
        invalid_patterns = [
            "摘要",
            "关键词",
            "abstract",
            "keywords",
            r"^\d+$"
        ]
        
        author_lower = author.lower()
        for pattern in invalid_patterns:
            if re.search(pattern, author_lower):
                return False
        
        return True
    
    def _is_valid_journal(self, journal: str) -> bool:
        if len(journal) < 3:
            return False
        if len(journal) > 100:
            return False
        
        invalid_patterns = [
            r"^\d+$",
            "摘要",
            "关键词",
            "abstract",
            "作者",
            "下载"
        ]
        
        journal_lower = journal.lower()
        for pattern in invalid_patterns:
            if re.search(pattern, journal_lower):
                return False
        
        return True

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
            
            # Skip enrichment if page is login/captcha/interstitial
            if self._is_interstitial_page(soup):
                logger.debug(
                    f"[{self.name}] Skipping enrichment for {result.url}: detected auth/captcha page"
                )
                continue
            
            detail = self._extract_detail_data(soup)

            # Only overwrite with valid, non-empty data
            if needs_abstract and detail.get("abstract") and len(detail["abstract"]) > 10:
                result.abstract = detail["abstract"]
            if needs_doi and detail.get("doi") and self._is_valid_doi(detail["doi"]):
                result.doi = detail["doi"]
            if needs_pdf and detail.get("pdf_url") and self._is_valid_pdf_url(detail["pdf_url"]):
                result.pdf_url = detail["pdf_url"]
            if needs_authors and detail.get("authors") and len(detail["authors"]) > 0:
                result.authors = detail["authors"]
            if needs_year and detail.get("year") and self._is_valid_year(detail["year"]):
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
        for label in soup.find_all("b"):
            if label.string and "摘要" in label.string:
                if label.parent:
                    text = label.parent.get_text(" ", strip=True)
                    if text:
                        return self._strip_label(text, ("摘要", "Abstract"))

        for node in soup.select(".abstract"):
            text = node.get_text(" ", strip=True)
            if text:
                return self._strip_label(text, ("摘要", "Abstract"))
        return None

    def _extract_detail_authors(self, soup: BeautifulSoup) -> list[str]:
        authors: list[str] = []
        
        for link in soup.select(".author a"):
            name = self._normalize_text(link.get_text(" ", strip=True))
            if name and self._is_valid_author(name):
                authors.append(name)
        
        if not authors:
            author_elem = soup.select_one(".author")
            if author_elem:
                text = self._normalize_text(author_elem.get_text(" ", strip=True))
                if text:
                    authors = self._split_author_string(text)
        
        if not authors:
            author_elem = soup.select_one(".authors")
            if author_elem:
                text = self._normalize_text(author_elem.get_text(" ", strip=True))
                if text:
                    authors = self._split_author_string(text)
        
        if not authors:
            author_elem = soup.select_one("[class*='author']")
            if author_elem:
                text = self._normalize_text(author_elem.get_text(" ", strip=True))
                if text:
                    authors = self._split_author_string(text)
        
        if not authors:
            text = soup.get_text(" ", strip=True)
            match = re.search(r"作者[:：]\s*([^\n]+)", text)
            if match:
                authors = self._split_author_string(match.group(1))
        
        return [author for author in authors if author and self._is_valid_author(author)]

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
            if not isinstance(href, str):
                continue
            
            href_lower = href.lower()
            if ".pdf" in href_lower or "download" in href_lower or "fulltext" in href_lower:
                url = urllib.parse.urljoin(self.base_url, href)
                if self._is_valid_pdf_url(url):
                    return url
        
        for link in soup.select("a"):
            text = link.get_text(" ", strip=True).lower()
            if "pdf" in text or "全文下载" in text or "下载" in text:
                href = link.get("href")
                if isinstance(href, str):
                    url = urllib.parse.urljoin(self.base_url, href)
                    if self._is_valid_pdf_url(url):
                        return url
        
        return None

    def _extract_detail_doi(self, soup: BeautifulSoup) -> Optional[str]:
        for link in soup.select("a[href*='doi.org']"):
            href = link.get("href")
            doi = self._normalize_doi_doi(href)
            if doi:
                return doi
            text = link.get_text(" ", strip=True)
            doi = self._normalize_doi_doi(text)
            if doi:
                return doi
        
        text = soup.get_text(" ", strip=True)
        doi = self._extract_doi_from_text(text)
        if doi:
            return doi
        
        return None
    
    def _extract_doi_from_text(self, text: str) -> Optional[str]:
        if not text:
            return None
        
        match = re.search(r'\b(10\.\d{4,}/[^\s]+)', text)
        if match:
            candidate = match.group(1)
            candidate = re.sub(r'[,;.\)\]]+$', '', candidate)
            if '/' in candidate and len(candidate) > 7:
                return candidate
        
        return None
    
    def _is_interstitial_page(self, soup: BeautifulSoup) -> bool:
        if not soup:
            return False
        
        text = soup.get_text(" ", strip=True).lower()
        
        auth_keywords = [
            "登录", "login", "sign in", "验证码", "captcha",
            "暂无权限", "unauthorized", "403", "401",
            "需要登录", "请登录", "authentication required"
        ]
        
        for keyword in auth_keywords:
            if keyword in text:
                return True
        
        if soup.find("input", {"type": "password"}):
            return True
        
        for form in soup.find_all("form"):
            action = form.get("action", "")
            if isinstance(action, str) and re.search(r"login|auth", action, re.I):
                return True
        
        for img in soup.find_all("img"):
            alt = img.get("alt", "")
            if isinstance(alt, str) and re.search(r"captcha|验证码", alt, re.I):
                return True
        
        return False
    
    def _is_valid_doi(self, doi: str) -> bool:
        if not doi or not isinstance(doi, str):
            return False
        if len(doi) < 7:
            return False
        if not doi.startswith("10."):
            return False
        if "/" not in doi:
            return False
        return True
    
    def _is_valid_pdf_url(self, url: str) -> bool:
        if not url or not isinstance(url, str):
            return False
        if len(url) < 10:
            return False
        if not url.startswith("http"):
            return False
        if "login" in url.lower() or "error" in url.lower():
            return False
        return True
    
    def _is_valid_year(self, year: Optional[int]) -> bool:
        if year is None or not isinstance(year, int):
            return False
        if year < 1900 or year > 2100:
            return False
        return True
