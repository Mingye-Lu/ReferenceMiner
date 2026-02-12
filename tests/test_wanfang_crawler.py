from __future__ import annotations

import base64
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refminer.crawler.engines.wanfang import BlockedBySiteError, WanfangCrawler
from refminer.crawler.models import SearchQuery


class TestWanfangCrawler(unittest.IsolatedAsyncioTestCase):
    crawler: WanfangCrawler = WanfangCrawler()

    def setUp(self) -> None:
        self.crawler = WanfangCrawler()

    def _build_response(self, body: str) -> httpx.Response:
        request = httpx.Request(
            "GET", "https://s.wanfangdata.com.cn/paper?q=distill&p=1"
        )
        return httpx.Response(
            200,
            content=body.encode("utf-8"),
            headers={"Content-Type": "text/html; charset=utf-8"},
            request=request,
        )

    def _fixture_bytes(self, relative_path: str) -> bytes:
        fixture_path = ROOT / relative_path
        encoded = fixture_path.read_text(encoding="ascii").strip()
        return base64.b64decode(encoded)

    async def test_search_raises_blocked_error_for_interstitial_html(self) -> None:
        blocked_html = """
        <html>
          <body>
            <div>万方数据知识服务平台</div>
            <div>检测到您正在使用 Safari 浏览器</div>
            <div>建议升级您的浏览器</div>
          </body>
        </html>
        """
        self.crawler._fetch = AsyncMock(return_value=self._build_response(blocked_html))
        self.crawler._search_grpc = AsyncMock(return_value=[])

        with self.assertRaises(BlockedBySiteError) as context:
            await self.crawler.search(
                SearchQuery(
                    query="Distill",
                    engines=None,
                    year_from=None,
                    year_to=None,
                    max_results=5,
                    fields=None,
                    include_abstract=True,
                )
            )

        self.assertIn("Safari", str(context.exception))

    async def test_search_parses_single_result_from_minimal_html(self) -> None:
        result_html = """
        <html>
          <body>
            <div class="search-result-item">
              <h3><a href="/details/ABC123">Distillation and Attention</a></h3>
              <div class="author">Alice; Bob</div>
              <div class="journal">Journal of Testing</div>
              <div>2024</div>
            </div>
          </body>
        </html>
        """
        self.crawler._fetch = AsyncMock(return_value=self._build_response(result_html))
        self.crawler._search_grpc = AsyncMock(return_value=[])
        self.crawler._enrich_results = AsyncMock(return_value=None)

        results = await self.crawler.search(
            SearchQuery(
                query="Distill",
                engines=None,
                year_from=None,
                year_to=None,
                max_results=1,
                fields=None,
                include_abstract=True,
            )
        )

        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].title)
        self.assertTrue(results[0].url)

    async def test_search_continues_when_warmup_request_fails(self) -> None:
        result_html = """
        <html>
          <body>
            <div class="search-result-item">
              <h3><a href="/details/ABC123">Distillation and Attention</a></h3>
              <div class="author">Alice; Bob</div>
              <div class="journal">Journal of Testing</div>
              <div>2024</div>
            </div>
          </body>
        </html>
        """
        self.crawler._fetch = AsyncMock(
            side_effect=[
                RuntimeError("warmup failed"),
                self._build_response(result_html),
            ]
        )
        self.crawler._search_grpc = AsyncMock(return_value=[])
        self.crawler._enrich_results = AsyncMock(return_value=None)

        results = await self.crawler.search(
            SearchQuery(
                query="Distill",
                engines=None,
                year_from=None,
                year_to=None,
                max_results=1,
                fields=None,
                include_abstract=True,
            )
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(self.crawler._fetch.await_count, 2)

    def test_parse_grpc_fixture_returns_periodical_results(self) -> None:
        payload = self._fixture_bytes(
            "tests/fixtures/wanfang/search_response_periodical_distill_page1.b64"
        )
        query = SearchQuery(
            query="Distill",
            engines=None,
            year_from=None,
            year_to=None,
            max_results=5,
            fields=None,
            include_abstract=True,
        )

        count, results = self.crawler._parse_grpc_search_response(payload, query)

        self.assertGreaterEqual(count, 1)
        self.assertGreaterEqual(len(results), 1)
        first = results[0]
        self.assertTrue(first.title)
        self.assertTrue(first.url)
        self.assertTrue(first.authors)
        self.assertIsInstance(first.year, int)


if __name__ == "__main__":
    unittest.main()
