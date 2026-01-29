"""Upload streaming logic for file ingestion."""

from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path
from typing import Iterator, Optional

from fastapi import UploadFile

from refminer.ingest.incremental import full_ingest_single_file, remove_file_from_index
from refminer.ingest.manifest import SUPPORTED_EXTENSIONS
from refminer.ingest.registry import (
    load_registry,
    check_duplicate,
    register_file,
    save_registry,
)
from refminer.utils.hashing import sha256_file
from refminer.server.globals import project_manager, get_bank_paths, queue_store
from refminer.server.utils import sse, get_temp_dir, load_manifest_entries

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB


def stream_upload(
    project_id: Optional[str],
    file: UploadFile,
    replace_existing: bool = False,
    select_in_project: bool = True,
) -> Iterator[str]:
    """Stream file upload with SSE progress events."""
    scope = "project" if project_id else "bank"
    job = queue_store.create_job(
        job_type="upload",
        scope=scope,
        project_id=project_id,
        name=file.filename or "file",
        status="pending",
        phase="uploading",
        progress=0,
    )
    job_id = job["id"]
    # Check file extension
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        message = f"Unsupported file type: {suffix}"
        queue_store.update_job(
            job_id, status="error", error=message, phase=None, progress=0
        )
        yield sse(
            "error", {"code": "UNSUPPORTED_TYPE", "message": message, "job_id": job_id}
        )
        return

    temp_dir = get_temp_dir()
    temp_path = temp_dir / f"upload_{int(time.time() * 1000)}{suffix}"

    try:
        logger.info(f"[Upload] job={job_id[:8]} phase=uploading progress=0")
        queue_store.update_job(
            job_id, status="uploading", phase="uploading", progress=0
        )
        yield sse("progress", {"phase": "uploading", "percent": 0, "job_id": job_id})

        file_size: Optional[int]
        try:
            file.file.seek(0, 2)
            file_size = file.file.tell()
            file.file.seek(0)
        except Exception:
            file_size = None

        # Stream file to temp location
        total_size = 0
        last_percent = 0
        with temp_path.open("wb") as f:
            while chunk := file.file.read(64 * 1024):  # 64KB chunks
                total_size += len(chunk)
                if total_size > MAX_FILE_SIZE:
                    message = f"File exceeds {MAX_FILE_SIZE // (1024*1024)}MB limit"
                    queue_store.update_job(
                        job_id, status="error", error=message, phase=None
                    )
                    yield sse(
                        "error",
                        {
                            "code": "FILE_TOO_LARGE",
                            "message": message,
                            "job_id": job_id,
                        },
                    )
                    return
                f.write(chunk)

                if file_size and file_size > 0:
                    percent = int((total_size / file_size) * 40)
                    percent = max(0, min(40, percent))
                    if percent != last_percent:
                        last_percent = percent
                        queue_store.update_job(
                            job_id,
                            status="uploading",
                            phase="uploading",
                            progress=percent,
                        )
                        yield sse(
                            "progress",
                            {
                                "phase": "uploading",
                                "percent": percent,
                                "job_id": job_id,
                            },
                        )

        if last_percent < 40:
            queue_store.update_job(
                job_id, status="uploading", phase="uploading", progress=40
            )
            yield sse(
                "progress", {"phase": "uploading", "percent": 40, "job_id": job_id}
            )

        logger.info(f"[Upload] job={job_id[:8]} phase=hashing progress=50")
        queue_store.update_job(
            job_id, status="processing", phase="hashing", progress=50
        )
        yield sse("progress", {"phase": "hashing", "percent": 50, "job_id": job_id})

        # Compute SHA256
        file_hash = sha256_file(temp_path)

        logger.info(f"[Upload] job={job_id[:8]} phase=checking_duplicate progress=60")
        queue_store.update_job(
            job_id, status="processing", phase="checking_duplicate", progress=60
        )
        yield sse(
            "progress", {"phase": "checking_duplicate", "percent": 60, "job_id": job_id}
        )

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
            queue_store.update_job(
                job_id,
                status="duplicate",
                duplicate_path=existing_path,
                progress=100,
                phase=None,
            )
            yield sse(
                "duplicate",
                {"sha256": file_hash, "existing_path": existing_path, "job_id": job_id},
            )
            return

        logger.info(f"[Upload] job={job_id[:8]} phase=storing progress=70")
        queue_store.update_job(
            job_id, status="processing", phase="storing", progress=70
        )
        yield sse("progress", {"phase": "storing", "percent": 70, "job_id": job_id})

        # Determine final path
        references_dir.mkdir(parents=True, exist_ok=True)

        # Handle name collisions (unless replacing)
        if existing_path and replace_existing:
            existing_rel_path = str(existing_path)
            final_path = references_dir / existing_rel_path
            # Remove old file from index first
            remove_file_from_index(
                existing_rel_path, index_dir=index_dir, references_dir=references_dir
            )
        elif reuse_existing:
            existing_rel_path = str(existing_path)
            final_path = references_dir / existing_rel_path
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

        logger.info(f"[Upload] job={job_id[:8]} phase=extracting progress=80")
        queue_store.update_job(
            job_id, status="processing", phase="extracting", progress=80
        )
        yield sse("progress", {"phase": "extracting", "percent": 80, "job_id": job_id})

        # Process the file
        try:
            entry = None
            if reuse_existing and not replace_existing:
                existing_rel_path = str(existing_path)
                manifest = load_manifest_entries()
                entry = next(
                    (e for e in manifest if e.rel_path == existing_rel_path), None
                )
                if entry is None:
                    entry = full_ingest_single_file(
                        final_path,
                        references_dir=references_dir,
                        index_dir=index_dir,
                        build_vectors=True,
                    )
                else:
                    register_file(existing_rel_path, file_hash, registry)
                    save_registry(
                        registry, index_dir=index_dir, references_dir=references_dir
                    )
            else:
                entry = full_ingest_single_file(
                    final_path,
                    references_dir=references_dir,
                    index_dir=index_dir,
                    build_vectors=True,
                )
        except Exception as e:
            # Clean up on processing failure - but NEVER delete reused files
            # Only delete files we just moved/created, not existing reference files
            if not reuse_existing and final_path.exists():
                final_path.unlink()
            message = str(e)
            queue_store.update_job(job_id, status="error", error=message, phase=None)
            yield sse(
                "error",
                {"code": "EXTRACTION_ERROR", "message": message, "job_id": job_id},
            )
            return

        logger.info(f"[Upload] job={job_id[:8]} phase=indexing progress=95")
        queue_store.update_job(
            job_id, status="processing", phase="indexing", progress=95
        )
        yield sse("progress", {"phase": "indexing", "percent": 95, "job_id": job_id})

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
        status_value = (
            "replaced"
            if existing_path and replace_existing
            else ("reused" if reuse_existing else "processed")
        )

        if select_in_project and project_id:
            project_manager.add_selected_files(project_id, [entry.rel_path])

        logger.info(f"[Upload] job={job_id[:8]} phase=complete progress=100")
        queue_store.update_job(
            job_id,
            status="complete",
            phase=None,
            progress=100,
            rel_path=entry.rel_path,
            name=Path(entry.rel_path).name,
        )
        yield sse(
            "complete",
            {
                "rel_path": entry.rel_path,
                "sha256": entry.sha256,
                "status": status_value,
                "manifest_entry": manifest_entry,
                "job_id": job_id,
            },
        )

    except Exception as e:
        message = str(e)
        queue_store.update_job(job_id, status="error", error=message, phase=None)
        yield sse(
            "error", {"code": "UPLOAD_ERROR", "message": message, "job_id": job_id}
        )
    finally:
        # Cleanup temp file
        if temp_path.exists():
            temp_path.unlink()
        job = queue_store.get_job(job_id)
        if job and job.get("status") not in {"complete", "duplicate", "error"}:
            queue_store.update_job(
                job_id,
                status="error",
                error="Upload interrupted",
                phase=None,
            )
