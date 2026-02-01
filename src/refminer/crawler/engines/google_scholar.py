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
from refminer.crawler.selector_engine import SelectorEngine
from refminer.crawler.selectors.google_scholar import GoogleScholarSelectors

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
            
            engine = SelectorEngine(soup)
            results = self._parse_results(engine, query)
            
            successful = engine.get_successful_selectors()
            if successful:
                logger.info(
                    f"[{self.name}] Successful selectors: {list(successful.keys())}"
                )
            
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
        self, engine: SelectorEngine, query: SearchQuery
    ) -> list[SearchResult]:
        """Parse search results from HTML using selector engine."""
        results: list[SearchResult] = []

        result_divs = engine.find_elements(GoogleScholarSelectors.RESULT_CONTAINER)
        
        for div in result_divs:
            try:
                result = self._parse_single_result(div, engine, query)
                if result:
                    results.append(result)
            except Exception as e:
                logger.debug(f"[{self.name}] Failed to parse result: {e}")
                continue

        return results

    def _parse_single_result(
        self, div: BeautifulSoup, engine: SelectorEngine, query: SearchQuery
    ) -> Optional[SearchResult]:
        """Parse a single search result using selector engine."""
        result_engine = SelectorEngine(div)
        
        title_element = result_engine.find_element(GoogleScholarSelectors.TITLE)
        if not title_element:
            return None

        title_link = result_engine.find_element(GoogleScholarSelectors.TITLE_LINK)
        
        url = None
        pdf_url = None
        
        if title_link:
            raw_title = title_link.get_text(strip=True)
            link_url = title_link.get("href", "")
            
            title = re.sub(r'^\[PDF\]\s*', '', raw_title).strip()
            
            link_url_str = str(link_url) if link_url else ""
            is_pdf_url = '.pdf' in link_url_str.lower() or '/pdf/' in link_url_str.lower()
            if is_pdf_url:
                pdf_url = link_url_str
                url = self._transform_pdf_to_landing_page(link_url_str)
            else:
                url = link_url_str
        else:
            title = title_element.get_text(strip=True)
            url = None

        if not title:
            return None

        if not pdf_url:
            pdf_link = result_engine.find_element(GoogleScholarSelectors.PDF_LINK)
            if pdf_link:
                pdf_url = pdf_link.get("href", "")

        authors, year, journal = self._parse_authors_year_journal(div)

        result = SearchResult(
            title=title,
            authors=authors,
            year=year,
            source=self.name,
            url=url,
            pdf_url=pdf_url,
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

    def _transform_pdf_to_landing_page(self, pdf_url: str) -> Optional[str]:
        """Transform PDF URL to landing page URL."""
        if 'arxiv.org/pdf/' in pdf_url:
            arxiv_id = pdf_url.split('/pdf/')[-1].replace('.pdf', '')
            return f"https://arxiv.org/abs/{arxiv_id}"
        
        if 'biorxiv.org' in pdf_url or 'medrxiv.org' in pdf_url:
            return pdf_url.replace('.full.pdf', '').replace('.pdf', '')
        
        return pdf_url
