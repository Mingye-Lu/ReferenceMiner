"""Europe PMC crawler using Europe PMC RESTful API."""

from __future__ import annotations

import logging
import urllib.parse
from typing import Any, Optional

from refminer.crawler.base import BaseCrawler
from refminer.crawler.models import SearchQuery, SearchResult

logger = logging.getLogger(__name__)


class EuropePmcCrawler(BaseCrawler):
    """Europe PMC crawler using Europe PMC RESTful API."""

    @property
    def name(self) -> str:
        return "europe_pmc"

    @property
    def base_url(self) -> str:
        return "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

    @property
    def requires_api_key(self) -> bool:
        return False

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        """Search Europe PMC for papers."""
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
        """Build Europe PMC search URL."""
        params = {
            "query": query.query,
            "resultType": "core",
            "pageSize": str(query.max_results),
            "format": "json",
        }

        if query.year_from:
            params["query"] += f" FIRST_PDATE:{query.year_from}"
        if query.year_to:
            params["query"] += f" LAST_PDATE:{query.year_to}"

        query_string = "&".join(
            f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items()
        )
        return f"{self.base_url}?{query_string}"

    def _parse_results(self, json_text: str, query: SearchQuery) -> list[SearchResult]:
        """Parse Europe PMC JSON response."""
        try:
            import json
        except ImportError:
            logger.error(f"[{self.name}] json module not available")
            return []

        results: list[SearchResult] = []

        try:
            data = json.loads(json_text)
            hit_count = data.get("hitCount", 0)

            if hit_count == 0:
                return results

            items = data.get("resultList", {}).get("result", [])
            for item in items:
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
        title = item.get("title", "")
        if not title:
            return None

        authors = self._parse_authors(item)
        year = self._parse_year(item)
        doi = self._parse_doi(item)
        abstract = self._parse_abstract(item)
        url = item.get("pmcid")
        pdf_url = self._parse_pdf_url(item)
        journal = self._parse_journal(item)
        volume = self._parse_volume(item)
        issue = self._parse_issue(item)
        pages = self._parse_pages(item)
        citation_count = item.get("citedByCount")

        if url:
            url = f"https://europepmc.org/article/PMC/{url}"

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
            volume=volume,
            issue=issue,
            pages=pages,
            citation_count=citation_count,
        )

        return result

    def _parse_authors(self, item: dict[str, Any]) -> list[str]:
        """Parse authors from item."""
        authors: list[str] = []
        author_list = item.get("authorList", {}).get("author", [])

        if not isinstance(author_list, list):
            author_list = [author_list]

        for author in author_list:
            if isinstance(author, dict):
                full_name = author.get("fullName", "")
                if full_name:
                    authors.append(full_name)
                else:
                    first_name = author.get("firstName", "")
                    last_name = author.get("lastName", "")
                    if first_name and last_name:
                        authors.append(f"{first_name} {last_name}")
                    elif last_name:
                        authors.append(last_name)
                    elif first_name:
                        authors.append(first_name)

        return authors

    def _parse_year(self, item: dict[str, Any]) -> Optional[int]:
        """Parse publication year from item."""
        pub_date = item.get("pubDate", "")
        if pub_date:
            try:
                year_str = pub_date.split("-")[0]
                return int(year_str)
            except (ValueError, IndexError):
                pass
        return None

    def _parse_doi(self, item: dict[str, Any]) -> Optional[str]:
        """Parse DOI from item."""
        doi = item.get("doi", "")
        return doi if doi else None

    def _parse_abstract(self, item: dict[str, Any]) -> Optional[str]:
        """Parse abstract from item."""
        abstract_text = item.get("abstractText", "")
        return abstract_text if abstract_text else None

    def _parse_pdf_url(self, item: dict[str, Any]) -> Optional[str]:
        """Parse PDF URL from item."""
        pmcid = item.get("pmcid", "")
        if pmcid:
            return f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf"
        return None

    def _parse_journal(self, item: dict[str, Any]) -> Optional[str]:
        """Parse journal name."""
        journal_info = item.get("journalInfo", {})
        journal = journal_info.get("journal", {})
        return journal.get("title")

    def _parse_volume(self, item: dict[str, Any]) -> Optional[str]:
        """Parse volume from item."""
        journal_info = item.get("journalInfo", {})
        volume = journal_info.get("volume")
        return str(volume) if volume else None

    def _parse_issue(self, item: dict[str, Any]) -> Optional[str]:
        """Parse issue from item."""
        journal_info = item.get("journalInfo", {})
        issue = journal_info.get("journalIssueId")
        return str(issue) if issue else None

    def _parse_pages(self, item: dict[str, Any]) -> Optional[str]:
        """Parse page range from item."""
        page_info = item.get("pageInfo", "")
        return page_info if page_info and page_info != "Not Available" else None
