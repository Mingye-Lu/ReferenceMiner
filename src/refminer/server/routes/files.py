"""File management endpoints (manifest, selection, upload, delete)."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from refminer.ingest.incremental import remove_file_from_index
from refminer.ingest.registry import load_registry, check_duplicate
from refminer.server.globals import project_manager, get_bank_paths
from refminer.server.models import FileSelectionRequest, BatchDeleteRequest
from refminer.server.utils import (
    load_manifest_entries,
    load_chunk_highlights,
    resolve_rel_path,
    count_chunks,
)
from refminer.server.streaming.upload import stream_upload

router = APIRouter(tags=["files"])


# --- Project-scoped file endpoints ---

@router.get("/api/projects/{project_id}/manifest")
async def get_manifest(project_id: str):
    """Get manifest entries for files in a project."""
    entries = load_manifest_entries()
    selected = set(project_manager.get_selected_files(project_id))
    filtered = entries if not selected else [e for e in entries if e.rel_path in selected]
    return [asdict(entry) for entry in filtered]


@router.get("/api/projects/{project_id}/files")
async def get_project_files(project_id: str):
    """Get selected files for a project."""
    return {"selected_files": project_manager.get_selected_files(project_id)}


@router.post("/api/projects/{project_id}/files/select")
async def select_project_files(project_id: str, req: FileSelectionRequest):
    """Add files to a project's selection."""
    manifest = load_manifest_entries()
    allowed = {entry.rel_path for entry in manifest}
    rel_paths = [p for p in req.rel_paths if p in allowed]
    selected = project_manager.add_selected_files(project_id, rel_paths)
    return {"selected_files": selected}


@router.post("/api/projects/{project_id}/files/remove")
async def remove_project_files(project_id: str, req: FileSelectionRequest):
    """Remove files from a project's selection."""
    selected = project_manager.remove_selected_files(project_id, req.rel_paths)
    return {"selected_files": selected}


@router.get("/api/projects/{project_id}/status")
async def get_status(project_id: str):
    """Get index statistics for a project."""
    manifest = load_manifest_entries()
    return {
        "indexed": len(manifest) > 0,
        "total_files": len(manifest),
        "total_chunks": count_chunks(),
    }


@router.post("/api/projects/{project_id}/upload/stream")
async def upload_file_stream_api(
    project_id: str,
    file: UploadFile = File(...),
    replace_existing: bool = Form(False)
):
    """Upload a file with SSE progress events."""
    return StreamingResponse(
        stream_upload(project_id, file, replace_existing, True),
        media_type="text/event-stream",
    )


@router.get("/api/projects/{project_id}/files/check-duplicate")
async def check_duplicate_api(project_id: str, sha256: str):
    """Check if a file with the given hash already exists."""
    _, idx_dir = get_bank_paths()
    registry = load_registry(index_dir=idx_dir)
    existing_path = check_duplicate(sha256, registry)
    entry = None
    if existing_path:
        manifest = load_manifest_entries()
        entry = next((e for e in manifest if e.rel_path == existing_path), None)
    return {
        "is_duplicate": existing_path is not None,
        "existing_path": existing_path,
        "existing_entry": asdict(entry) if entry else None,
    }


@router.delete("/api/projects/{project_id}/files/{rel_path:path}")
async def delete_file_api(project_id: str, rel_path: str):
    """Delete a file from the bank and remove it from the index."""
    ref_dir, idx_dir = get_bank_paths()
    resolved_path = resolve_rel_path(rel_path)
    file_path = ref_dir / resolved_path

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {resolved_path}")

    # Remove from index (which also updates registry and unlinks file if called via higher level)
    # Actually remove_file_from_index does: manifest update, chunks update, index rebuild, AND registry update.
    removed_chunks = remove_file_from_index(resolved_path, index_dir=idx_dir, references_dir=ref_dir)

    # Delete the actual file
    if file_path.exists():
        file_path.unlink()

    project_manager.remove_file_from_all_projects(resolved_path)

    return {
        "success": True,
        "removed_chunks": removed_chunks,
        "message": f"Deleted {resolved_path} and removed {removed_chunks} chunks from index",
    }


@router.post("/api/projects/{project_id}/files/batch-delete")
async def batch_delete_files_api(project_id: str, req: BatchDeleteRequest):
    """Delete multiple files from the bank and remove them from the index."""
    ref_dir, idx_dir = get_bank_paths()

    results = []
    total_chunks_removed = 0
    deleted_count = 0
    failed_count = 0

    for rel_path in req.rel_paths:
        try:
            resolved_path = resolve_rel_path(rel_path)
            file_path = ref_dir / resolved_path
            if not file_path.exists():
                results.append({"rel_path": resolved_path, "success": False, "error": "File not found"})
                failed_count += 1
                continue

            removed_chunks = remove_file_from_index(resolved_path, index_dir=idx_dir, references_dir=ref_dir)
            total_chunks_removed += removed_chunks

            if file_path.exists():
                file_path.unlink()

            project_manager.remove_file_from_all_projects(resolved_path)
            results.append({"rel_path": resolved_path, "success": True, "removed_chunks": removed_chunks})
            deleted_count += 1
        except HTTPException as e:
            results.append({"rel_path": rel_path, "success": False, "error": str(e.detail)})
            failed_count += 1
        except Exception as e:
            results.append({"rel_path": rel_path, "success": False, "error": str(e)})
            failed_count += 1

    return {
        "success": failed_count == 0,
        "deleted_count": deleted_count,
        "failed_count": failed_count,
        "total_chunks_removed": total_chunks_removed,
        "results": results,
    }


# --- File highlights endpoint (not project-scoped) ---

@router.get("/api/files/{rel_path:path}/highlights")
async def get_file_highlights(rel_path: str):
    """Return bounding boxes for all chunks in a file (PDF only)."""
    resolved_path = resolve_rel_path(rel_path)
    highlights = load_chunk_highlights(resolved_path)
    return highlights
