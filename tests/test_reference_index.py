import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refminer.index.references import load_reference_records_for_file
from refminer.ingest.incremental import full_ingest_single_file, remove_file_from_index


class TestReferenceIndex(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.references_dir = self.temp_dir / "references"
        self.references_dir.mkdir(parents=True)
        self.index_dir = self.temp_dir / ".index"
        self.index_dir.mkdir(parents=True)

    def tearDown(self) -> None:
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def _create_pdf_with_references(self) -> Path:
        import fitz

        path = self.references_dir / "paper.pdf"
        doc = fitz.open()
        doc.insert_page(
            0,
            text=(
                "A Test Paper\n\n"
                "Body text\n\n"
                "REFERENCES\n"
                '[1] A. Author, "First Study", 2021. doi:10.1234/ABC.DEF\n'
                '[2] B. Author, "Second Study", 2020. https://example.org/paper\n'
            ),
        )
        doc.save(str(path))
        doc.close()
        return path

    def test_full_ingest_persists_references_and_remove_cleans_them(self) -> None:
        pdf_path = self._create_pdf_with_references()

        entry = full_ingest_single_file(
            pdf_path,
            references_dir=self.references_dir,
            index_dir=self.index_dir,
            build_vectors=False,
        )

        records = load_reference_records_for_file(
            source_rel_path=entry.rel_path,
            source_sha256=entry.sha256,
            index_dir=self.index_dir,
        )
        self.assertGreaterEqual(len(records), 1)
        self.assertEqual(records[0].source_rel_path, entry.rel_path)

        remove_file_from_index(
            entry.rel_path,
            references_dir=self.references_dir,
            index_dir=self.index_dir,
        )
        after = load_reference_records_for_file(
            source_rel_path=entry.rel_path,
            index_dir=self.index_dir,
        )
        self.assertEqual(after, [])


if __name__ == "__main__":
    unittest.main()
