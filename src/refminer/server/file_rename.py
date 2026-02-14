from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException

from refminer.ingest.incremental import (
    _file_lock,
    full_ingest_single_file,
    load_all_chunks,
    remove_file_from_index,
)
from refminer.ingest.manifest import load_manifest
from refminer.index.vectors import build_vectors, save_vectors
from refminer.server.globals import get_bank_paths, project_manager
from refminer.server.utils import resolve_rel_path

_RESERVED_WINDOWS_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}


@dataclass
class RenameFileResult:
    old_rel_path: str
    new_rel_path: str
    removed_chunks: int


def _validate_new_name(old_file: Path, new_name: str) -> str:
    candidate = (new_name or "").strip()
    if not candidate:
        raise HTTPException(status_code=400, detail="new_name must not be empty")
    if "/" in candidate or "\\" in candidate:
        raise HTTPException(status_code=400, detail="new_name must be a filename only")
    if ".." in candidate:
        raise HTTPException(status_code=400, detail="new_name must not contain '..'")

    name_path = Path(candidate)
    if name_path.name != candidate:
        raise HTTPException(status_code=400, detail="new_name must be a filename only")

    old_suffix = old_file.suffix
    new_suffix = name_path.suffix
    if old_suffix.lower() != new_suffix.lower():
        raise HTTPException(
            status_code=400,
            detail=f"new_name must keep suffix '{old_suffix}'",
        )

    if re.search(r"[<>:\"/\\|?*]", candidate) is not None:
        raise HTTPException(status_code=400, detail="new_name contains invalid characters")
    if any(ord(ch) < 32 for ch in candidate):
        raise HTTPException(status_code=400, detail="new_name contains control characters")
    if candidate.endswith(" ") or candidate.endswith("."):
        raise HTTPException(status_code=400, detail="new_name cannot end with space or dot")

    stem_upper = name_path.stem.upper()
    if stem_upper in _RESERVED_WINDOWS_NAMES:
        raise HTTPException(status_code=400, detail="new_name uses a reserved device name")

    return candidate


def _rename_file_with_case_support(old_file_path: Path, new_file_path: Path) -> None:
    case_only = (
        old_file_path.name != new_file_path.name
        and old_file_path.name.lower() == new_file_path.name.lower()
    )
    if case_only:
        temp_path = old_file_path.with_name(
            f"{old_file_path.stem}.__rename_tmp__{uuid.uuid4().hex}{old_file_path.suffix}"
        )
        old_file_path.rename(temp_path)
        temp_path.rename(new_file_path)
        return
    old_file_path.rename(new_file_path)


def _paths_refer_same_file(first_path: Path, second_path: Path) -> bool:
    try:
        return first_path.samefile(second_path)
    except OSError:
        return False


def _rebuild_vectors_if_needed(vectors_existed: bool, index_dir: Path) -> None:
    if not vectors_existed:
        return

    chunks = load_all_chunks(index_dir=index_dir)
    if not chunks:
        return

    try:
        vector_index = build_vectors(chunks)
        save_vectors(vector_index, index_dir / "vectors.faiss")
    except RuntimeError:
        return


def rename_file_on_disk_and_reindex(old_rel_path: str, new_name: str) -> RenameFileResult:
    references_dir, index_dir = get_bank_paths()
    resolved_old_rel_path = resolve_rel_path(old_rel_path)
    old_rel_path_obj = Path(resolved_old_rel_path)
    old_file_path = references_dir / old_rel_path_obj

    if not old_file_path.exists() or not old_file_path.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {resolved_old_rel_path}")

    validated_new_name = _validate_new_name(old_file_path, new_name)
    new_rel_path = str(old_rel_path_obj.with_name(validated_new_name))
    if new_rel_path == resolved_old_rel_path:
        raise HTTPException(status_code=400, detail="new_name is identical to current name")

    new_file_path = references_dir / new_rel_path
    lock_path = index_dir / ".rename.lock"

    with _file_lock(lock_path):
        if not old_file_path.exists() or not old_file_path.is_file():
            raise HTTPException(
                status_code=404, detail=f"File not found: {resolved_old_rel_path}"
            )

        if new_file_path.exists() and not _paths_refer_same_file(old_file_path, new_file_path):
            raise HTTPException(status_code=409, detail=f"File already exists: {new_rel_path}")

        vectors_existed_at_start = (index_dir / "vectors.faiss").exists()

        manifest = load_manifest(index_dir=index_dir)
        old_manifest_entry = next(
            (entry for entry in manifest if entry.rel_path == resolved_old_rel_path), None
        )
        preserved_bibliography = (
            old_manifest_entry.bibliography
            if old_manifest_entry and old_manifest_entry.bibliography is not None
            else None
        )

        removed_chunks = remove_file_from_index(
            resolved_old_rel_path,
            index_dir=index_dir,
            references_dir=references_dir,
        )

        rename_applied = False
        try:
            _rename_file_with_case_support(old_file_path, new_file_path)
            rename_applied = True

            ingested = full_ingest_single_file(
                new_file_path,
                references_dir=references_dir,
                index_dir=index_dir,
                build_vectors=False,
                bibliography=preserved_bibliography,
            )

            project_manager.replace_file_in_all_projects(
                resolved_old_rel_path, ingested.rel_path
            )
            _rebuild_vectors_if_needed(vectors_existed_at_start, index_dir)
        except Exception as exc:
            rollback_errors: list[str] = []

            if rename_applied and new_file_path.exists():
                try:
                    _rename_file_with_case_support(new_file_path, old_file_path)
                except Exception as rollback_exc:
                    rollback_errors.append(f"failed to rename back: {rollback_exc}")

            try:
                full_ingest_single_file(
                    old_file_path,
                    references_dir=references_dir,
                    index_dir=index_dir,
                    build_vectors=False,
                    bibliography=preserved_bibliography,
                )
            except Exception as rollback_exc:
                rollback_errors.append(f"failed to reindex original file: {rollback_exc}")

            if rollback_errors:
                details = "; ".join(rollback_errors)
                raise RuntimeError(
                    f"Rename failed and rollback was incomplete: {details}"
                ) from exc
            raise

    return RenameFileResult(
        old_rel_path=resolved_old_rel_path,
        new_rel_path=ingested.rel_path,
        removed_chunks=removed_chunks,
    )
