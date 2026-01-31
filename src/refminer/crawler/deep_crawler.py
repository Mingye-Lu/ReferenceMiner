"""Deep crawler for citation-based expansion."""

from __future__ import annotations

import logging
from typing import Set

import httpx

from refminer.crawler.models import SearchResult

logger = logging.getLogger(__name__)


class DeepCrawler:
    """Deep crawler for citation-based paper discovery."""

    def __init__(self, max_papers: int = 50) -> None:
        self.max_papers = max_papers
        self.seen_hashes: Set[str] = set()
        self.seen_dois: Set[str] = set()

    async def expand_by_citations(
        self,
        initial_results: list[SearchResult],
        fetch_references: bool = True,
        fetch_citations: bool = True,
    ) -> list[SearchResult]:
        """Expand results by fetching citations and references.

        Args:
            initial_results: Initial search results
            fetch_references: Fetch papers cited by these papers
            fetch_citations: Fetch papers that cite these papers

        Returns:
            Expanded list of results including citations/references
        """
        all_results = list(initial_results)

        for result in initial_results:
            self._mark_seen(result)

        if not (fetch_references or fetch_citations):
            return all_results

        logger.info(f"[DeepCrawler] Starting deep crawl with {len(initial_results)} seeds")

        for result in initial_results:
            if len(all_results) >= self.max_papers:
                logger.info(f"[DeepCrawler] Reached max papers limit: {self.max_papers}")
                break

            if fetch_references:
                refs = await self._fetch_references(result)
                for ref in refs:
                    if self._is_new(ref):
                        all_results.append(ref)
                        self._mark_seen(ref)
                        logger.info(
                            f"[DeepCrawler] Added reference: {ref.title[:50]}..."
                        )

                    if len(all_results) >= self.max_papers:
                        break

            if fetch_citations and len(all_results) < self.max_papers:
                cites = await self._fetch_citations(result)
                for cite in cites:
                    if self._is_new(cite):
                        all_results.append(cite)
                        self._mark_seen(cite)
                        logger.info(
                            f"[DeepCrawler] Added citation: {cite.title[:50]}..."
                        )

                    if len(all_results) >= self.max_papers:
                        break

        logger.info(f"[DeepCrawler] Deep crawl complete: {len(all_results)} total papers")
        return all_results

    async def _fetch_references(
        self, result: SearchResult
    ) -> list[SearchResult]:
        """Fetch papers cited by this paper using Semantic Scholar."""
        if not result.doi:
            return []

        try:
            url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{result.doi}?fields=references.title,references.authors,references.year,references.doi,references.url,references.openAccessPdf"

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                data = response.json()

            refs = data.get("references", [])
            results = []

            for ref in refs[:10]:
                try:
                    title = ref.get("title", "")
                    if not title:
                        continue

                    authors = [
                        a.get("name", "")
                        for a in ref.get("authors", [])
                        if a.get("name")
                    ]

                    open_access = ref.get("openAccessPdf", {})
                    pdf_url = open_access.get("url") if open_access else None

                    result_ref = SearchResult(
                        title=title,
                        authors=authors,
                        year=ref.get("year"),
                        doi=ref.get("doi"),
                        source="semantic_scholar_reference",
                        url=ref.get("url"),
                        pdf_url=pdf_url,
                    )

                    results.append(result_ref)
                except Exception as e:
                    logger.debug(f"[DeepCrawler] Failed to parse reference: {e}")
                    continue

            return results

        except Exception as e:
            logger.error(f"[DeepCrawler] Failed to fetch references: {e}")
            return []

    async def _fetch_citations(
        self, result: SearchResult
    ) -> list[SearchResult]:
        """Fetch papers that cite this paper using Semantic Scholar."""
        if not result.doi:
            return []

        try:
            url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{result.doi}?fields=citations.title,citations.authors,citations.year,citations.doi,citations.url,citations.openAccessPdf"

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                data = response.json()

            cites = data.get("citations", [])
            results = []

            for cite in cites[:10]:
                try:
                    title = cite.get("title", "")
                    if not title:
                        continue

                    authors = [
                        a.get("name", "")
                        for a in cite.get("authors", [])
                        if a.get("name")
                    ]

                    open_access = cite.get("openAccessPdf", {})
                    pdf_url = open_access.get("url") if open_access else None

                    result_cite = SearchResult(
                        title=title,
                        authors=authors,
                        year=cite.get("year"),
                        doi=cite.get("doi"),
                        source="semantic_scholar_citation",
                        url=cite.get("url"),
                        pdf_url=pdf_url,
                    )

                    results.append(result_cite)
                except Exception as e:
                    logger.debug(f"[DeepCrawler] Failed to parse citation: {e}")
                    continue

            return results

        except Exception as e:
            logger.error(f"[DeepCrawler] Failed to fetch citations: {e}")
            return []

    def _mark_seen(self, result: SearchResult) -> None:
        """Mark a result as seen to avoid duplicates."""
        self.seen_hashes.add(result.get_hash())
        if result.doi:
            self.seen_dois.add(result.doi)

    def _is_new(self, result: SearchResult) -> bool:
        """Check if result is new (not seen before)."""
        return result.get_hash() not in self.seen_hashes
