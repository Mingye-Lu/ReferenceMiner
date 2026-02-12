"""Crawler manager for orchestrating multiple search engines."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any
from typing import Optional

from refminer.crawler.base import BaseCrawler
from refminer.crawler.engines import (
    AiritiCrawler,
    ArXivCrawler,
    BiorxivMedrxivCrawler,
    ChaoxingCrawler,
    ChinaXivCrawler,
    CnkiCrawler,
    CoreCrawler,
    CrossrefCrawler,
    EuropePmcCrawler,
    GoogleScholarCrawler,
    NstlCrawler,
    OpenAlexCrawler,
    PubMedCrawler,
    SemanticScholarCrawler,
    WanfangCrawler,
)
from refminer.crawler.models import CrawlerConfig, SearchQuery, SearchResult

logger = logging.getLogger(__name__)


class CrawlerManager:
    """Manager for coordinating multiple crawler engines."""

    def __init__(
        self,
        config: Optional[CrawlerConfig] = None,
        auth_profiles: Optional[dict[str, dict[str, Any]]] = None,
    ) -> None:
        self.config = config or CrawlerConfig()
        self.auth_profiles = auth_profiles or {}
        self._engines: dict[str, BaseCrawler] = {}
        self._initialize_engines()

    def _engine_auth(self, name: str) -> dict[str, Any]:
        profile = self.auth_profiles.get(name)
        if isinstance(profile, dict):
            return profile
        return {}

    def _initialize_engines(self) -> None:
        """Initialize all available engines."""
        self._engines = {
            "airiti": AiritiCrawler(
                self.config.get_engine_config("airiti"),
                self._engine_auth("airiti"),
            ),
            "chaoxing": ChaoxingCrawler(
                self.config.get_engine_config("chaoxing"),
                self._engine_auth("chaoxing"),
            ),
            "chinaxiv": ChinaXivCrawler(
                self.config.get_engine_config("chinaxiv"),
                self._engine_auth("chinaxiv"),
            ),
            "cnki": CnkiCrawler(
                self.config.get_engine_config("cnki"),
                self._engine_auth("cnki"),
            ),
            "google_scholar": GoogleScholarCrawler(
                self.config.get_engine_config("google_scholar"),
                self._engine_auth("google_scholar"),
            ),
            "pubmed": PubMedCrawler(
                self.config.get_engine_config("pubmed"),
                self._engine_auth("pubmed"),
            ),
            "semantic_scholar": SemanticScholarCrawler(
                self.config.get_engine_config("semantic_scholar"),
                self._engine_auth("semantic_scholar"),
            ),
            "arxiv": ArXivCrawler(
                self.config.get_engine_config("arxiv"),
                self._engine_auth("arxiv"),
            ),
            "crossref": CrossrefCrawler(
                self.config.get_engine_config("crossref"),
                self._engine_auth("crossref"),
            ),
            "openalex": OpenAlexCrawler(
                self.config.get_engine_config("openalex"),
                self._engine_auth("openalex"),
            ),
            "core": CoreCrawler(
                self.config.get_engine_config("core"),
                self._engine_auth("core"),
            ),
            "europe_pmc": EuropePmcCrawler(
                self.config.get_engine_config("europe_pmc"),
                self._engine_auth("europe_pmc"),
            ),
            "biorxiv_medrxiv": BiorxivMedrxivCrawler(
                self.config.get_engine_config("biorxiv_medrxiv"),
                self._engine_auth("biorxiv_medrxiv"),
            ),
            "nstl": NstlCrawler(
                self.config.get_engine_config("nstl"),
                self._engine_auth("nstl"),
            ),
            "wanfang": WanfangCrawler(
                self.config.get_engine_config("wanfang"),
                self._engine_auth("wanfang"),
            ),
        }

    def get_engine(self, name: str) -> Optional[BaseCrawler]:
        """Get a specific engine by name."""
        return self._engines.get(name)

    def list_engines(self) -> list[str]:
        """List all available engine names."""
        return list(self._engines.keys())

    def list_enabled_engines(self) -> list[str]:
        """List enabled engine names."""
        return [
            name for name in self._engines.keys() if self.config.is_engine_enabled(name)
        ]

    async def search(
        self,
        query: SearchQuery,
        engines: Optional[list[str]] = None,
        allow_disabled: bool = False,
    ) -> list[SearchResult]:
        """Search across multiple engines concurrently.

        Args:
            query: Search query parameters
            engines: Specific engines to use (default: all enabled)

        Returns:
            Deduplicated list of search results
        """
        if engines is None:
            engines = self.list_enabled_engines()
        else:
            engines = list(dict.fromkeys(engines))

        if not engines:
            logger.warning("[CrawlerManager] No enabled engines")
            return []

        logger.info(f"[CrawlerManager] Searching with engines: {', '.join(engines)}")

        tasks = []
        for engine_name in engines:
            if not allow_disabled and not self.config.is_engine_enabled(engine_name):
                logger.info(f"[CrawlerManager] Skipping disabled engine: {engine_name}")
                continue

            engine = self.get_engine(engine_name)
            if engine is None:
                logger.warning(f"[CrawlerManager] Engine not found: {engine_name}")
                continue

            tasks.append(self._search_single_engine(engine, query))

        if not tasks:
            return []

        results_by_engine = await asyncio.gather(*tasks, return_exceptions=True)

        all_results: list[SearchResult] = []
        for i, result in enumerate(results_by_engine):
            if isinstance(result, Exception):
                logger.error(f"[CrawlerManager] Engine {engines[i]} failed: {result}")
                continue
            all_results.extend(result)

        deduplicated = self._deduplicate_results(all_results)
        logger.info(
            f"[CrawlerManager] Found {len(all_results)} results, "
            f"deduplicated to {len(deduplicated)}"
        )

        return deduplicated

    async def _search_single_engine(
        self, engine: BaseCrawler, query: SearchQuery
    ) -> list[SearchResult]:
        """Search with a single engine with error handling."""
        try:
            logger.info(f"[CrawlerManager] Searching with {engine.name}")
            results = await engine.search(query)
            logger.info(
                f"[CrawlerManager] {engine.name} returned {len(results)} results"
            )
            return results
        except Exception as e:
            logger.error(f"[CrawlerManager] {engine.name} error: {e}", exc_info=True)
            raise

    def _deduplicate_results(self, results: list[SearchResult]) -> list[SearchResult]:
        """Remove duplicate results based on hash."""
        seen_hashes: set[str] = set()
        deduplicated: list[SearchResult] = []

        for result in results:
            result_hash = result.get_hash()
            if result_hash not in seen_hashes:
                seen_hashes.add(result_hash)
                deduplicated.append(result)

        return deduplicated

    async def close(self) -> None:
        """Close all engine connections."""
        for engine in self._engines.values():
            await engine.close()

    async def __aenter__(self) -> CrawlerManager:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
