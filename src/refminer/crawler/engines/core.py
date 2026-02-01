"""CORE crawler using the CORE API."""

from __future__ import annotations

import logging
import urllib.parse
from typing import Any, Optional

from refminer.crawler.base import BaseCrawler
from refminer.crawler.models import SearchQuery, SearchResult

logger = logging.getLogger(__name__)


class CoreCrawler(BaseCrawler):
    """CORE crawler using the CORE API."""

    @property
    def name(self) -> str:
        return "core"

    @property
    def base_url(self) -> str:
        return "https://api.core.ac.uk/v3/search/works"

    @property
    def requires_api_key(self) -> bool:
        return True

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        """Search CORE for papers."""
        results: list[SearchResult] = []

        try:
            search_url = self._build_search_url(query)
            response = await self._fetch(search_url)
            data = response.json()
            results = self._parse_results(data, query)

            logger.info(f"[{self.name}] Found {len(results)} results")
        except Exception as e:
            logger.error(f"[{self.name}] Search failed: {e}", exc_info=True)

        return results

    def _build_search_url(self, query: SearchQuery) -> str:
        """Build CORE search URL."""
        params = {
            "q": query.query,
            "limit": str(query.max_results),
        }

        if query.year_from:
            params["from"] = str(query.year_from)
        if query.year_to:
            params["to"] = str(query.year_to)

        query_string = "&".join(
            f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items()
        )
        return f"{self.base_url}?{query_string}"

    def _parse_results(
        self, data: dict[str, Any], query: SearchQuery
    ) -> list[SearchResult]:
        """Parse CORE API response."""
        results: list[SearchResult] = []

        items = data.get("results", [])
        for item in items:
            try:
                result = self._parse_single_item(item, query)
                if result:
                    results.append(result)
            except Exception as e:
                logger.debug(f"[{self.name}] Failed to parse item: {e}")
                continue

        return results

    def _parse_single_item(
        self, item: dict[str, Any], query: SearchQuery
    ) -> Optional[SearchResult]:
        """Parse a single search result item."""
        title = item.get("title", "")
        if not title:
            return None

        authors = self._parse_authors(item)
        year = self._parse_year(item)
        doi = self._parse_doi(item)
        abstract = self._parse_abstract(item)
        url = item.get("downloadUrl")
        journal = self._parse_journal(item)

        result = SearchResult(
            title=title,
            authors=authors,
            year=year,
            doi=doi,
            abstract=abstract,
            source=self.name,
            url=url,
            pdf_url=url,
            journal=journal,
        )

        return result

    def _parse_authors(self, item: dict[str, Any]) -> list[str]:
        """Parse authors from item."""
        authors: list[str] = []
        authors_list = item.get("authors", [])

        for author in authors_list:
            name = author.get("name", "")
            if name:
                authors.append(name)

        return authors

    def _parse_year(self, item: dict[str, Any]) -> Optional[int]:
        """Parse publication year from item."""
        year = item.get("yearPublished")
        if year:
            try:
                return int(year)
            except (ValueError, TypeError):
                pass
        return None

    def _parse_doi(self, item: dict[str, Any]) -> Optional[str]:
        """Parse DOI from item."""
        identifiers = item.get("identifiers", [])
        for identifier in identifiers:
            if identifier.get("type") == "doi":
                return identifier.get("identifier")
        return None

    def _parse_abstract(self, item: dict[str, Any]) -> Optional[str]:
        """Parse abstract from item."""
        return item.get("abstract")

    def _parse_journal(self, item: dict[str, Any]) -> Optional[str]:
        """Parse journal name."""
        journals = item.get("journals", [])
        if journals and isinstance(journals, list):
            return journals[0].get("name")
        return None
