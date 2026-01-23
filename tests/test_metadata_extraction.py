import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refminer.ingest.bibliography import extract_pdf_bibliography, merge_bibliography


class TestMetadataExtraction(unittest.TestCase):
    def test_extract_pdf_bibliography_basic(self):
        text_blocks = [
            "Deep Learning for Widgets\n"
            "Alice Smith, Bob Lee\n"
            "Abstract\n"
            "We study widgets in 2021.\n"
            "doi: 10.1234/ABC.DEF.5678\n"
            "Journal of Widget Research",
            "More content here."
        ]
        result = extract_pdf_bibliography(text_blocks, title=None)
        self.assertIsNotNone(result)
        self.assertEqual(result.get("title"), "Deep Learning for Widgets")
        self.assertEqual(result.get("year"), 2021)
        self.assertEqual(result.get("doi"), "10.1234/ABC.DEF.5678")
        self.assertEqual(result.get("doi_status"), "extracted")
        authors = result.get("authors") or []
        self.assertEqual(len(authors), 2)
        self.assertEqual(authors[0].get("literal"), "Alice Smith")
        self.assertEqual(authors[1].get("literal"), "Bob Lee")

    def test_merge_bibliography_preserves_existing(self):
        existing = {
            "title": "Existing Title",
            "authors": [{"literal": "Existing Author"}],
            "year": 2020,
        }
        extracted = {
            "title": "New Title",
            "authors": [{"literal": "New Author"}],
            "year": 2021,
            "doi": "10.5555/12345678",
        }
        merged = merge_bibliography(existing, extracted)
        self.assertEqual(merged.get("title"), "Existing Title")
        self.assertEqual(merged.get("year"), 2020)
        self.assertEqual(merged.get("doi"), "10.5555/12345678")
        authors = merged.get("authors") or []
        self.assertEqual(len(authors), 1)
        self.assertEqual(authors[0].get("literal"), "Existing Author")


if __name__ == "__main__":
    unittest.main()
