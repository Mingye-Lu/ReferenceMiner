"""Crawler engine implementations."""

from __future__ import annotations

from refminer.crawler.engines.airiti import AiritiCrawler
from refminer.crawler.engines.arxiv import ArXivCrawler
from refminer.crawler.engines.biorxiv_medrxiv import BiorxivMedrxivCrawler
from refminer.crawler.engines.core import CoreCrawler
from refminer.crawler.engines.crossref import CrossrefCrawler
from refminer.crawler.engines.europe_pmc import EuropePmcCrawler
from refminer.crawler.engines.google_scholar import GoogleScholarCrawler
from refminer.crawler.engines.nstl import NstlCrawler
from refminer.crawler.engines.openalex import OpenAlexCrawler
from refminer.crawler.engines.pubmed import PubMedCrawler
from refminer.crawler.engines.semantic_scholar import SemanticScholarCrawler

__all__ = [
    "AiritiCrawler",
    "ArXivCrawler",
    "BiorxivMedrxivCrawler",
    "CoreCrawler",
    "CrossrefCrawler",
    "EuropePmcCrawler",
    "GoogleScholarCrawler",
    "NstlCrawler",
    "OpenAlexCrawler",
    "PubMedCrawler",
    "SemanticScholarCrawler",
]
