"""File management endpoints (manifest, selection, upload, delete)."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from pathlib import Path

from refminer.ingest.extract import extract_document
from refminer.ingest.bibliography import (
    extract_bibliography_from_pdf,
    merge_bibliography,
)
from refminer.ingest.incremental import remove_file_from_index
from refminer.ingest.registry import load_registry, check_duplicate
from refminer.server.globals import project_manager, get_bank_paths
from refminer.server.models import (
    FileSelectionRequest,
    BatchDeleteRequest,
    FileMetadataUpdateRequest,
)
from refminer.server.utils import (
    load_manifest_entries,
    load_chunk_highlights,
    resolve_rel_path,
    count_chunks,
    update_manifest_entry,
)
from refminer.server.streaming.delete import (
    stream_delete_file,
    stream_batch_delete_files,
)
from refminer.server.streaming.upload import stream_upload

router = APIRouter(tags=["files"])


# --- Project-scoped file endpoints ---


@router.get("/api/projects/{project_id}/manifest")
async def get_manifest(project_id: str):
    """Get manifest entries for files in a project."""
    entries = load_manifest_entries()
    selected = set(project_manager.get_selected_files(project_id))
    filtered = (
        entries if not selected else [e for e in entries if e.rel_path in selected]
    )
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
    replace_existing: bool = Form(False),
    bibliography: str = Form(None),
):
    """Upload a file with SSE progress events."""
    import json

    bib_data = json.loads(bibliography) if bibliography else None
    return StreamingResponse(
        stream_upload(project_id, file, replace_existing, True, bib_data),
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


@router.post("/api/projects/{project_id}/files/{rel_path:path}/delete/stream")
async def delete_file_stream_api(project_id: str, rel_path: str):
    """Stream delete progress while removing a file from the bank."""
    return StreamingResponse(
        stream_delete_file(rel_path), media_type="text/event-stream"
    )


@router.post("/api/projects/{project_id}/files/batch-delete/stream")
async def batch_delete_files_stream_api(project_id: str, req: BatchDeleteRequest):
    """Stream delete progress while removing multiple files from the bank."""
    return StreamingResponse(
        stream_batch_delete_files(req.rel_paths), media_type="text/event-stream"
    )


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
                results.append(
                    {
                        "rel_path": resolved_path,
                        "success": False,
                        "error": "File not found",
                    }
                )
                failed_count += 1
                continue

            removed_chunks = remove_file_from_index(
                resolved_path, index_dir=idx_dir, references_dir=ref_dir
            )
            total_chunks_removed += removed_chunks

            if file_path.exists():
                file_path.unlink()

            project_manager.remove_file_from_all_projects(resolved_path)
            results.append(
                {
                    "rel_path": resolved_path,
                    "success": True,
                    "removed_chunks": removed_chunks,
                }
            )
            deleted_count += 1
        except HTTPException as e:
            results.append(
                {"rel_path": rel_path, "success": False, "error": str(e.detail)}
            )
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


# --- File metadata endpoints (not project-scoped) ---


@router.get("/api/files/{rel_path:path}/metadata")
async def get_file_metadata(rel_path: str):
    """Return stored metadata for a file."""
    resolved_path = resolve_rel_path(rel_path)
    entries = load_manifest_entries()
    entry = next((e for e in entries if e.rel_path == resolved_path), None)
    if not entry:
        raise HTTPException(status_code=404, detail=f"File not found: {resolved_path}")
    return {"bibliography": entry.bibliography}


@router.patch("/api/files/{rel_path:path}/metadata")
async def update_file_metadata(rel_path: str, req: FileMetadataUpdateRequest):
    """Update stored metadata for a file."""
    resolved_path = resolve_rel_path(rel_path)
    updated = update_manifest_entry(
        resolved_path,
        lambda entry: setattr(entry, "bibliography", req.bibliography),
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"File not found: {resolved_path}")
    return {"bibliography": updated.bibliography}


@router.post("/api/files/{rel_path:path}/metadata/extract")
async def extract_file_metadata(rel_path: str, force: bool = False):
    """Extract metadata heuristically for a file.

    Args:
        rel_path: Relative path to the file.
        force: If True, replace existing metadata. If False, merge (keep existing, fill gaps).
    """
    resolved_path = resolve_rel_path(rel_path)
    entries = load_manifest_entries()
    entry = next((e for e in entries if e.rel_path == resolved_path), None)
    if not entry:
        raise HTTPException(status_code=404, detail=f"File not found: {resolved_path}")
    if entry.file_type != "pdf":
        raise HTTPException(
            status_code=400, detail="Metadata extraction is only supported for PDFs."
        )

    ref_dir, _ = get_bank_paths()
    file_path = ref_dir / resolved_path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {resolved_path}")

    extracted = extract_document(Path(file_path), entry.file_type)
    extracted_bib = extract_bibliography_from_pdf(
        file_path, extracted.text_blocks, extracted.title, file_path.name
    )

    if force:
        # Replace existing metadata entirely with new extraction
        final_bib = extracted_bib
    else:
        # Merge: keep existing values, fill gaps with extracted
        final_bib = merge_bibliography(entry.bibliography, extracted_bib)

    updated = update_manifest_entry(
        resolved_path,
        lambda target: setattr(target, "bibliography", final_bib),
    )
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update metadata.")
    return {"bibliography": updated.bibliography}
