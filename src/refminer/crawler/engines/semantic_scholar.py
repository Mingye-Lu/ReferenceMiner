"""Semantic Scholar crawler using the free API."""

from __future__ import annotations

import logging
from typing import Any, Optional

from refminer.crawler.base import BaseCrawler
from refminer.crawler.models import SearchQuery, SearchResult

logger = logging.getLogger(__name__)


class SemanticScholarCrawler(BaseCrawler):
    """Semantic Scholar crawler using the free API."""

    @property
    def name(self) -> str:
        return "semantic_scholar"

    @property
    def base_url(self) -> str:
        return "https://api.semanticscholar.org/graph/v1/paper/search"

    @property
    def requires_api_key(self) -> bool:
        return False

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        """Search Semantic Scholar for papers."""
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
        """Build Semantic Scholar search URL."""
        fields = [
            "title",
            "authors",
            "year",
            "externalIds",
            "url",
            "openAccessPdf",
            "journal",
            "citationCount",
        ]

        if query.include_abstract:
            fields.append("abstract")

        params = {
            "query": query.query,
            "limit": str(query.max_results),
            "fields": ",".join(fields),
        }

        if query.year_from and query.year_to:
            params["year"] = f"{query.year_from}-{query.year_to}"
        elif query.year_from:
            params["year"] = f"{query.year_from}-"
        elif query.year_to:
            params["year"] = f"-{query.year_to}"

        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.base_url}?{query_string}"

    def _parse_results(
        self, data: dict[str, Any], query: SearchQuery
    ) -> list[SearchResult]:
        """Parse Semantic Scholar API response."""
        results: list[SearchResult] = []

        items = data.get("data", [])
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
        year = item.get("year")
        doi = self._parse_doi(item)
        abstract = item.get("abstract") if query.include_abstract else None
        url = item.get("url")
        pdf_url = self._parse_pdf_url(item)
        journal = self._parse_journal(item)
        citation_count = item.get("citationCount")

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
            citation_count=citation_count,
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

    def _parse_doi(self, item: dict[str, Any]) -> Optional[str]:
        """Parse DOI from external IDs."""
        external_ids = item.get("externalIds", {})
        return external_ids.get("DOI")

    def _parse_pdf_url(self, item: dict[str, Any]) -> Optional[str]:
        """Parse PDF URL from open access data."""
        open_access = item.get("openAccessPdf")
        if open_access:
            return open_access.get("url")
        return None

    def _parse_journal(self, item: dict[str, Any]) -> Optional[str]:
        """Parse journal name."""
        journal = item.get("journal")
        if journal:
            return journal.get("name")
        return None
