"""PubMed crawler using NCBI E-utilities API."""

from __future__ import annotations

import logging
import urllib.parse
from typing import Any, Optional

from refminer.crawler.base import BaseCrawler
from refminer.crawler.models import SearchQuery, SearchResult

logger = logging.getLogger(__name__)


class PubMedCrawler(BaseCrawler):
    """PubMed crawler using NCBI E-utilities API."""

    @property
    def name(self) -> str:
        return "pubmed"

    @property
    def base_base_url(self) -> str:
        return "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    @property
    def base_url(self) -> str:
        return "https://pubmed.ncbi.nlm.nih.gov"

    @property
    def requires_api_key(self) -> bool:
        return False

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        """Search PubMed for papers."""
        results: list[SearchResult] = []

        try:
            pmids = await self._search_pmids(query)
            if not pmids:
                logger.info(f"[{self.name}] No PMIDs found")
                return []

            summaries = await self._fetch_summaries(pmids)
            results = self._parse_summaries(summaries, query)

            logger.info(f"[{self.name}] Found {len(results)} results")
        except Exception as e:
            logger.error(f"[{self.name}] Search failed: {e}", exc_info=True)

        return results

    async def _search_pmids(self, query: SearchQuery) -> list[str]:
        """Search for PMIDs using ESearch."""
        search_url = f"{self.base_base_url}/esearch.fcgi"

        params = {
            "db": "pubmed",
            "term": query.query,
            "retmode": "json",
            "retmax": str(query.max_results),
        }

        if query.year_from:
            params["datetype"] = "pdat"
            params["mindate"] = str(query.year_from)
        if query.year_to:
            params["datetype"] = "pdat"
            params["maxdate"] = str(query.year_to)

        response = await self._fetch(search_url, params=params)
        data = response.json()

        pmids = data.get("esearchresult", {}).get("idlist", [])
        return pmids

    async def _fetch_summaries(self, pmids: list[str]) -> dict[str, Any]:
        """Fetch article summaries using ESummary."""
        if not pmids:
            return {}

        summary_url = f"{self.base_base_url}/esummary.fcgi"

        params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "json",
            "rettype": "abstract",
        }

        response = await self._fetch(summary_url, params=params)
        return response.json()

    def _parse_summaries(
        self, data: dict[str, Any], query: SearchQuery
    ) -> list[SearchResult]:
        """Parse ESummary results."""
        results: list[SearchResult] = []

        result_data = data.get("result", {})
        if not result_data:
            return results

        uids = result_data.get("uids", [])
        for uid in uids:
            try:
                article_data = result_data.get(uid, {})
                result = self._parse_single_article(article_data, uid)
                if result:
                    results.append(result)
            except Exception as e:
                logger.debug(f"[{self.name}] Failed to parse article {uid}: {e}")
                continue

        return results

    def _parse_single_article(
        self, data: dict[str, Any], uid: str
    ) -> Optional[SearchResult]:
        """Parse a single article from ESummary."""
        title = data.get("title", "")
        if not title:
            return None

        authors = self._parse_authors(data)
        year = self._parse_year(data)
        doi = self._parse_doi(data)
        abstract = self._parse_abstract(data)
        pdf_url = self._parse_pdf_url(data)
        journal = data.get("source", "")
        volume = self._parse_volume(data)
        issue = self._parse_issue(data)
        pages = self._parse_pages(data)
        citation_count = self._parse_citation_count(data)

        result = SearchResult(
            title=title,
            authors=authors,
            year=year,
            doi=doi,
            abstract=abstract,
            source=self.name,
            url=f"{self.base_url}/{uid}/",
            pdf_url=pdf_url,
            journal=journal,
            volume=volume,
            issue=issue,
            pages=pages,
            citation_count=citation_count,
        )

        return result

    def _parse_authors(self, data: dict[str, Any]) -> list[str]:
        """Parse authors from article data."""
        authors: list[str] = []
        authors_list = data.get("authors", [])

        for author in authors_list:
            name = author.get("name", "")
            if name:
                authors.append(name)

        return authors

    def _parse_year(self, data: dict[str, Any]) -> Optional[int]:
        """Parse publication year from article data."""
        pubdates = data.get("pubdates", [])
        for pubdate in pubdates:
            year = pubdate.get("year")
            if year:
                try:
                    return int(year)
                except (ValueError, TypeError):
                    continue
        return None

    def _parse_doi(self, data: dict[str, Any]) -> Optional[str]:
        """Parse DOI from article data."""
        article_ids = data.get("articleids", [])
        for aid in article_ids:
            if aid.get("idtype") == "doi":
                return aid.get("value")
        return None

    def _parse_abstract(self, data: dict[str, Any]) -> Optional[str]:
        """Parse abstract from article data."""
        return data.get("abstract")

    def _parse_pdf_url(self, data: dict[str, Any]) -> Optional[str]:
        """Parse PDF URL from article data."""
        pmcid = data.get("pmcid", "")
        if pmcid:
            return f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf"
        return None

    def _parse_volume(self, data: dict[str, Any]) -> Optional[str]:
        """Parse volume from article data."""
        volume = data.get("volume", "")
        return volume if volume else None

    def _parse_issue(self, data: dict[str, Any]) -> Optional[str]:
        """Parse issue from article data."""
        issue = data.get("issue", "")
        return issue if issue else None

    def _parse_pages(self, data: dict[str, Any]) -> Optional[str]:
        """Parse pages from article data."""
        pages = data.get("pages", "")
        return pages if pages else None

    def _parse_citation_count(self, data: dict[str, Any]) -> Optional[int]:
        """Parse citation count from article data."""
        pmcrefcount = data.get("pmcrefcount", "")
        if pmcrefcount:
            try:
                return int(pmcrefcount)
            except (ValueError, TypeError):
                pass
        return None
