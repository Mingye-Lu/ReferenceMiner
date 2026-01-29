from __future__ import annotations

from pathlib import Path

DEFAULT_REFERENCES_DIR = "references"
DEFAULT_INDEX_DIR = ".index"


def find_project_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for parent in [current, *current.parents]:
        if (parent / DEFAULT_REFERENCES_DIR).exists():
            return parent
    return current


def get_references_dir(root: Path | None = None) -> Path:
    base = root or find_project_root()
    return base / DEFAULT_REFERENCES_DIR


def get_index_dir(root: Path | None = None) -> Path:
    base = root or find_project_root()
    return base / DEFAULT_INDEX_DIR
