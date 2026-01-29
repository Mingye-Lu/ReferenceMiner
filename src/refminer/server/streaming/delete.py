"""Delete streaming logic for removing files from the bank."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import AsyncIterator, Optional

from refminer.ingest.incremental import remove_file_from_index
from refminer.server.globals import get_bank_paths, project_manager, queue_store
from refminer.server.utils import resolve_rel_path, sse


async def stream_delete_file(rel_path: str) -> AsyncIterator[str]:
    """Stream delete progress for a single file."""
    job_id: Optional[str] = None
    try:
        ref_dir, idx_dir = get_bank_paths()
        resolved_path = resolve_rel_path(rel_path)
        file_path = ref_dir / resolved_path

        if not file_path.exists():
            yield sse(
                "error",
                {"code": "NOT_FOUND", "message": f"File not found: {resolved_path}"},
            )
            return

        job = queue_store.create_job(
            job_type="delete",
            scope="bank",
            name=Path(resolved_path).name,
            rel_path=resolved_path,
            status="processing",
            phase="removing",
            progress=0,
        )
        job_id = job["id"]

        yield sse(
            "file",
            {
                "rel_path": resolved_path,
                "status": "processing",
                "phase": "removing",
            },
        )
        await asyncio.sleep(0)

        removed_chunks = await asyncio.to_thread(
            remove_file_from_index,
            resolved_path,
            index_dir=idx_dir,
            references_dir=ref_dir,
        )

        if job_id:
            queue_store.update_job(
                job_id, status="processing", phase="rebuilding_index", progress=50
            )
        yield sse(
            "file",
            {
                "rel_path": resolved_path,
                "status": "processing",
                "phase": "rebuilding_index",
            },
        )
        await asyncio.sleep(0)

        if file_path.exists():
            file_path.unlink()

        project_manager.remove_file_from_all_projects(resolved_path)

        if job_id:
            queue_store.update_job(job_id, status="complete", phase=None, progress=100)
        yield sse(
            "complete",
            {
                "rel_path": resolved_path,
                "removed_chunks": removed_chunks,
            },
        )
    except Exception as e:
        message = str(e)
        if job_id:
            queue_store.update_job(job_id, status="error", error=message, phase=None)
        yield sse("error", {"code": "DELETE_ERROR", "message": message})


async def stream_batch_delete_files(rel_paths: list[str]) -> AsyncIterator[str]:
    """Stream delete progress for multiple files."""
    job_ids: dict[str, str] = {}
    try:
        ref_dir, idx_dir = get_bank_paths()
        total_files = len(rel_paths)
        yield sse("start", {"total_files": total_files})
        await asyncio.sleep(0)

        results = []
        deleted_count = 0
        failed_count = 0

        for index, rel_path in enumerate(rel_paths, start=1):
            resolved_path = resolve_rel_path(rel_path)
            file_path = ref_dir / resolved_path

            job = queue_store.create_job(
                job_type="delete",
                scope="bank",
                name=Path(resolved_path).name,
                rel_path=resolved_path,
                status="processing",
                phase="removing",
                progress=0,
            )
            job_id = job["id"]
            job_ids[rel_path] = job_id

            yield sse(
                "file",
                {
                    "rel_path": resolved_path,
                    "status": "processing",
                    "phase": "removing",
                    "index": index,
                    "total": total_files,
                },
            )
            await asyncio.sleep(0)

            try:
                if not file_path.exists():
                    results.append(
                        {
                            "rel_path": resolved_path,
                            "success": False,
                            "error": "File not found",
                        }
                    )
                    failed_count += 1
                    queue_store.update_job(
                        job_id, status="error", error="File not found", phase=None
                    )
                    continue

                removed_chunks = await asyncio.to_thread(
                    remove_file_from_index,
                    resolved_path,
                    index_dir=idx_dir,
                    references_dir=ref_dir,
                )

                if job_id:
                    queue_store.update_job(
                        job_id, status="processing", phase="rebuilding_index", progress=50
                    )
                yield sse(
                    "file",
                    {
                        "rel_path": resolved_path,
                        "status": "processing",
                        "phase": "rebuilding_index",
                        "index": index,
                        "total": total_files,
                    },
                )
                await asyncio.sleep(0)

                if file_path.exists():
                    file_path.unlink()

                project_manager.remove_file_from_all_projects(resolved_path)

                if job_id:
                    queue_store.update_job(
                        job_id, status="complete", phase=None, progress=100
                    )
                results.append(
                    {
                        "rel_path": resolved_path,
                        "success": True,
                        "removed_chunks": removed_chunks,
                    }
                )
                deleted_count += 1
            except Exception as e:
                error_msg = str(e)
                results.append(
                    {"rel_path": rel_path, "success": False, "error": error_msg}
                )
                failed_count += 1
                queue_store.update_job(
                    job_id, status="error", error=error_msg, phase=None
                )

        yield sse(
            "complete",
            {
                "deleted_count": deleted_count,
                "failed_count": failed_count,
                "results": results,
            },
        )
    except Exception as e:
        message = str(e)
        yield sse("error", {"code": "BATCH_DELETE_ERROR", "message": message})
