# pyright: reportUninitializedInstanceVariable=false

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fastapi import HTTPException

from refminer.ingest.incremental import full_ingest_single_file
from refminer.ingest.manifest import load_manifest
from refminer.projects.manager import ProjectManager
from refminer.server import file_rename as file_rename_module
from refminer.server.file_rename import rename_file_on_disk_and_reindex


class TestFileRename(unittest.TestCase):
    temp_dir: Path
    references_dir: Path
    index_dir: Path
    project_manager: ProjectManager

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.references_dir = self.temp_dir / "references"
        self.index_dir = self.temp_dir / ".index"
        self.references_dir.mkdir(parents=True)
        self.index_dir.mkdir(parents=True)
        self.project_manager = ProjectManager(str(self.temp_dir))

    def tearDown(self) -> None:
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def _create_pdf(self, rel_path: str, text: str) -> Path:
        import fitz

        file_path = self.references_dir / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        doc = fitz.open()
        doc.insert_page(0, text=text)
        doc.save(str(file_path))
        doc.close()
        return file_path

    def _read_chunk_paths(self) -> list[str]:
        chunks_path = self.index_dir / "chunks.jsonl"
        if not chunks_path.exists():
            return []
        paths: list[str] = []
        with chunks_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                item = json.loads(line)
                paths.append(item.get("path", ""))
        return paths

    def test_rename_updates_disk_indexes_and_projects(self) -> None:
        old_rel_path = "nested/old_name.pdf"
        normalized_old_rel_path = str(Path(old_rel_path))
        old_file = self._create_pdf(old_rel_path, "Old file body")
        bibliography = {
            "title": "Preserved Bib",
            "authors": [{"literal": "A. Author"}],
            "year": 2025,
        }
        full_ingest_single_file(
            old_file,
            references_dir=self.references_dir,
            index_dir=self.index_dir,
            build_vectors=False,
            bibliography=bibliography,
        )

        self.project_manager.set_selected_files("default", [normalized_old_rel_path])
        project_two = self.project_manager.create_project("Second")
        self.project_manager.set_selected_files(project_two.id, [normalized_old_rel_path])

        with (
            patch(
                "refminer.server.file_rename.get_bank_paths",
                return_value=(self.references_dir, self.index_dir),
            ),
            patch(
                "refminer.server.file_rename.resolve_rel_path",
                return_value=normalized_old_rel_path,
            ),
            patch("refminer.server.file_rename.project_manager", self.project_manager),
        ):
            result = rename_file_on_disk_and_reindex(old_rel_path, "new_name.pdf")

        new_rel_path = str(Path("nested") / "new_name.pdf")
        self.assertEqual(result.old_rel_path, normalized_old_rel_path)
        self.assertEqual(result.new_rel_path, new_rel_path)
        self.assertFalse((self.references_dir / normalized_old_rel_path).exists())
        self.assertTrue((self.references_dir / new_rel_path).exists())

        manifest = load_manifest(index_dir=self.index_dir)
        rel_paths = [entry.rel_path for entry in manifest]
        self.assertNotIn(normalized_old_rel_path, rel_paths)
        self.assertIn(new_rel_path, rel_paths)
        new_entry = next(entry for entry in manifest if entry.rel_path == new_rel_path)
        self.assertEqual(new_entry.bibliography, bibliography)

        chunk_paths = self._read_chunk_paths()
        self.assertTrue(chunk_paths)
        self.assertEqual(set(chunk_paths), {new_rel_path})

        self.assertEqual(
            self.project_manager.get_selected_files("default"),
            [new_rel_path],
        )
        self.assertEqual(
            self.project_manager.get_selected_files(project_two.id),
            [new_rel_path],
        )

    def test_rename_rejects_collision(self) -> None:
        old_rel_path = "a.pdf"
        old_file = self._create_pdf(old_rel_path, "A")
        full_ingest_single_file(
            old_file,
            references_dir=self.references_dir,
            index_dir=self.index_dir,
            build_vectors=False,
            bibliography={"title": "A"},
        )

        colliding_rel_path = "b.pdf"
        colliding_file = self._create_pdf(colliding_rel_path, "B")
        full_ingest_single_file(
            colliding_file,
            references_dir=self.references_dir,
            index_dir=self.index_dir,
            build_vectors=False,
            bibliography={"title": "B"},
        )

        with (
            patch(
                "refminer.server.file_rename.get_bank_paths",
                return_value=(self.references_dir, self.index_dir),
            ),
            patch(
                "refminer.server.file_rename.resolve_rel_path",
                return_value=str(Path(old_rel_path)),
            ),
            patch("refminer.server.file_rename.project_manager", self.project_manager),
        ):
            with self.assertRaises(HTTPException) as ctx:
                rename_file_on_disk_and_reindex(old_rel_path, "b.pdf")

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertTrue((self.references_dir / old_rel_path).exists())
        self.assertTrue((self.references_dir / colliding_rel_path).exists())

    def test_rename_rejects_invalid_names(self) -> None:
        old_rel_path = "paper.pdf"
        old_file = self._create_pdf(old_rel_path, "Body")
        full_ingest_single_file(
            old_file,
            references_dir=self.references_dir,
            index_dir=self.index_dir,
            build_vectors=False,
            bibliography={"title": "Body"},
        )

        invalid_names = [
            "../paper.pdf",
            "folder/paper.pdf",
            "NUL.pdf",
            "bad?.pdf",
            "paper.txt",
        ]

        with (
            patch(
                "refminer.server.file_rename.get_bank_paths",
                return_value=(self.references_dir, self.index_dir),
            ),
            patch(
                "refminer.server.file_rename.resolve_rel_path",
                return_value=str(Path(old_rel_path)),
            ),
            patch("refminer.server.file_rename.project_manager", self.project_manager),
        ):
            for name in invalid_names:
                with self.subTest(name=name):
                    with self.assertRaises(HTTPException) as ctx:
                        rename_file_on_disk_and_reindex(old_rel_path, name)
                    self.assertEqual(ctx.exception.status_code, 400)

        self.assertTrue((self.references_dir / old_rel_path).exists())

    def test_case_only_rename(self) -> None:
        old_rel_path = "Paper.pdf"
        old_file = self._create_pdf(old_rel_path, "Case")
        full_ingest_single_file(
            old_file,
            references_dir=self.references_dir,
            index_dir=self.index_dir,
            build_vectors=False,
            bibliography={"title": "Case"},
        )

        with (
            patch(
                "refminer.server.file_rename.get_bank_paths",
                return_value=(self.references_dir, self.index_dir),
            ),
            patch(
                "refminer.server.file_rename.resolve_rel_path",
                return_value=str(Path(old_rel_path)),
            ),
            patch("refminer.server.file_rename.project_manager", self.project_manager),
        ):
            result = rename_file_on_disk_and_reindex(old_rel_path, "paper.pdf")

        self.assertEqual(result.new_rel_path, str(Path("paper.pdf")))
        self.assertTrue((self.references_dir / "paper.pdf").exists())
        manifest = load_manifest(index_dir=self.index_dir)
        self.assertEqual({entry.rel_path for entry in manifest}, {str(Path("paper.pdf"))})

    def test_case_only_rename_rejects_distinct_existing_target(self) -> None:
        old_rel_path = "Paper.pdf"
        old_file = self._create_pdf(old_rel_path, "Old")
        full_ingest_single_file(
            old_file,
            references_dir=self.references_dir,
            index_dir=self.index_dir,
            build_vectors=False,
            bibliography={"title": "Old"},
        )

        with (
            patch(
                "refminer.server.file_rename.get_bank_paths",
                return_value=(self.references_dir, self.index_dir),
            ),
            patch(
                "refminer.server.file_rename.resolve_rel_path",
                return_value=str(Path(old_rel_path)),
            ),
            patch("refminer.server.file_rename.project_manager", self.project_manager),
            patch("refminer.server.file_rename.Path.exists", return_value=True),
            patch("refminer.server.file_rename._paths_refer_same_file", return_value=False),
        ):
            with self.assertRaises(HTTPException) as ctx:
                rename_file_on_disk_and_reindex(old_rel_path, "paper.pdf")

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertTrue((self.references_dir / old_rel_path).exists())

    def test_rollback_restores_old_file_and_index_when_ingest_fails(self) -> None:
        old_rel_path = str(Path("nested") / "rollback.pdf")
        old_file = self._create_pdf(old_rel_path, "Rollback body")
        bibliography = {"title": "Rollback Bib"}
        full_ingest_single_file(
            old_file,
            references_dir=self.references_dir,
            index_dir=self.index_dir,
            build_vectors=False,
            bibliography=bibliography,
        )

        call_count = {"count": 0}
        real_ingest = full_ingest_single_file

        def fail_once_ingest(*args, **kwargs):
            call_count["count"] += 1
            if call_count["count"] == 1:
                raise RuntimeError("forced ingest failure")
            return real_ingest(*args, **kwargs)

        with (
            patch(
                "refminer.server.file_rename.get_bank_paths",
                return_value=(self.references_dir, self.index_dir),
            ),
            patch(
                "refminer.server.file_rename.resolve_rel_path",
                return_value=old_rel_path,
            ),
            patch("refminer.server.file_rename.project_manager", self.project_manager),
            patch.object(file_rename_module, "full_ingest_single_file", side_effect=fail_once_ingest),
        ):
            with self.assertRaises(RuntimeError):
                rename_file_on_disk_and_reindex(old_rel_path, "rolled.pdf")

        old_path = self.references_dir / old_rel_path
        new_path = self.references_dir / str(Path("nested") / "rolled.pdf")
        self.assertTrue(old_path.exists())
        self.assertFalse(new_path.exists())

        manifest = load_manifest(index_dir=self.index_dir)
        manifest_paths = {entry.rel_path for entry in manifest}
        self.assertEqual(manifest_paths, {old_rel_path})
        old_entry = next(entry for entry in manifest if entry.rel_path == old_rel_path)
        self.assertEqual(old_entry.bibliography, bibliography)

        chunk_paths = self._read_chunk_paths()
        self.assertEqual(set(chunk_paths), {old_rel_path})

    def test_rebuild_vectors_when_vectors_existed_at_start(self) -> None:
        old_rel_path = "vec_old.pdf"
        old_file = self._create_pdf(old_rel_path, "Vector source")
        full_ingest_single_file(
            old_file,
            references_dir=self.references_dir,
            index_dir=self.index_dir,
            build_vectors=False,
            bibliography={"title": "Vector source"},
        )
        (self.index_dir / "vectors.faiss").write_bytes(b"placeholder")

        chunks = [("c1", "text one"), ("c2", "text two")]
        fake_vector_index = object()

        with (
            patch(
                "refminer.server.file_rename.get_bank_paths",
                return_value=(self.references_dir, self.index_dir),
            ),
            patch(
                "refminer.server.file_rename.resolve_rel_path",
                return_value=str(Path(old_rel_path)),
            ),
            patch("refminer.server.file_rename.project_manager", self.project_manager),
            patch("refminer.server.file_rename.load_all_chunks", return_value=chunks),
            patch("refminer.server.file_rename.build_vectors", return_value=fake_vector_index) as build_mock,
            patch("refminer.server.file_rename.save_vectors") as save_mock,
        ):
            rename_file_on_disk_and_reindex(old_rel_path, "vec_new.pdf")

        build_mock.assert_called_once_with(chunks)
        save_mock.assert_called_once_with(fake_vector_index, self.index_dir / "vectors.faiss")

    def test_does_not_rebuild_vectors_when_vectors_missing_at_start(self) -> None:
        old_rel_path = "no_vec_old.pdf"
        old_file = self._create_pdf(old_rel_path, "No vector source")
        full_ingest_single_file(
            old_file,
            references_dir=self.references_dir,
            index_dir=self.index_dir,
            build_vectors=False,
            bibliography={"title": "No vector source"},
        )

        with (
            patch(
                "refminer.server.file_rename.get_bank_paths",
                return_value=(self.references_dir, self.index_dir),
            ),
            patch(
                "refminer.server.file_rename.resolve_rel_path",
                return_value=str(Path(old_rel_path)),
            ),
            patch("refminer.server.file_rename.project_manager", self.project_manager),
            patch("refminer.server.file_rename.build_vectors") as build_mock,
            patch("refminer.server.file_rename.save_vectors") as save_mock,
        ):
            rename_file_on_disk_and_reindex(old_rel_path, "no_vec_new.pdf")

        build_mock.assert_not_called()
        save_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
