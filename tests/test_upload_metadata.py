import sys
import unittest
import tempfile
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refminer.ingest.incremental import ingest_single_file, full_ingest_single_file


class TestUploadMetadata(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.references_dir = self.temp_dir / "references"
        self.references_dir.mkdir(parents=True)
        self.index_dir = self.temp_dir / "index"
        self.index_dir.mkdir(parents=True)

    def tearDown(self):
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def _create_minimal_pdf(self, title: str = "Test PDF") -> Path:
        import fitz

        pdf_path = self.references_dir / "test.pdf"
        doc = fitz.open()
        doc.insert_page(0, text=f"{title}\n\nTest content for metadata testing.")
        doc.save(str(pdf_path))
        doc.close()
        return pdf_path

    def _create_sample_bibliography(self) -> dict:
        return {
            "title": "Test Paper Title",
            "authors": [{"literal": "John Doe"}, {"literal": "Jane Smith"}],
            "year": 2024,
            "doi": "10.1234/test.5678",
            "abstract": "This is a test abstract.",
            "journal": "Test Journal",
            "volume": "10",
            "issue": "2",
            "pages": "123-145",
            "citation_count": 42,
            "extraction": "crawler_pre_fetched",
        }

    def test_ingest_single_file_with_bibliography(self):
        pdf_path = self._create_minimal_pdf()
        bibliography = self._create_sample_bibliography()

        entry, chunks = ingest_single_file(
            pdf_path,
            references_dir=self.references_dir,
            bibliography=bibliography,
        )

        self.assertIsNotNone(entry)
        self.assertEqual(entry.bibliography, bibliography)
        self.assertEqual(entry.bibliography.get("title"), "Test Paper Title")
        self.assertEqual(entry.bibliography.get("year"), 2024)
        self.assertEqual(entry.bibliography.get("doi"), "10.1234/test.5678")

    def test_ingest_single_file_without_bibliography(self):
        pdf_path = self._create_minimal_pdf()

        entry, chunks = ingest_single_file(
            pdf_path,
            references_dir=self.references_dir,
            bibliography=None,
        )

        self.assertIsNotNone(entry)
        self.assertIsNotNone(entry.bibliography)

    def test_ingest_single_file_with_empty_bibliography(self):
        pdf_path = self._create_minimal_pdf()
        bibliography = {}

        entry, chunks = ingest_single_file(
            pdf_path,
            references_dir=self.references_dir,
            bibliography=bibliography,
        )

        self.assertIsNotNone(entry)
        self.assertIsNotNone(entry.bibliography)
        self.assertIsNotNone(entry.title)

    def test_ingest_single_file_with_partial_bibliography(self):
        pdf_path = self._create_minimal_pdf()
        bibliography = {
            "title": "Partial Title",
            "authors": [{"literal": "Single Author"}],
        }

        entry, chunks = ingest_single_file(
            pdf_path,
            references_dir=self.references_dir,
            bibliography=bibliography,
        )

        self.assertIsNotNone(entry)
        self.assertEqual(entry.bibliography.get("title"), "Partial Title")
        self.assertEqual(len(entry.bibliography.get("authors", [])), 1)

    def test_full_ingest_single_file_with_bibliography(self):
        pdf_path = self._create_minimal_pdf()
        bibliography = self._create_sample_bibliography()

        entry = full_ingest_single_file(
            pdf_path,
            references_dir=self.references_dir,
            index_dir=self.index_dir,
            build_vectors=False,
            bibliography=bibliography,
        )

        self.assertIsNotNone(entry)
        self.assertEqual(entry.bibliography, bibliography)
        self.assertEqual(entry.bibliography.get("extraction"), "crawler_pre_fetched")

    def test_full_ingest_single_file_without_bibliography(self):
        pdf_path = self._create_minimal_pdf()

        entry = full_ingest_single_file(
            pdf_path,
            references_dir=self.references_dir,
            index_dir=self.index_dir,
            build_vectors=False,
            bibliography=None,
        )

        self.assertIsNotNone(entry)
        self.assertIsNotNone(entry.bibliography)

    def test_bibliography_authors_format(self):
        pdf_path = self._create_minimal_pdf()
        bibliography = {
            "title": "Authors Test",
            "authors": [
                {"literal": "Author One"},
                {"literal": "Author Two"},
                {"literal": "Author Three"},
            ],
            "year": 2024,
        }

        entry, chunks = ingest_single_file(
            pdf_path,
            references_dir=self.references_dir,
            bibliography=bibliography,
        )

        self.assertIsNotNone(entry)
        authors = entry.bibliography.get("authors", [])
        self.assertEqual(len(authors), 3)
        self.assertEqual(authors[0]["literal"], "Author One")
        self.assertEqual(authors[1]["literal"], "Author Two")
        self.assertEqual(authors[2]["literal"], "Author Three")

    def test_bibliography_with_none_values(self):
        pdf_path = self._create_minimal_pdf()
        bibliography = {
            "title": "Test Title",
            "authors": None,
            "year": None,
            "doi": "10.1234/test",
        }

        entry, chunks = ingest_single_file(
            pdf_path,
            references_dir=self.references_dir,
            bibliography=bibliography,
        )

        self.assertIsNotNone(entry)
        self.assertEqual(entry.bibliography.get("title"), "Test Title")
        self.assertEqual(entry.bibliography.get("doi"), "10.1234/test")
        self.assertIsNone(entry.bibliography.get("authors"))
        self.assertIsNone(entry.bibliography.get("year"))

    def test_bibliography_overrides_extraction(self):
        pdf_path = self._create_minimal_pdf()
        bibliography = {
            "title": "Provided Title",
            "year": 2024,
            "extraction": "custom_source",
        }

        entry, chunks = ingest_single_file(
            pdf_path,
            references_dir=self.references_dir,
            bibliography=bibliography,
        )

        self.assertIsNotNone(entry)
        self.assertEqual(entry.bibliography.get("title"), "Provided Title")
        self.assertEqual(entry.bibliography.get("extraction"), "custom_source")


if __name__ == "__main__":
    unittest.main()
