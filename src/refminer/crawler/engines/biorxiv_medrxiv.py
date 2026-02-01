"""bioRxiv/medRxiv crawler using Cold Spring Harbor API."""

from __future__ import annotations

import logging
import urllib.parse
from typing import Any, Optional

from refminer.crawler.base import BaseCrawler
from refminer.crawler.models import SearchQuery, SearchResult

logger = logging.getLogger(__name__)


class BiorxivMedrxivCrawler(BaseCrawler):
    """bioRxiv/medRxiv crawler using Cold Spring Harbor API."""

    @property
    def name(self) -> str:
        return "biorxiv_medrxiv"

    @property
    def base_url(self) -> str:
        return "https://api.biorxiv.org/pub/biorxiv/medrxiv"

    @property
    def requires_api_key(self) -> bool:
        return False

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        """Search bioRxiv/medRxiv for papers."""
        results: list[SearchResult] = []

        try:
            search_url = self._build_search_url(query)
            response = await self._fetch(search_url)
            results = self._parse_results(response.text, query)

            logger.info(f"[{self.name}] Found {len(results)} results")
        except Exception as e:
            logger.error(f"[{self.name}] Search failed: {e}", exc_info=True)

        return results

    def _build_search_url(self, query: SearchQuery) -> str:
        """Build bioRxiv/medRxiv search URL."""
        from_date = "2020-01-01"
        to_date = "2099-12-31"

        if query.year_from:
            from_date = f"{query.year_from}-01-01"
        if query.year_to:
            to_date = f"{query.year_to}-12-31"

        params = {
            "interval": f"{from_date}/{to_date}",
            "format": "json",
            "limit": str(query.max_results),
        }

        query_string = "&".join(
            f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items()
        )
        return f"{self.base_url}/{query_string}"

    def _parse_results(self, json_text: str, query: SearchQuery) -> list[SearchResult]:
        """Parse bioRxiv/medRxiv JSON response."""
        try:
            import json
        except ImportError:
            logger.error(f"[{self.name}] json module not available")
            return []

        results: list[SearchResult] = []

        try:
            data = json.loads(json_text)
            collection = data.get("collection", [])

            for item in collection:
                try:
                    result = self._parse_single_item(item, query)
                    if result:
                        results.append(result)
                except Exception as e:
                    logger.debug(f"[{self.name}] Failed to parse item: {e}")
                    continue
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"[{self.name}] Failed to parse JSON: {e}")

        return results

    def _parse_single_item(
        self, item: dict[str, Any], query: SearchQuery
    ) -> Optional[SearchResult]:
        """Parse a single search result item."""
        title = item.get("preprint_title", "")
        if not title:
            return None

        authors = self._parse_authors(item)
        year = self._parse_year(item)
        doi = item.get("biorxiv_doi")
        abstract = self._parse_abstract(item)
        url = item.get("biorxiv_doi")
        pdf_url = self._parse_pdf_url(item)
        journal = item.get("server")

        if url:
            url = f"https://www.biorxiv.org/content/{url}"

        result = SearchResult(
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

        return result

    def _parse_authors(self, item: dict[str, Any]) -> list[str]:
        """Parse authors from item."""
        authors: list[str] = []
        authors_text = item.get("authors", "")
        if authors_text:
            authors = [a.strip() for a in authors_text.split(";") if a.strip()]

        return authors

    def _parse_year(self, item: dict[str, Any]) -> Optional[int]:
        """Parse publication year from item."""
        date = item.get("preprint_date", "")
        if date:
            try:
                year_str = date.split("-")[0]
                return int(year_str)
            except (ValueError, IndexError):
                pass
        return None

    def _parse_abstract(self, item: dict[str, Any]) -> Optional[str]:
        """Parse abstract from item."""
        abstract = item.get("abstract", "")
        return abstract if abstract else None

    def _parse_pdf_url(self, item: dict[str, Any]) -> Optional[str]:
        """Parse PDF URL from item."""
        doi = item.get("biorxiv_doi", "")
        if doi:
            return f"https://www.biorxiv.org/content/{doi}.full.pdf"
        return None
