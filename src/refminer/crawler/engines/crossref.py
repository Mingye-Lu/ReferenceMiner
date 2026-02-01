"""Crossref crawler using the Crossref REST API."""

from __future__ import annotations

import logging
import urllib.parse
from typing import Any, Optional

from refminer.crawler.base import BaseCrawler
from refminer.crawler.models import SearchQuery, SearchResult

logger = logging.getLogger(__name__)


class CrossrefCrawler(BaseCrawler):
    """Crossref crawler using the Crossref REST API."""

    @property
    def name(self) -> str:
        return "crossref"

    @property
    def base_url(self) -> str:
        return "https://api.crossref.org/works"

    @property
    def requires_api_key(self) -> bool:
        return False

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        """Search Crossref for papers."""
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
        """Build Crossref search URL."""
        params = {
            "query": query.query,
            "rows": str(query.max_results),
        }

        if query.year_from and query.year_to:
            params["filter"] = (
                f"from-pub-date:{query.year_from},until-pub-date:{query.year_to}"
            )
        elif query.year_from:
            params["filter"] = f"from-pub-date:{query.year_from}"
        elif query.year_to:
            params["filter"] = f"until-pub-date:{query.year_to}"

        query_string = "&".join(
            f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items()
        )
        return f"{self.base_url}?{query_string}"

    def _parse_results(
        self, data: dict[str, Any], query: SearchQuery
    ) -> list[SearchResult]:
        """Parse Crossref API response."""
        results: list[SearchResult] = []

        items = data.get("message", {}).get("items", [])
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
        titles = item.get("title", [])
        if not titles:
            return None

        title = titles[0] if isinstance(titles, list) else titles
        if not title:
            return None

        authors = self._parse_authors(item)
        year = item.get("year")
        doi = item.get("DOI")
        url = item.get("URL")
        journal = self._parse_journal(item)
        volume = item.get("volume")
        issue = item.get("issue")
        pages = item.get("page")

        result = SearchResult(
            title=title,
            authors=authors,
            year=year,
            doi=doi,
            abstract=None,
            source=self.name,
            url=url,
            pdf_url=None,
            journal=journal,
            volume=volume,
            issue=issue,
            pages=pages,
            citation_count=None,
        )

        return result

    def _parse_authors(self, item: dict[str, Any]) -> list[str]:
        """Parse authors from item."""
        authors: list[str] = []
        authors_list = item.get("author", [])

        for author in authors_list:
            given = author.get("given", "")
            family = author.get("family", "")
            if given and family:
                authors.append(f"{given} {family}")
            elif family:
                authors.append(family)
            elif given:
                authors.append(given)

        return authors

    def _parse_journal(self, item: dict[str, Any]) -> Optional[str]:
        """Parse journal name."""
        container_titles = item.get("container-title", [])
        if container_titles and isinstance(container_titles, list):
            return container_titles[0]
        return None
