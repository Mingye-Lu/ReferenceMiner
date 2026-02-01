"""Global reference bank endpoints."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import StreamingResponse

from refminer.server.globals import project_manager
from refminer.server.utils import load_manifest_entries
from refminer.server.streaming.upload import stream_upload
from refminer.server.streaming.reprocess import stream_reprocess, stream_reprocess_file

router = APIRouter(prefix="/api/bank", tags=["bank"])


@router.get("/manifest")
async def get_bank_manifest():
    """Get all files in the reference bank."""
    entries = load_manifest_entries()
    return [asdict(entry) for entry in entries]


@router.get("/files/stats")
async def get_file_stats():
    """Get usage statistics for all files in the bank."""
    projects = project_manager.get_projects()

    # Dictionary to store stats: {file_path: {usage_count, last_used}}
    stats = {}

    for project in projects:
        for file_path in project.selected_files:
            if file_path not in stats:
                stats[file_path] = {"usage_count": 0, "last_used": 0.0}

            stats[file_path]["usage_count"] += 1
            # Update last_used to the most recent project's last_active
            if project.last_active > stats[file_path]["last_used"]:
                stats[file_path]["last_used"] = project.last_active

    return stats


@router.post("/upload/stream")
async def upload_bank_stream_api(
    file: UploadFile = File(...),
    replace_existing: bool = Form(False),
    bibliography: str = Form(None),
):
    """Upload a file to the global reference bank."""
    import json

    bib_data = json.loads(bibliography) if bibliography else None
    return StreamingResponse(
        stream_upload(None, file, replace_existing, False, bib_data),
        media_type="text/event-stream",
    )


@router.post("/reprocess/stream")
async def reprocess_reference_bank_stream():
    """Stream reprocess progress while rebuilding from files in the references folder."""
    return StreamingResponse(stream_reprocess(), media_type="text/event-stream")


@router.post("/files/{rel_path:path}/reprocess/stream")
async def reprocess_single_file_stream(rel_path: str):
    """Stream reprocess progress for a single file."""
    return StreamingResponse(
        stream_reprocess_file(rel_path), media_type="text/event-stream"
    )
