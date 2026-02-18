import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refminer.index.references import ReferenceRecord, upsert_reference_records
from refminer.ingest.manifest import ManifestEntry
from refminer.server import app
from refminer.utils.hashing import sha256_file


class TestFileReferencesApi(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.references_dir = self.temp_dir / "references"
        self.references_dir.mkdir(parents=True)
        self.index_dir = self.temp_dir / ".index"
        self.index_dir.mkdir(parents=True)

        import fitz

        self.rel_path = "cached.pdf"
        self.file_path = self.references_dir / self.rel_path
        doc = fitz.open()
        doc.insert_page(0, text="Cached document")
        doc.save(str(self.file_path))
        doc.close()
        self.sha256 = sha256_file(self.file_path)

    def tearDown(self) -> None:
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_references_endpoint_uses_cached_records_without_reextract(self) -> None:
        entry = ManifestEntry(
            path=str(self.file_path),
            rel_path=self.rel_path,
            file_type="pdf",
            size_bytes=self.file_path.stat().st_size,
            modified_time=self.file_path.stat().st_mtime,
            sha256=self.sha256,
        )
        upsert_reference_records(
            source_rel_path=self.rel_path,
            records=[
                ReferenceRecord(
                    source_rel_path=self.rel_path,
                    source_sha256=self.sha256,
                    source_file_type="pdf",
                    ref_number=1,
                    raw_text='[1] Cached Ref, "Title"',
                    title="Cached Ref Title",
                    availability="searchable",
                    source_type="text",
                    extracted_at=1.0,
                )
            ],
            index_dir=self.index_dir,
        )

        with (
            patch(
                "refminer.server.routes.files.get_bank_paths",
                return_value=(self.references_dir, self.index_dir),
            ),
            patch(
                "refminer.server.routes.files.resolve_rel_path",
                return_value=self.rel_path,
            ),
            patch(
                "refminer.server.routes.files.load_manifest_entries",
                return_value=[entry],
            ),
            patch(
                "refminer.server.routes.files.extract_document",
                side_effect=AssertionError("should not re-extract"),
            ),
            TestClient(app) as client,
        ):
            response = client.get(f"/api/files/{self.rel_path}/references")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["references"]), 1)
        self.assertEqual(data["references"][0]["title"], "Cached Ref Title")


if __name__ == "__main__":
    unittest.main()
