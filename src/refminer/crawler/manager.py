"""Crawler manager for orchestrating multiple search engines."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Optional

from refminer.crawler.base import BaseCrawler
from refminer.crawler.engines import (
    GoogleScholarCrawler,
    PubMedCrawler,
    SemanticScholarCrawler,
)
from refminer.crawler.models import CrawlerConfig, SearchQuery, SearchResult

logger = logging.getLogger(__name__)


class CrawlerManager:
    """Manager for coordinating multiple crawler engines."""

    def __init__(self, config: Optional[CrawlerConfig] = None) -> None:
        self.config = config or CrawlerConfig()
        self._engines: dict[str, BaseCrawler] = {}
        self._initialize_engines()

    def _initialize_engines(self) -> None:
        """Initialize all available engines."""
        self._engines = {
            "google_scholar": GoogleScholarCrawler(
                self.config.get_engine_config("google_scholar")
            ),
            "pubmed": PubMedCrawler(self.config.get_engine_config("pubmed")),
            "semantic_scholar": SemanticScholarCrawler(
                self.config.get_engine_config("semantic_scholar")
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

        if not engines:
            logger.warning("[CrawlerManager] No enabled engines")
            return []

        logger.info(
            f"[CrawlerManager] Searching with engines: {', '.join(engines)}"
        )

        tasks = []
        for engine_name in engines:
            if not self.config.is_engine_enabled(engine_name):
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
                logger.error(
                    f"[CrawlerManager] Engine {engines[i]} failed: {result}"
                )
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
            logger.info(f"[CrawlerManager] {engine.name} returned {len(results)} results")
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
