from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from refminer.utils.hashing import sha256_file
from refminer.utils.paths import get_index_dir, get_references_dir


SUPPORTED_EXTENSIONS = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".txt": "text",
    ".md": "text",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".csv": "table",
    ".xlsx": "table",
}


@dataclass
class ManifestEntry:
    path: str
    rel_path: str
    file_type: str
    size_bytes: int
    modified_time: float
    sha256: str
    title: str | None = None
    abstract: str | None = None
    page_count: int | None = None


def iter_reference_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_file():
            yield path


def detect_type(path: Path) -> str | None:
    return SUPPORTED_EXTENSIONS.get(path.suffix.lower())


def build_manifest(root: Path | None = None) -> list[ManifestEntry]:
    references_dir = get_references_dir(root)
    entries: list[ManifestEntry] = []
    for path in iter_reference_files(references_dir):
        file_type = detect_type(path)
        if not file_type:
            continue
        stat = path.stat()
        entries.append(
            ManifestEntry(
                path=str(path),
                rel_path=str(path.relative_to(references_dir)),
                file_type=file_type,
                size_bytes=stat.st_size,
                modified_time=stat.st_mtime,
                sha256=sha256_file(path),
            )
        )
    return entries


def write_manifest(entries: list[ManifestEntry], root: Path | None = None) -> Path:
    index_dir = get_index_dir(root)
    index_dir.mkdir(parents=True, exist_ok=True)
    output_path = index_dir / "manifest.json"
    payload = [asdict(entry) for entry in entries]
    output_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    return output_path


def load_manifest(root: Path | None = None) -> list[ManifestEntry]:
    index_dir = get_index_dir(root)
    manifest_path = index_dir / "manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    return [ManifestEntry(**item) for item in data]
