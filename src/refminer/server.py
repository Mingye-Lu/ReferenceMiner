from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Optional

import shutil

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from refminer.analyze.workflow import analyze, EvidenceChunk
from refminer.ingest.incremental import full_ingest_single_file, remove_file_from_index
from refminer.ingest.manifest import SUPPORTED_EXTENSIONS, load_manifest
from refminer.ingest.pipeline import ingest_all
from refminer.ingest.registry import check_duplicate, load_registry, save_registry
from refminer.llm.deepseek import blocks_to_markdown, generate_answer, stream_answer, DeepSeekClient, _load_config, set_settings_manager
from refminer.retrieve.search import retrieve
from refminer.utils.hashing import sha256_file
from refminer.utils.paths import get_index_dir, get_references_dir
from refminer.projects.manager import ProjectManager
from refminer.settings import SettingsManager
from refminer.chats import ChatManager


def _get_base_dir() -> Path:
    """Get base directory, accounting for PyInstaller bundling."""
    if getattr(sys, "frozen", False):
        # Running as PyInstaller bundle - use executable's directory
        return Path(sys.executable).parent
    else:
        # Normal execution - relative to this file
        return Path(__file__).resolve().parent.parent.parent


def _is_bundled() -> bool:
    """Check if running as a PyInstaller bundle."""
    return getattr(sys, "frozen", False)


def _get_frontend_dir() -> Path:
    """Get the frontend dist directory."""
    if _is_bundled():
        # PyInstaller extracts data to _MEIPASS
        return Path(sys._MEIPASS) / "frontend"
    else:
        return _get_base_dir() / "frontend" / "dist"


# Root directory of the repository
BASE_DIR = _get_base_dir()
project_manager = ProjectManager(str(BASE_DIR))

# Settings manager for API key and other configuration
settings_manager = SettingsManager(get_index_dir(BASE_DIR))
set_settings_manager(settings_manager)

# Chat manager for persistent chat sessions
chat_manager = ChatManager(get_index_dir(BASE_DIR))


from fastapi.staticfiles import StaticFiles

app = FastAPI(title="ReferenceMiner API", version="0.1.0")

# CORS: Allow localhost dev server in dev mode, or same-origin in bundled mode
_cors_origins = ["*"] if _is_bundled() else ["http://localhost:5173", "http://127.0.0.1:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the references directory to serve files
# Files will be at /files/{rel_path}
app.mount("/files", StaticFiles(directory=str(get_references_dir(BASE_DIR))), name="files")

# --- Project Management Endpoints ---

@app.get("/api/projects")
async def get_projects():
    return [p.to_dict() for p in project_manager.get_projects()]

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None

@app.post("/api/projects")
async def create_project(req: ProjectCreate):
    project = project_manager.create_project(req.name, req.description)
    return project.to_dict()

@app.get("/api/projects/{project_id}")
async def get_project(project_id: str):
    project = project_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project.to_dict()

@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str):
    project_manager.delete_project(project_id)
    return {"success": True}

@app.post("/api/projects/{project_id}/activate")
async def activate_project(project_id: str):
    project_manager.update_activity(project_id)
    return {"success": True}


# --- Settings Endpoints ---

class ApiKeyRequest(BaseModel):
    api_key: str


@app.get("/api/settings")
async def get_settings():
    """Get current settings (API key is masked)."""
    return {
        "has_api_key": settings_manager.has_api_key(),
        "masked_api_key": settings_manager.get_masked_api_key(),
        "base_url": settings_manager.get_base_url(),
        "model": settings_manager.get_model(),
    }


@app.post("/api/settings/api-key")
async def save_api_key(req: ApiKeyRequest):
    """Save the DeepSeek API key."""
    api_key = req.api_key.strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="API key cannot be empty")
    settings_manager.set_api_key(api_key)
    return {
        "success": True,
        "has_api_key": True,
        "masked_api_key": settings_manager.get_masked_api_key(),
    }


@app.delete("/api/settings/api-key")
async def delete_api_key():
    """Remove the saved API key."""
    settings_manager.clear_api_key()
    return {"success": True, "has_api_key": settings_manager.has_api_key()}


@app.post("/api/settings/validate")
async def validate_api_key():
    """Test if the current API key is valid by fetching the user balance."""
    config = settings_manager.get_deepseek_config()
    if not config:
        raise HTTPException(status_code=400, detail="No API key configured")

    try:
        url = f"{config.base_url.rstrip('/')}/user/balance"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {config.api_key}",
        }
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
        return {
            "valid": True,
            "is_available": data.get("is_available"),
            "balance_infos": data.get("balance_infos", []),
        }
    except httpx.HTTPStatusError as e:
        error_body = e.response.text
        return {"valid": False, "error": f"HTTP {e.response.status_code}: {error_body}"}
    except Exception as e:
        return {"valid": False, "error": str(e)}


@app.post("/api/settings/reset")
async def reset_all_data():
    """Clear all chunks, indexes, manifest, and chat sessions. Reference files remain untouched."""
    try:
        ref_dir, idx_dir = _get_bank_paths()

        # Delete index files AND manifest (but NEVER the actual reference files)
        files_to_delete = [
            "manifest.json",  # List of files - safe to delete
            "chunks.jsonl",
            "bm25.pkl",
            "vectors.faiss",
            "vectors.meta.npz",
            "hash_registry.json",  # File hash registry
        ]

        deleted_files = []
        for filename in files_to_delete:
            file_path = idx_dir / filename
            if file_path.exists():
                file_path.unlink()
                deleted_files.append(filename)

        # Clear all chat sessions
        chats_dir = idx_dir / "chats"
        if chats_dir.exists():
            # Remove all chat session files
            for chat_file in chats_dir.glob("*.json"):
                chat_file.unlink()

        # CRITICAL: We do NOT touch files in references/ folder
        # Reference files are the user's primary data and must never be deleted

        return {
            "success": True,
            "message": "All metadata, indexes, and chat sessions cleared. Reference files preserved.",
            "deleted_files": deleted_files,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset data: {str(e)}")


# --- Chat Session Endpoints ---

class ChatSessionCreate(BaseModel):
    title: str = "New Chat"


class ChatSessionUpdate(BaseModel):
    title: Optional[str] = None
    messages: Optional[list[dict]] = None


class ChatMessageAdd(BaseModel):
    message: dict


class ChatMessageUpdate(BaseModel):
    message_id: str
    updates: dict


@app.get("/api/projects/{project_id}/chats")
async def get_chat_sessions(project_id: str):
    """Get all chat sessions for a project (without messages)."""
    sessions = chat_manager.get_sessions(project_id)
    return [s.to_dict() for s in sessions]


@app.post("/api/projects/{project_id}/chats")
async def create_chat_session(project_id: str, req: ChatSessionCreate):
    """Create a new chat session."""
    session = chat_manager.create_session(project_id, req.title)
    return session.to_dict()


@app.get("/api/projects/{project_id}/chats/{session_id}")
async def get_chat_session(project_id: str, session_id: str):
    """Get a specific chat session with all messages."""
    session = chat_manager.get_session(project_id, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return session.to_dict()


@app.put("/api/projects/{project_id}/chats/{session_id}")
async def update_chat_session(project_id: str, session_id: str, req: ChatSessionUpdate):
    """Update a chat session (title and/or messages)."""
    session = chat_manager.update_session(
        project_id, session_id,
        title=req.title,
        messages=req.messages
    )
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return session.to_dict()


@app.delete("/api/projects/{project_id}/chats/{session_id}")
async def delete_chat_session(project_id: str, session_id: str):
    """Delete a chat session."""
    success = chat_manager.delete_session(project_id, session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return {"success": True}


@app.post("/api/projects/{project_id}/chats/{session_id}/messages")
async def add_chat_message(project_id: str, session_id: str, req: ChatMessageAdd):
    """Add a message to a chat session."""
    session = chat_manager.add_message(project_id, session_id, req.message)
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return session.to_dict()


@app.patch("/api/projects/{project_id}/chats/{session_id}/messages")
async def update_chat_message(project_id: str, session_id: str, req: ChatMessageUpdate):
    """Update a specific message in a chat session."""
    session = chat_manager.update_message(project_id, session_id, req.message_id, req.updates)
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return session.to_dict()


class AskRequest(BaseModel):
    question: str
    context: Optional[list[str]] = None
    use_notes: bool = False
    notes: Optional[list[dict]] = None
    history: Optional[list[dict]] = None


def _get_bank_paths() -> tuple[Path, Path]:
    ref_dir = get_references_dir(BASE_DIR)
    idx_dir = get_index_dir(BASE_DIR)
    ref_dir.mkdir(parents=True, exist_ok=True)
    idx_dir.mkdir(parents=True, exist_ok=True)
    return ref_dir, idx_dir

def _manifest_path() -> Path:
    _, index_dir = _get_bank_paths()
    return index_dir / "manifest.json"

def _chunks_path() -> Path:
    _, index_dir = _get_bank_paths()
    return index_dir / "chunks.jsonl"

def _bm25_path() -> Path:
    _, index_dir = _get_bank_paths()
    return index_dir / "bm25.pkl"

def _load_manifest() -> list:
    try:
        _, idx_dir = _get_bank_paths()
        return load_manifest(index_dir=idx_dir)
    except Exception:
        return []

def _resolve_rel_path(rel_path: str) -> str:
    ref_dir, _ = _get_bank_paths()
    file_path = ref_dir / rel_path
    if file_path.exists():
        return rel_path

    name = Path(rel_path).name
    if not name:
        return rel_path

    matches = [entry.rel_path for entry in _load_manifest() if Path(entry.rel_path).name == name]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise HTTPException(status_code=409, detail=f"Multiple files named '{name}'. Provide full path.")
    return rel_path

def _count_chunks() -> int:
    path = _chunks_path()
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for _ in handle)


def _format_citation(path: str, page: Optional[int], section: Optional[str]) -> str:
    if page:
        return f"{path} p.{page}"
    if section:
        return f"{path} {section}"
    return path


def _format_timestamp(epoch: Optional[float]) -> Optional[str]:
    if not epoch:
        return None
    return datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M")


def _ensure_index() -> None:
    manifest_exists = _manifest_path().exists()
    bm25_exists = _bm25_path().exists()
    if manifest_exists and bm25_exists:
        return
    ref_dir, idx_dir = _get_bank_paths()
    ingest_all(references_dir=ref_dir, index_dir=idx_dir)


def _fallback_answer(analysis: dict, evidence: list) -> tuple[list[dict[str, Any]], str]:
    citations = [_format_citation(item.path, item.page, item.section) for item in evidence]
    blocks = [
        {
            "heading": "Synthesis",
            "body": analysis.get("synthesis", ""),
            "citations": citations[:4],
        },
        {
            "heading": "Cross-check",
            "body": analysis.get("crosscheck", ""),
            "citations": [],
        },
    ]
    markdown = "\n\n".join(
        [
            "## Synthesis\n" + analysis.get("synthesis", ""),
            "## Cross-check\n" + analysis.get("crosscheck", ""),
        ]
    )
    return blocks, markdown


def _sse(event: str, payload: Any) -> str:
    data = json.dumps(payload, ensure_ascii=False)
    return f"event: {event}\ndata: {data}\n\n"


def _stream_rag(
    project_id: str,
    question: str,
    context: Optional[list[str]] = None,
    use_notes: bool = False,
    notes: Optional[list[dict]] = None,
    history: Optional[list[dict]] = None,
) -> Iterator[str]:
    # Load manifest and ensure it exists
    if not _bm25_path().exists():
        yield _sse("error", {"code": "LACK_INGEST", "message": "Indexes not found. Run ingest first."})
        return

    evidence: list[EvidenceChunk] = []

    yield _sse("step", {"step": "research", "title": "Searching References", "timestamp": time.time()})

    if use_notes and notes:
        for note in notes:
            try:
                evidence.append(
                    EvidenceChunk(
                        chunk_id=note.get("chunkId") or note.get("chunk_id") or "",
                        path=note.get("path") or "",
                        page=note.get("page"),
                        section=note.get("section"),
                        text=note.get("text") or "",
                        score=note.get("score") or 1.0,
                    )
                )
            except Exception:
                pass
    else:
        _, idx_dir = _get_bank_paths()
        evidence = retrieve(question, index_dir=idx_dir, k=8, filter_files=context)

    yield _sse("evidence", [asdict(e) for e in evidence])

    yield _sse("step", {"step": "analyze", "title": "Analyzing Evidence", "timestamp": time.time()})
    analysis = analyze(question, evidence)

    yield _sse("step", {"step": "answer", "title": "Generating Answer", "timestamp": time.time()})
    try:
        stream_result = stream_answer(question, evidence, analysis.get("keywords", []), history=history)
        if stream_result:
            stream_iter, _citations = stream_result
            for delta in stream_iter:
                yield _sse("answer_delta", {"delta": delta})
        else:
            _, answer_markdown = _fallback_answer(analysis, evidence)
            if answer_markdown:
                yield _sse("answer_delta", {"delta": answer_markdown})
    except Exception as e:
        error_msg = str(e)
        # Parse DeepSeek error messages for user-friendly display
        if "Content Exists Risk" in error_msg:
            yield _sse("error", {
                "code": "CONTENT_FILTERED",
                "message": "The AI provider flagged this content. Try rephrasing your question or using different references."
            })
        else:
            yield _sse("error", {
                "code": "LLM_ERROR",
                "message": f"AI generation failed: {error_msg[:200]}"
            })
        return

    yield _sse("step", {"step": "done", "title": "Complete", "timestamp": time.time()})
    # Send final done event to signal completion
    yield _sse("done", {})


@app.get("/api/projects/{project_id}/manifest")
async def get_manifest(project_id: str):
    entries = _load_manifest()
    selected = set(project_manager.get_selected_files(project_id))
    filtered = entries if not selected else [e for e in entries if e.rel_path in selected]
    return [asdict(entry) for entry in filtered]


@app.get("/api/bank/manifest")
async def get_bank_manifest():
    entries = _load_manifest()
    return [asdict(entry) for entry in entries]


@app.get("/api/bank/files/stats")
async def get_file_stats():
    """Get usage statistics for all files in the bank."""
    projects = project_manager.get_projects()
    
    # Dictionary to store stats: {file_path: {usage_count, last_used}}
    stats = {}
    
    for project in projects:
        for file_path in project.selected_files:
            if file_path not in stats:
                stats[file_path] = {
                    "usage_count": 0,
                    "last_used": 0.0
                }
            
            stats[file_path]["usage_count"] += 1
            # Update last_used to the most recent project's last_active
            if project.last_active > stats[file_path]["last_used"]:
                stats[file_path]["last_used"] = project.last_active
    
    return stats


@app.get("/api/projects/{project_id}/files")
async def get_project_files(project_id: str):
    return {"selected_files": project_manager.get_selected_files(project_id)}


class FileSelectionRequest(BaseModel):
    rel_paths: list[str]


@app.post("/api/projects/{project_id}/files/select")
async def select_project_files(project_id: str, req: FileSelectionRequest):
    manifest = _load_manifest()
    allowed = {entry.rel_path for entry in manifest}
    rel_paths = [p for p in req.rel_paths if p in allowed]
    selected = project_manager.add_selected_files(project_id, rel_paths)
    return {"selected_files": selected}


@app.post("/api/projects/{project_id}/files/remove")
async def remove_project_files(project_id: str, req: FileSelectionRequest):
    selected = project_manager.remove_selected_files(project_id, req.rel_paths)
    return {"selected_files": selected}


@app.get("/api/projects/{project_id}/status")
async def get_status(project_id: str):
    manifest = _load_manifest()
    # The original _ensure_index needs to be updated to be project-specific
    # manifest_exists = _manifest_path(project_id).exists()
    # bm25_exists = _bm25_path(project_id).exists()
    # last_ingest = _format_timestamp(_manifest_path(project_id).stat().st_mtime) if manifest_exists else None
    return {
        "indexed": len(manifest) > 0,
        # "last_ingest": last_ingest, # Removed as per diff
        "total_files": len(manifest),
        "total_chunks": _count_chunks(),
    }


@app.post("/api/projects/{project_id}/ask")
async def ask(project_id: str, req: AskRequest):
    # The original _ensure_index needs to be updated to be project-specific
    # if not _bm25_path(project_id).exists():
    #     _ensure_index(project_id)
    if not _bm25_path().exists():
        raise HTTPException(status_code=400, detail="Indexes not found. Run ingest first.")

    evidence: list[EvidenceChunk] = []
    if req.use_notes and req.notes:
        for note in req.notes:
            try:
                evidence.append(
                    EvidenceChunk(
                        chunk_id=note.get("chunkId") or note.get("chunk_id") or "",
                        path=note.get("path") or "",
                        page=note.get("page"),
                        section=note.get("section"),
                        text=note.get("text") or "",
                        score=note.get("score") or 1.0,
                    )
                )
            except Exception:
                pass
    else:
        _, idx_dir = _get_bank_paths()
        evidence = retrieve(req.question, index_dir=idx_dir, k=8, filter_files=req.context)
    analysis = analyze(req.question, evidence)

    evidence_payload = [asdict(item) for item in evidence]

    answer_blocks = None
    try:
        answer_blocks = generate_answer(req.question, evidence, analysis.get("keywords", []), history=req.history)
    except Exception:
        answer_blocks = None

    if answer_blocks:
        answer_payload = [
            {"heading": block.heading, "body": block.body, "citations": block.citations}
            for block in answer_blocks
        ]
        answer_markdown = blocks_to_markdown(answer_blocks)
    else:
        answer_payload, answer_markdown = _fallback_answer(analysis, evidence)

    return {
        "question": req.question,
        "scope": analysis.get("scope", []),
        "evidence": evidence_payload,
        "answer": answer_payload,
        "answer_markdown": answer_markdown,
        "crosscheck": analysis.get("crosscheck", ""),
    }

@app.post("/api/projects/{project_id}/ask/stream")
async def ask_stream(project_id: str, req: AskRequest) -> StreamingResponse:
    generator = _stream_rag(
        project_id, # Pass project_id
        req.question,
        context=req.context,
        use_notes=req.use_notes,
        notes=req.notes,
        history=req.history,
    )
    return StreamingResponse(generator, media_type="text/event-stream")


class SummarizeRequest(BaseModel):
    messages: list[dict]


def _generate_title_fallback(messages: list[dict]) -> str:
    first_msg = next((m for m in messages if m.get("role") == "user"), None)
    if not first_msg:
        return "New Chat"
    content = first_msg.get("content", "")
    if len(content) > 30:
        return content[:30] + "..."
    return content


def _stream_summarize(messages: list[dict]) -> Iterator[str]:
    config = _load_config()
    if not config:
        yield _sse("title_done", {"title": _generate_title_fallback(messages)})
        return

    conversation = "\n".join(
        f"{m.get('role', 'user').upper()}: {m.get('content', '')[:200]}"
        for m in messages[:4]
    )

    prompt_messages = [
        {
            "role": "system",
            "content": "Generate a very short title (3-6 words) for this conversation. Reply with ONLY the title, no quotes or punctuation.",
        },
        {"role": "user", "content": conversation},
    ]

    try:
        client = DeepSeekClient(config)
        full_title = ""
        for delta in client.stream_chat(prompt_messages):
            for char in delta:
                full_title += char
                yield _sse("title_delta", {"delta": char})
        title = full_title.strip().strip('"\'')
        if len(title) > 50:
            title = title[:50] + "..."
        yield _sse("title_done", {"title": title or _generate_title_fallback(messages)})
    except Exception:
        yield _sse("title_done", {"title": _generate_title_fallback(messages)})


@app.post("/api/projects/{project_id}/summarize")
async def summarize(project_id: str, request: SummarizeRequest):
    if not request.messages:
        async def empty_gen() -> Iterator[str]:
            yield _sse("title_done", {"title": "New Chat"})
        return StreamingResponse(empty_gen(), media_type="text/event-stream")

    return StreamingResponse(_stream_summarize(request.messages), media_type="text/event-stream")


# =============================================================================
# File Upload Endpoints
# =============================================================================

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB


def _get_temp_dir() -> Path:
    _, index_dir = _get_bank_paths()
    temp_dir = index_dir / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def _stream_upload(
    project_id: Optional[str],
    file: UploadFile,
    replace_existing: bool = False,
    select_in_project: bool = True,
) -> Iterator[str]:
    """Stream file upload with SSE progress events."""
    # Check file extension
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        yield _sse("error", {"code": "UNSUPPORTED_TYPE", "message": f"Unsupported file type: {suffix}"})
        return

    temp_dir = _get_temp_dir()
    temp_path = temp_dir / f"upload_{int(time.time() * 1000)}{suffix}"

    try:
        yield _sse("progress", {"phase": "uploading", "percent": 0})

        # Stream file to temp location
        total_size = 0
        with temp_path.open("wb") as f:
            while chunk := file.file.read(64 * 1024):  # 64KB chunks
                total_size += len(chunk)
                if total_size > MAX_FILE_SIZE:
                    yield _sse("error", {"code": "FILE_TOO_LARGE", "message": f"File exceeds {MAX_FILE_SIZE // (1024*1024)}MB limit"})
                    return
                f.write(chunk)

        yield _sse("progress", {"phase": "hashing", "percent": 50})

        # Compute SHA256
        file_hash = sha256_file(temp_path)

        yield _sse("progress", {"phase": "checking_duplicate", "percent": 60})

        # Check for duplicates
        references_dir, index_dir = _get_bank_paths()
        registry = load_registry(index_dir=index_dir)
        existing_path = check_duplicate(file_hash, registry)

        if existing_path and not replace_existing:
            yield _sse("duplicate", {"sha256": file_hash, "existing_path": existing_path})
            return

        yield _sse("progress", {"phase": "storing", "percent": 70})

        # Determine final path
        references_dir, index_dir = _get_bank_paths()
        references_dir.mkdir(parents=True, exist_ok=True)
        final_name = file.filename or f"file{suffix}"

        # Handle name collisions (unless replacing)
        if existing_path and replace_existing:
            final_path = references_dir / existing_path
            # Remove old file from index first
            remove_file_from_index(existing_path, index_dir=index_dir, references_dir=references_dir)
        else:
            final_path = references_dir / final_name
            counter = 1
            while final_path.exists():
                stem = Path(final_name).stem
                final_path = references_dir / f"{stem}_{counter}{suffix}"
                counter += 1

        # Move file to references
        shutil.move(str(temp_path), str(final_path))

        yield _sse("progress", {"phase": "extracting", "percent": 80})

        # Process the file
        try:
            entry = full_ingest_single_file(final_path, references_dir=references_dir, index_dir=index_dir, build_vectors=True)
        except Exception as e:
            # Clean up on processing failure
            if final_path.exists():
                final_path.unlink()
            yield _sse("error", {"code": "EXTRACTION_ERROR", "message": str(e)})
            return

        yield _sse("progress", {"phase": "indexing", "percent": 95})

        # Return complete response
        manifest_entry = {
            "rel_path": entry.rel_path,
            "file_type": entry.file_type,
            "title": entry.title,
            "abstract": entry.abstract,
            "page_count": entry.page_count,
            "size_bytes": entry.size_bytes,
        }

        if select_in_project and project_id:
            project_manager.add_selected_files(project_id, [entry.rel_path])

        yield _sse("complete", {
            "rel_path": entry.rel_path,
            "sha256": entry.sha256,
            "status": "replaced" if existing_path else "processed",
            "manifest_entry": manifest_entry,
        })

    except Exception as e:
        yield _sse("error", {"code": "UPLOAD_ERROR", "message": str(e)})
    finally:
        # Cleanup temp file
        if temp_path.exists():
            temp_path.unlink()


@app.post("/api/projects/{project_id}/upload/stream")
async def upload_file_stream_api(
    project_id: str,
    file: UploadFile = File(...),
    replace_existing: bool = Form(False)
):
    """Upload a file with SSE progress events."""
    return StreamingResponse(
        _stream_upload(project_id, file, replace_existing, True),
        media_type="text/event-stream",
    )


@app.get("/api/projects/{project_id}/files/check-duplicate")
async def check_duplicate_api(project_id: str, sha256: str):
    _, idx_dir = _get_bank_paths()
    registry = load_registry(index_dir=idx_dir)
    existing_path = check_duplicate(sha256, registry)
    entry = None
    if existing_path:
        manifest = _load_manifest()
        entry = next((e for e in manifest if e.rel_path == existing_path), None)
    return {
        "is_duplicate": existing_path is not None,
        "existing_path": existing_path,
        "existing_entry": asdict(entry) if entry else None,
    }


@app.delete("/api/projects/{project_id}/files/{rel_path:path}")
async def delete_file_api(project_id: str, rel_path: str):
    """Delete a file from the bank and remove it from the index."""
    _, idx_dir = _get_bank_paths()
    ref_dir, _ = _get_bank_paths()
    resolved_path = _resolve_rel_path(rel_path)
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


class BatchDeleteRequest(BaseModel):
    rel_paths: list[str]


@app.post("/api/projects/{project_id}/files/batch-delete")
async def batch_delete_files_api(project_id: str, req: BatchDeleteRequest):
    """Delete multiple files from the bank and remove them from the index."""
    ref_dir, idx_dir = _get_bank_paths()

    results = []
    total_chunks_removed = 0
    deleted_count = 0
    failed_count = 0

    for rel_path in req.rel_paths:
        try:
            resolved_path = _resolve_rel_path(rel_path)
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


@app.post("/api/bank/upload/stream")
async def upload_bank_stream_api(
    file: UploadFile = File(...),
    replace_existing: bool = Form(False)
):
    """Upload a file to the global reference bank."""
    return StreamingResponse(
        _stream_upload(None, file, replace_existing, False),
        media_type="text/event-stream",
    )


# =============================================================================
# SPA Static File Serving (for bundled executable)
# =============================================================================

FRONTEND_DIR = _get_frontend_dir()

# Mount frontend assets if available
if FRONTEND_DIR.exists() and (FRONTEND_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="frontend_assets")


@app.get("/")
async def serve_root():
    """Serve the frontend index.html at root."""
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    # Fallback for development without built frontend
    return {"message": "ReferenceMiner API", "docs": "/docs"}


@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    """
    SPA fallback route - serves static files or index.html for client-side routing.
    This must be the LAST route registered.
    """
    # Skip API routes (handled by earlier routes)
    if full_path.startswith("api/") or full_path.startswith("files/"):
        raise HTTPException(status_code=404, detail="Not found")

    # Try to serve the exact file
    file_path = FRONTEND_DIR / full_path
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)

    # Fallback to index.html for SPA routing (e.g., /project/123)
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)

    # No frontend available
    raise HTTPException(status_code=404, detail="Not found")
