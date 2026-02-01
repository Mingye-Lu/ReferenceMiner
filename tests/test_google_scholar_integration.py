"""Integration test for Google Scholar crawler with HTML samples."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refminer.crawler.engines.google_scholar import GoogleScholarCrawler
from refminer.crawler.models import SearchQuery


class TestGoogleScholarIntegration(unittest.TestCase):
    """Integration tests for Google Scholar crawler."""

    def setUp(self):
        """Set up test fixtures."""
        self.crawler = GoogleScholarCrawler()

    def test_parse_arxiv_pdf_result(self):
        """Test parsing arXiv result with PDF link."""
        html = """
        <div class="gs_r gs_or gs_scl">
            <div class="gs_ri gs_ggs gs_fl gs_res gs_bg">
                <h3 class="gs_rt">
                    <a href="https://arxiv.org/pdf/2412.19437">[PDF] arxiv.org</a>
                </h3>
                <div class="gs_a">John Doe - 2024 - arXiv</div>
            </div>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        
        result = self.crawler._parse_single_result(
            soup.find("div", class_="gs_r"),
            None,
            SearchQuery(query="test")
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result.title, "arxiv.org")
        self.assertEqual(result.url, "https://arxiv.org/abs/2412.19437")
        self.assertEqual(result.pdf_url, "https://arxiv.org/pdf/2412.19437")
        self.assertEqual(result.year, 2024)

    def test_parse_biorxiv_pdf_result(self):
        """Test parsing bioRxiv result with PDF link."""
        html = """
        <div class="gs_r gs_or gs_scl">
            <h3 class="gs_rt">
                <a href="https://biorxiv.org/content/10.1101/2024.123456.full.pdf">[PDF] bioRxiv</a>
            </h3>
            <div class="gs_a">Jane Smith - 2024 - bioRxiv</div>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        
        result = self.crawler._parse_single_result(
            soup.find("div", class_="gs_r"),
            None,
            SearchQuery(query="test")
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result.title, "bioRxiv")
        self.assertEqual(result.url, "https://biorxiv.org/content/10.1101/2024.123456")
        self.assertEqual(result.pdf_url, "https://biorxiv.org/content/10.1101/2024.123456.full.pdf")

    def test_parse_regular_result(self):
        """Test parsing regular result without PDF in title."""
        html = """
        <div class="gs_r gs_or gs_scl">
            <h3 class="gs_rt">
                <a href="https://example.com/paper">Regular Paper Title</a>
            </h3>
            <div class="gs_a">Author A, Author B - 2023 - Journal Name</div>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        
        result = self.crawler._parse_single_result(
            soup.find("div", class_="gs_r"),
            None,
            SearchQuery(query="test")
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result.title, "Regular Paper Title")
        self.assertEqual(result.url, "https://example.com/paper")
        self.assertIsNone(result.pdf_url)

    def test_parse_result_with_separate_pdf_link(self):
        """Test parsing result with separate PDF link."""
        html = """
        <div class="gs_r gs_or gs_scl">
            <h3 class="gs_rt">
                <a href="https://example.com/paper">Paper Title</a>
            </h3>
            <div class="gs_a">Author - 2024 - Journal</div>
            <a href="https://example.com/paper.pdf" class="gs_pdf">PDF</a>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        
        result = self.crawler._parse_single_result(
            soup.find("div", class_="gs_r"),
            None,
            SearchQuery(query="test")
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result.title, "Paper Title")
        self.assertEqual(result.url, "https://example.com/paper")
        self.assertEqual(result.pdf_url, "https://example.com/paper.pdf")


if __name__ == "__main__":
    unittest.main()
