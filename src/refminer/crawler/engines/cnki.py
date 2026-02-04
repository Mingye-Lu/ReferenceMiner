"""CNKI crawler using the licensed CNKI API."""

from __future__ import annotations

import logging

from refminer.crawler.base import BaseCrawler
from refminer.crawler.models import SearchQuery, SearchResult

logger = logging.getLogger(__name__)


class CnkiCrawler(BaseCrawler):
    """CNKI crawler using the licensed CNKI API."""

    @property
    def name(self) -> str:
        return "cnki"

    @property
    def base_url(self) -> str:
        return "https://www.cnki.net"

    @property
    def requires_api_key(self) -> bool:
        return True

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        """Search CNKI for papers via the licensed API."""
        if not self.config.api_key:
            logger.warning(
                "[%s] CNKI requires a licensed API key. Configure crawler.engine_settings.cnki.api_key to enable.",
                self.name,
            )
            return []

        logger.error(
            "[%s] CNKI API endpoint is not configured. Provide the licensed API base URL and schema to complete integration.",
            self.name,
        )
        return []
