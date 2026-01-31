"""Paper crawler module for ReferenceMiner."""

from __future__ import annotations

from refminer.crawler.deep_crawler import DeepCrawler
from refminer.crawler.downloader import PDFDownloader
from refminer.crawler.manager import CrawlerManager
from refminer.crawler.models import (
    CrawlerConfig,
    EngineConfig,
    SearchResult,
    SearchQuery,
)

__all__ = [
    "CrawlerManager",
    "DeepCrawler",
    "PDFDownloader",
    "CrawlerConfig",
    "EngineConfig",
    "SearchResult",
    "SearchQuery",
]
