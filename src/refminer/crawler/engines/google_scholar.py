"""Google Scholar crawler (web scraping).

NOTE: This crawler uses web scraping which may violate Google Scholar's terms of service.
Users are responsible for ensuring compliance with applicable laws and terms of service.
"""

from __future__ import annotations

import logging
import re
import urllib.parse
from typing import Optional

from bs4 import BeautifulSoup

from refminer.crawler.base import BaseCrawler
from refminer.crawler.models import SearchQuery, SearchResult

logger = logging.getLogger(__name__)


class GoogleScholarCrawler(BaseCrawler):
    """Google Scholar crawler using web scraping."""

    @property
    def name(self) -> str:
        return "google_scholar"

    @property
    def base_url(self) -> str:
        return "https://scholar.google.com"

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        """Search Google Scholar for papers."""
        results: list[SearchResult] = []

        try:
            search_url = self._build_search_url(query)
            response = await self._fetch(search_url)
            soup = BeautifulSoup(response.text, "html.parser")
            results = self._parse_results(soup, query)

            logger.info(f"[{self.name}] Found {len(results)} results")
        except Exception as e:
            logger.error(f"[{self.name}] Search failed: {e}", exc_info=True)

        return results

    def _build_search_url(self, query: SearchQuery) -> str:
        """Build Google Scholar search URL."""
        params = {
            "q": query.query,
            "hl": "en",
            "as_sdt": "0,5",
        }

        if query.year_from:
            params["as_ylo"] = str(query.year_from)
        if query.year_to:
            params["as_yhi"] = str(query.year_to)

        encoded_params = urllib.parse.urlencode(params)
        return f"{self.base_url}/scholar?{encoded_params}"

    def _parse_results(
        self, soup: BeautifulSoup, query: SearchQuery
    ) -> list[SearchResult]:
        """Parse search results from HTML."""
        results: list[SearchResult] = []

        for div in soup.find_all("div", class_="gs_r gs_or gs_scl"):
            try:
                result = self._parse_single_result(div, query)
                if result:
                    results.append(result)
            except Exception as e:
                logger.debug(f"[{self.name}] Failed to parse result: {e}")
                continue

        return results

    def _parse_single_result(
        self, div: BeautifulSoup, query: SearchQuery
    ) -> Optional[SearchResult]:
        """Parse a single search result."""
        title_div = div.find("h3", class_="gs_rt")
        if not title_div:
            return None

        title_link = title_div.find("a")
        if title_link:
            title = title_link.get_text(strip=True)
            url = title_link.get("href", "")
        else:
            title = title_div.get_text(strip=True)
            url = None

        if not title:
            return None

        authors, year, journal = self._parse_authors_year_journal(div)

        result = SearchResult(
            title=title,
            authors=authors,
            year=year,
            source=self.name,
            url=url,
            journal=journal,
        )

        return result

    def _parse_authors_year_journal(
        self, div: BeautifulSoup
    ) -> tuple[list[str], Optional[int], Optional[str]]:
        """Parse authors, year, and journal from result div."""
        authors: list[str] = []
        year: Optional[int] = None
        journal: Optional[str] = None

        gs_a = div.find("div", class_="gs_a")
        if gs_a:
            text = gs_a.get_text(strip=True)

            year_match = re.search(r"\b(\d{4})\b", text)
            if year_match:
                year = int(year_match.group(1))

            parts = text.split("-")
            if parts:
                authors_text = parts[0].strip()
                authors = [a.strip() for a in authors_text.split(",") if a.strip()]

                if len(parts) > 1:
                    journal = parts[-1].strip()

        return authors, year, journal
