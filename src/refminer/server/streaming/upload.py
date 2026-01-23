"""Upload streaming logic for file ingestion."""
from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Iterator, Optional

from fastapi import UploadFile

from refminer.ingest.incremental import full_ingest_single_file, remove_file_from_index
from refminer.ingest.manifest import SUPPORTED_EXTENSIONS
from refminer.ingest.registry import load_registry, check_duplicate, register_file, save_registry
from refminer.utils.hashing import sha256_file
from refminer.server.globals import project_manager, get_bank_paths
from refminer.server.utils import sse, get_temp_dir, load_manifest_entries

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB


def stream_upload(
    project_id: Optional[str],
    file: UploadFile,
    replace_existing: bool = False,
    select_in_project: bool = True,
) -> Iterator[str]:
    """Stream file upload with SSE progress events."""
    # Check file extension
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        yield sse("error", {"code": "UNSUPPORTED_TYPE", "message": f"Unsupported file type: {suffix}"})
        return

    temp_dir = get_temp_dir()
    temp_path = temp_dir / f"upload_{int(time.time() * 1000)}{suffix}"

    try:
        yield sse("progress", {"phase": "uploading", "percent": 0})

        # Stream file to temp location
        total_size = 0
        with temp_path.open("wb") as f:
            while chunk := file.file.read(64 * 1024):  # 64KB chunks
                total_size += len(chunk)
                if total_size > MAX_FILE_SIZE:
                    yield sse("error", {"code": "FILE_TOO_LARGE", "message": f"File exceeds {MAX_FILE_SIZE // (1024*1024)}MB limit"})
                    return
                f.write(chunk)

        yield sse("progress", {"phase": "hashing", "percent": 50})

        # Compute SHA256
        file_hash = sha256_file(temp_path)

        yield sse("progress", {"phase": "checking_duplicate", "percent": 60})

        # Check for duplicates
        references_dir, index_dir = get_bank_paths()
        registry = load_registry(index_dir=index_dir)
        existing_path = check_duplicate(file_hash, registry)
        reuse_existing = False

        final_name = file.filename or f"file{suffix}"
        candidate_path = references_dir / final_name
        if not existing_path and candidate_path.exists():
            try:
                candidate_hash = sha256_file(candidate_path)
            except Exception:
                candidate_hash = None
            if candidate_hash == file_hash:
                existing_path = str(candidate_path.relative_to(references_dir))
                reuse_existing = True

        if existing_path and not replace_existing and not reuse_existing:
            yield sse("duplicate", {"sha256": file_hash, "existing_path": existing_path})
            return

        yield sse("progress", {"phase": "storing", "percent": 70})

        # Determine final path
        references_dir.mkdir(parents=True, exist_ok=True)

        # Handle name collisions (unless replacing)
        if existing_path and replace_existing:
            final_path = references_dir / existing_path
            # Remove old file from index first
            remove_file_from_index(existing_path, index_dir=index_dir, references_dir=references_dir)
        elif reuse_existing:
            final_path = references_dir / existing_path
        else:
            final_path = references_dir / final_name
            counter = 1
            while final_path.exists():
                stem = Path(final_name).stem
                final_path = references_dir / f"{stem}_{counter}{suffix}"
                counter += 1

        # Move file to references (unless already there)
        if not reuse_existing:
            shutil.move(str(temp_path), str(final_path))

        yield sse("progress", {"phase": "extracting", "percent": 80})

        # Process the file
        try:
            entry = None
            if reuse_existing and not replace_existing:
                manifest = load_manifest_entries()
                entry = next((e for e in manifest if e.rel_path == existing_path), None)
                if entry is None:
                    entry = full_ingest_single_file(final_path, references_dir=references_dir, index_dir=index_dir, build_vectors=True)
                else:
                    register_file(existing_path, file_hash, registry)
                    save_registry(registry, index_dir=index_dir, references_dir=references_dir)
            else:
                entry = full_ingest_single_file(final_path, references_dir=references_dir, index_dir=index_dir, build_vectors=True)
        except Exception as e:
            # Clean up on processing failure
            if final_path.exists():
                final_path.unlink()
            yield sse("error", {"code": "EXTRACTION_ERROR", "message": str(e)})
            return

        yield sse("progress", {"phase": "indexing", "percent": 95})

        # Return complete response
        manifest_entry = {
            "rel_path": entry.rel_path,
            "file_type": entry.file_type,
            "title": entry.title,
            "abstract": entry.abstract,
            "page_count": entry.page_count,
            "size_bytes": entry.size_bytes,
            "bibliography": entry.bibliography,
        }
        status_value = "replaced" if existing_path and replace_existing else ("reused" if reuse_existing else "processed")

        if select_in_project and project_id:
            project_manager.add_selected_files(project_id, [entry.rel_path])

        yield sse("complete", {
            "rel_path": entry.rel_path,
            "sha256": entry.sha256,
            "status": status_value,
            "manifest_entry": manifest_entry,
        })

    except Exception as e:
        yield sse("error", {"code": "UPLOAD_ERROR", "message": str(e)})
    finally:
        # Cleanup temp file
        if temp_path.exists():
            temp_path.unlink()
