from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import AsyncIterator, Optional

from fastapi import HTTPException

from refminer.server.file_rename import rename_file_on_disk_and_reindex
from refminer.server.globals import queue_store
from refminer.server.utils import resolve_rel_path, sse

logger = logging.getLogger(__name__)


def _error_code_for_http_exception(exc: HTTPException) -> str:
    if exc.status_code == 404:
        return "NOT_FOUND"
    if exc.status_code == 409:
        detail = str(exc.detail)
        if "Multiple files named" in detail:
            return "AMBIGUOUS_PATH"
        return "CONFLICT"
    if exc.status_code == 400:
        return "VALIDATION_ERROR"
    return "RENAME_ERROR"


async def stream_rename_file(rel_path: str, new_name: str) -> AsyncIterator[str]:
    job_id: Optional[str] = None
    try:
        resolved_old_rel_path = resolve_rel_path(rel_path)
        old_basename = Path(resolved_old_rel_path).name

        job = queue_store.create_job(
            job_type="rename",
            scope="bank",
            name=old_basename,
            rel_path=resolved_old_rel_path,
            status="processing",
            phase="starting",
            progress=0,
        )
        job_id = job["id"]
        if job_id is None:
            raise RuntimeError("queue_store.create_job returned no job id")

        yield sse(
            "start",
            {
                "job_id": job_id,
                "old_rel_path": resolved_old_rel_path,
                "new_name": new_name,
                "phase": "starting",
            },
        )
        await asyncio.sleep(0)

        queue_store.update_job(job_id, status="processing", phase="renaming", progress=50)
        yield sse(
            "progress",
            {
                "job_id": job_id,
                "old_rel_path": resolved_old_rel_path,
                "phase": "renaming",
                "percent": 50,
            },
        )
        yield sse(
            "file",
            {
                "job_id": job_id,
                "rel_path": resolved_old_rel_path,
                "status": "processing",
                "phase": "renaming",
            },
        )
        await asyncio.sleep(0)

        result = await asyncio.to_thread(
            rename_file_on_disk_and_reindex,
            resolved_old_rel_path,
            new_name,
        )

        # Update queue job to complete
        logger.info(
            f"[Rename] updating job {job_id[:8]} to complete, new_path={result.new_rel_path}"
        )
        updated = queue_store.update_job(
            job_id,
            status="complete",
            phase=None,
            progress=100,
            rel_path=result.new_rel_path,
            name=Path(result.new_rel_path).name,
        )
        if not updated:
            logger.error(f"[Rename] FAILED to update job {job_id[:8]} to complete")
            raise RuntimeError(f"Failed to update queue job {job_id} to complete")
        logger.info(f"[Rename] successfully updated job {job_id[:8]} to complete")

        yield sse(
            "complete",
            {
                "job_id": job_id,
                "old_rel_path": result.old_rel_path,
                "new_rel_path": result.new_rel_path,
                "removed_chunks": result.removed_chunks,
                "phase": "complete",
            },
        )
    except HTTPException as exc:
        message = str(exc.detail)
        code = _error_code_for_http_exception(exc)
        if job_id:
            queue_store.update_job(
                job_id,
                status="error",
                error=message,
                phase=None,
            )
        yield sse("error", {"code": code, "message": message})
    except Exception as exc:
        message = str(exc)
        if job_id:
            queue_store.update_job(
                job_id,
                status="error",
                error=message,
                phase=None,
            )
        yield sse("error", {"code": "RENAME_ERROR", "message": message})
