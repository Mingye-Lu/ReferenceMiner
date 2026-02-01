"""OpenAlex crawler using the OpenAlex API."""

from __future__ import annotations

import logging
import urllib.parse
from typing import Any, Optional

from refminer.crawler.base import BaseCrawler
from refminer.crawler.models import SearchQuery, SearchResult

logger = logging.getLogger(__name__)


class OpenAlexCrawler(BaseCrawler):
    """OpenAlex crawler using the OpenAlex API."""

    @property
    def name(self) -> str:
        return "openalex"

    @property
    def base_url(self) -> str:
        return "https://api.openalex.org/works"

    @property
    def requires_api_key(self) -> bool:
        return False

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        """Search OpenAlex for papers."""
        results: list[SearchResult] = []

        try:
            search_url = self._build_searches_url(query)
            response = await self._fetch(search_url)
            data = response.json()
            results = self._parse_results(data, query)

            logger.info(f"[{self.name}] Found {len(results)} results")
        except Exception as e:
            logger.error(f"[{self.name}] Search failed: {e}", exc_info=True)

        return results

    def _build_searches_url(self, query: SearchQuery) -> str:
        """Build OpenAlex search URL."""
        params = {
            "search": query.query,
            "per-page": str(query.max_results),
        }

        filters = []
        if query.year_from:
            filters.append(f"from_publication_date:{query.year_from}-01-01")
        if query.year_to:
            filters.append(f"to_publication_date:{query.year_to}-12-31")

        if filters:
            params["filter"] = ",".join(filters)

        query_string = "&".join(
            f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items()
        )
        return f"{self.base_url}?{query_string}"

    def _parse_results(
        self, data: dict[str, Any], query: SearchQuery
    ) -> list[SearchResult]:
        """Parse OpenAlex API response."""
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
        url = item.get("id")
        pdf_url = self._parse_pdf_url(item)
        journal = self._parse_journal(item)
        citation_count = item.get("cited_by_count")

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
        authorships = item.get("authorships", [])

        for authorship in authorships:
            author = authorship.get("author", {})
            display_name = author.get("display_name", "")
            if display_name:
                authors.append(display_name)

        return authors

    def _parse_year(self, item: dict[str, Any]) -> Optional[int]:
        """Parse publication year from item."""
        year = item.get("publication_year")
        if year:
            try:
                return int(year)
            except (ValueError, TypeError):
                pass
        return None

    def _parse_doi(self, item: dict[str, Any]) -> Optional[str]:
        """Parse DOI from item."""
        ids = item.get("ids", {})
        return ids.get("doi")

    def _parse_abstract(self, item: dict[str, Any]) -> Optional[str]:
        """Parse abstract from inverted index."""
        inverted_index = item.get("abstract_inverted_index")
        if not inverted_index:
            return None

        try:
            word_positions = []
            for word, positions in inverted_index.items():
                for pos in positions:
                    word_positions.append((pos, word))

            word_positions.sort(key=lambda x: x[0])

            abstract_words = [word for pos, word in word_positions]
            return " ".join(abstract_words)
        except (TypeError, AttributeError):
            return None

    def _parse_pdf_url(self, item: dict[str, Any]) -> Optional[str]:
        """Parse PDF URL from item."""
        locations = item.get("best_location")
        if locations:
            return locations.get("pdf_url")
        return None

    def _parse_journal(self, item: dict[str, Any]) -> Optional[str]:
        """Parse journal name."""
        primary_location = item.get("primary_location")
        if primary_location:
            source = primary_location.get("source")
            if source:
                return source.get("display_name")
        return None
