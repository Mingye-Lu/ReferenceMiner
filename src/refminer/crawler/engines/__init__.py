"""Crawler engine implementations."""

from __future__ import annotations

from refminer.crawler.engines.google_scholar import GoogleScholarCrawler
from refminer.crawler.engines.pubmed import PubMedCrawler
from refminer.crawler.engines.semantic_scholar import SemanticScholarCrawler

__all__ = [
    "GoogleScholarCrawler",
    "PubMedCrawler",
    "SemanticScholarCrawler",
]
