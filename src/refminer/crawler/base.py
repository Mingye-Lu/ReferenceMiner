"""Abstract base crawler interface."""

from __future__ import annotations

import abc
import asyncio
import logging
import time
from typing import Any, Optional

import httpx

from refminer.crawler.auth import build_auth_headers
from refminer.crawler.models import (
    CrawlerConfig,
    EngineConfig,
    SearchQuery,
    SearchResult,
)

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple rate limiter using token bucket algorithm."""

    def __init__(self, rate_limit: int) -> None:
        self.rate_limit = rate_limit
        self.last_request_time = 0.0
        self.min_interval = 1.0 / rate_limit if rate_limit > 0 else 0.0

    async def acquire(self) -> None:
        """Wait until next request is allowed."""
        if self.min_interval <= 0:
            return
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_interval:
            wait_time = self.min_interval - time_since_last
            await asyncio.sleep(wait_time)
        self.last_request_time = time.time()


class BaseCrawler(abc.ABC):
    """Abstract base class for crawler engines."""

    def __init__(
        self,
        config: Optional[EngineConfig] = None,
        auth_profile: Optional[dict[str, Any]] = None,
    ) -> None:
        self.config = config or EngineConfig()
        self.rate_limiter = RateLimiter(self.config.rate_limit)
        self._client: Optional[httpx.AsyncClient] = None
        self.auth_profile = auth_profile or {}

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Engine name."""
        ...

    @property
    @abc.abstractmethod
    def base_url(self) -> str:
        """Base URL for the engine."""
        ...

    @property
    def requires_api_key(self) -> bool:
        """Whether this engine requires an API key."""
        return False

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            timeout = httpx.Timeout(self.config.timeout)
            self._client = httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                headers=self._get_headers(),
            )
        return self._client

    def _get_headers(self) -> dict[str, str]:
        """Get default headers for requests."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
        headers.update(build_auth_headers(self.auth_profile))
        return headers

    async def _fetch(
        self,
        url: str,
        method: str = "GET",
        params: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> httpx.Response:
        """Fetch URL with rate limiting and retry logic."""
        await self.rate_limiter.acquire()

        client = await self._get_client()
        request_headers = self._get_headers()
        if headers:
            request_headers.update(headers)

        last_error = None
        for attempt in range(self.config.max_retries):
            try:
                if method.upper() == "GET":
                    response = await client.get(
                        url, params=params, headers=request_headers
                    )
                elif method.upper() == "POST":
                    response = await client.post(
                        url, params=params, json=data, headers=request_headers
                    )
                else:
                    raise ValueError(f"Unsupported method: {method}")

                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(
                    f"[{self.name}] HTTP error on attempt {attempt + 1}: {e.response.status_code}"
                )
                if e.response.status_code in {429, 503, 504}:
                    await asyncio.sleep(2**attempt)
                else:
                    break
            except (httpx.RequestError, asyncio.TimeoutError) as e:
                last_error = e
                logger.warning(
                    f"[{self.name}] Request error on attempt {attempt + 1}: {e}"
                )
                await asyncio.sleep(2**attempt)

        raise RuntimeError(f"Failed to fetch {url}: {last_error}") from last_error

    @abc.abstractmethod
    async def search(self, query: SearchQuery) -> list[SearchResult]:
        """Search for papers."""
        ...

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self) -> BaseCrawler:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()
