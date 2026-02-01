"""Tests for Google Scholar crawler PDF URL parsing."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refminer.crawler.engines.google_scholar import GoogleScholarCrawler


class TestGoogleScholarPDFParsing(unittest.TestCase):
    """Test PDF URL parsing in Google Scholar crawler."""

    def setUp(self):
        """Set up test fixtures."""
        self.crawler = GoogleScholarCrawler()

    def test_transform_arxiv_pdf_to_landing(self):
        """Test transforming arXiv PDF URL to landing page."""
        pdf_url = "https://arxiv.org/pdf/2412.19437"
        landing = self.crawler._transform_pdf_to_landing_page(pdf_url)

        self.assertEqual(landing, "https://arxiv.org/abs/2412.19437")

    def test_transform_arxiv_pdf_with_extension(self):
        """Test transforming arXiv PDF URL with .pdf extension."""
        pdf_url = "https://arxiv.org/pdf/2412.19437.pdf"
        landing = self.crawler._transform_pdf_to_landing_page(pdf_url)

        self.assertEqual(landing, "https://arxiv.org/abs/2412.19437")

    def test_transform_biorxiv_pdf(self):
        """Test transforming bioRxiv PDF URL."""
        pdf_url = "https://biorxiv.org/content/10.1101/2024.123456.full.pdf"
        landing = self.crawler._transform_pdf_to_landing_page(pdf_url)

        self.assertEqual(landing, "https://biorxiv.org/content/10.1101/2024.123456")

    def test_transform_medrxiv_pdf(self):
        """Test transforming medRxiv PDF URL."""
        pdf_url = "https://medrxiv.org/content/10.1101/2024.789012.full.pdf"
        landing = self.crawler._transform_pdf_to_landing_page(pdf_url)

        self.assertEqual(landing, "https://medrxiv.org/content/10.1101/2024.789012")

    def test_transform_other_pdf_url(self):
        """Test that non-arXiv/bioRxiv URLs are returned as-is."""
        pdf_url = "https://example.com/paper.pdf"
        landing = self.crawler._transform_pdf_to_landing_page(pdf_url)

        self.assertEqual(landing, pdf_url)


if __name__ == "__main__":
    unittest.main()
