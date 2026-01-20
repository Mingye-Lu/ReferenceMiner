from __future__ import annotations

import json
import os
import re
import sys
import time
import asyncio
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
from urllib.parse import urlparse

from refminer.analyze.workflow import analyze
from refminer.ingest.incremental import full_ingest_single_file, remove_file_from_index
from refminer.ingest.manifest import SUPPORTED_EXTENSIONS, load_manifest, build_manifest, write_manifest
from refminer.ingest.extract import extract_document
from refminer.ingest.pipeline import ingest_all
from refminer.ingest.registry import HashRegistry, check_duplicate, load_registry, register_file, save_registry
from refminer.index.bm25 import build_bm25, save_bm25
from refminer.index.chunk import chunk_text
from refminer.index.vectors import build_vectors, save_vectors
from refminer.llm.openai_compatible import blocks_to_markdown, parse_answer_text, format_evidence, ChatCompletionsClient, _load_config, set_settings_manager
from refminer.llm.agent import (
    run_agent,
    parse_agent_decision,
    build_agent_messages,
    build_tool_result_message,
    execute_retrieve_tool,
)
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

PROVIDERS = ("deepseek", "openai", "gemini", "anthropic", "custom")


class ApiKeyRequest(BaseModel):
    api_key: str
    provider: Optional[str] = None


class ApiKeyValidateRequest(BaseModel):
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None


class LlmSettingsRequest(BaseModel):
    base_url: str
    model: str
    provider: Optional[str] = None


class ModelsListRequest(BaseModel):
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    provider: Optional[str] = None


@app.get("/api/settings")
async def get_settings():
    """Get current settings (API key is masked)."""
    provider = settings_manager.get_provider()
    provider_keys = {
        key: {
            "has_key": settings_manager.has_api_key(key),
            "masked_key": settings_manager.get_masked_api_key(key),
        }
        for key in PROVIDERS
    }
    provider_settings = settings_manager.get_provider_settings()
    return {
        "active_provider": provider,
        "provider_keys": provider_keys,
        "provider_settings": provider_settings,
        "has_api_key": settings_manager.has_api_key(provider),
        "masked_api_key": settings_manager.get_masked_api_key(provider),
        "base_url": settings_manager.get_base_url(provider),
        "model": settings_manager.get_model(provider),
    }


@app.post("/api/settings/api-key")
async def save_api_key(req: ApiKeyRequest):
    """Save the provider API key."""
    api_key = req.api_key.strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="API key cannot be empty")
    provider = req.provider or settings_manager.get_provider()
    if provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail="Unsupported provider")
    settings_manager.set_api_key(api_key, provider)
    return {
        "success": True,
        "has_api_key": settings_manager.has_api_key(provider),
        "masked_api_key": settings_manager.get_masked_api_key(provider),
        "provider": provider,
    }


@app.delete("/api/settings/api-key")
async def delete_api_key(provider: Optional[str] = None):
    """Remove the saved API key."""
    provider = provider or settings_manager.get_provider()
    if provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail="Unsupported provider")
    settings_manager.clear_api_key(provider)
    return {"success": True, "has_api_key": settings_manager.has_api_key(provider), "provider": provider}


@app.post("/api/settings/validate")
async def validate_api_key(req: ApiKeyValidateRequest):
    """Validate OpenAI-compatible API credentials and model selection."""
    config = settings_manager.get_chat_completions_config()
    api_key = (req.api_key or "").strip() if req else ""
    base_url = (req.base_url or "").strip() if req else ""
    model = (req.model or "").strip() if req else ""
    provider = (req.provider or "").strip() if req else ""
    provider = provider or settings_manager.get_provider()
    if provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail="Unsupported provider")

    if not api_key:
        api_key = settings_manager.get_api_key(provider)
        if not api_key:
            if not config:
                raise HTTPException(status_code=400, detail="No API key configured")
            api_key = config.api_key
    if not base_url:
        base_url = settings_manager.get_base_url(provider) if provider else (config.base_url if config else "https://api.openai.com/v1")
    if not model:
        model = settings_manager.get_model(provider) if provider else (config.model if config else "")

    candidates = _candidate_model_urls(base_url)

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    last_error = ""
    for url in candidates:
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
            return {"valid": True}
        except httpx.HTTPStatusError as e:
            last_error = f"HTTP {e.response.status_code}: {e.response.text}"
        except Exception as e:
            last_error = str(e)

    return {"valid": False, "error": last_error or "Validation failed"}


def _candidate_model_urls(base_url: str) -> list[str]:
    stripped = base_url.rstrip("/")
    candidates = [f"{stripped}/models"]
    if "/v1" not in stripped:
        candidates.append(f"{stripped}/v1/models")
    return candidates


def _fetch_models(base_url: str, api_key: str) -> list[str]:
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    last_error = ""
    for url in _candidate_model_urls(base_url):
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
            models = data.get("data") if isinstance(data, dict) else None
            if isinstance(models, list):
                return [str(item.get("id")) for item in models if isinstance(item, dict) and item.get("id")]
            last_error = "Unexpected models payload"
        except httpx.HTTPStatusError as e:
            last_error = f"HTTP {e.response.status_code}: {e.response.text}"
        except Exception as e:
            last_error = str(e)
    raise HTTPException(status_code=400, detail=last_error or "Failed to fetch models")


@app.post("/api/settings/models")
async def list_models(req: ModelsListRequest):
    """List available models via OpenAI-compatible /models endpoint."""
    config = settings_manager.get_chat_completions_config()
    api_key = (req.api_key or "").strip() if req else ""
    base_url = (req.base_url or "").strip() if req else ""
    provider = (req.provider or "").strip() if req else ""
    provider = provider or settings_manager.get_provider()
    if provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail="Unsupported provider")

    if not api_key:
        api_key = settings_manager.get_api_key(provider)
        if not api_key:
            if not config:
                raise HTTPException(status_code=400, detail="No API key configured")
            api_key = config.api_key
    if not base_url:
        base_url = settings_manager.get_base_url(provider) if provider else (config.base_url if config else "https://api.openai.com/v1")

    models = _fetch_models(base_url, api_key)
    return {"models": models, "provider": provider}


@app.post("/api/settings/llm")
async def save_llm_settings(req: LlmSettingsRequest):
    """Save OpenAI-compatible base URL and model name."""
    base_url = req.base_url.strip()
    model = req.model.strip()
    provider = req.provider or settings_manager.get_provider()
    if provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail="Unsupported provider")
    if not base_url:
        raise HTTPException(status_code=400, detail="Base URL cannot be empty")
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Base URL must be a valid http(s) URL")
    if not model:
        raise HTTPException(status_code=400, detail="Model cannot be empty")

    normalized_url = base_url.rstrip("/")
    settings_manager.set_provider(provider)
    settings_manager.set_base_url(normalized_url, provider)
    settings_manager.set_model(model, provider)
    return {"success": True, "base_url": normalized_url, "model": model, "active_provider": provider}


@app.post("/api/settings/reset")
async def reset_all_data():
    """Clear all chunks, indexes, manifest, and chat sessions. Reference files remain untouched."""
    try:
        ref_dir, idx_dir = _get_bank_paths()

        # Delete index files AND manifest (but NEVER the actual reference files)
        deleted_files = []
        for filename in ["manifest.json", "chunks.jsonl", "bm25.pkl", "vectors.faiss", "vectors.meta.npz", "hash_registry.json"]:
            file_path = idx_dir / filename
            if file_path.exists():
                file_path.unlink()
                deleted_files.append(filename)

        chats_dir = idx_dir / "chats"
        if chats_dir.exists():
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


@app.post("/api/bank/reprocess/stream")
async def reprocess_reference_bank_stream():
    """Stream reprocess progress while rebuilding from files in the references folder."""
    return StreamingResponse(_stream_reprocess(), media_type="text/event-stream")


@app.post("/api/bank/files/{rel_path:path}/reprocess/stream")
async def reprocess_single_file_stream(rel_path: str):
    """Stream reprocess progress for a single file."""
    return StreamingResponse(_stream_reprocess_file(rel_path), media_type="text/event-stream")


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

def _load_chunk_highlights(rel_path: str) -> list[dict[str, Any]]:
    _, idx_dir = _get_bank_paths()
    chunks_path = idx_dir / "chunks.jsonl"
    if not chunks_path.exists():
        return []
    results: list[dict[str, Any]] = []
    try:
        with chunks_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if item.get("path") != rel_path:
                    continue
                bbox = item.get("bbox")
                if not bbox:
                    continue
                results.append(
                    {
                        "chunk_id": item.get("chunk_id"),
                        "bbox": bbox,
                    }
                )
    except Exception:
        return []
    return results


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


def _resolve_response_citations(
    response_citations: list[str],
    citations_map: dict[int, str],
) -> list[str]:
    resolved: list[str] = []
    for item in response_citations:
        text = str(item).strip()
        match = re.match(r"^C(\d+)$", text, re.IGNORECASE)
        if not match:
            continue
        idx = int(match.group(1))
        citation = citations_map.get(idx)
        if citation and citation not in resolved:
            resolved.append(citation)
    return resolved


def _filter_evidence_by_citations(
    evidence: list[Any],
    response_citations: list[str],
) -> list[Any]:
    if not response_citations:
        return []
    indices: list[int] = []
    for item in response_citations:
        match = re.match(r"^C(\d+)$", str(item).strip(), re.IGNORECASE)
        if not match:
            continue
        idx = int(match.group(1)) - 1
        if idx >= 0 and idx not in indices:
            indices.append(idx)
    return [evidence[i] for i in indices if i < len(evidence)]


def _format_timestamp(epoch: Optional[float]) -> Optional[str]:
    if not epoch:
        return None
    return datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M")


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def _format_details(lines: list[str]) -> str:
    return "\n".join(line for line in lines if line)


def _format_ms(ms: float) -> str:
    return f"{ms / 1000.0:.2f}s"


def _clean_response_text(text: str) -> str:
    if not text:
        return text
    cleaned_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.rstrip()
        if stripped.endswith("\\"):
            stripped = stripped[:-1].rstrip()
        cleaned_lines.append(stripped)
    cleaned = "\n".join(cleaned_lines).strip()
    cleaned = re.sub(r"\\(?=\d+\.)", "\n", cleaned)
    cleaned = re.sub(r"\\(?=[*-]\s)", "\n", cleaned)
    cleaned = cleaned.replace("\\", "")
    return cleaned


def _clean_stream_text(text: str) -> str:
    if not text:
        return text
    cleaned = text.replace("\r", "")
    cleaned = re.sub(r"\\(?=\d+\.)", "\n", cleaned)
    cleaned = re.sub(r"\\(?=[*-]\s)", "\n", cleaned)
    cleaned = cleaned.replace("\\", "")
    return cleaned


def _emit_error_step(code: str, message: str) -> Iterator[str]:
    details = _format_details(
        [
            f"Provider code: {code}",
            f"Summary: {message}",
            "Retry count: 0",
        ]
    )
    yield _sse(
        "step",
        {
            "step": "error",
            "title": "Error",
            "timestamp": time.time(),
            "details": details,
        },
    )


def _unescape_json_text(text: str) -> str:
    return (
        text.replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace('\\"', '"')
        .replace("\\\\", "\\")
    )


def _extract_json_string_partial(buffer: str, key_name: str) -> Optional[str]:
    key = f'"{key_name}"'
    idx = buffer.find(key)
    if idx == -1:
        return None
    colon = buffer.find(":", idx + len(key))
    if colon == -1:
        return None
    quote = buffer.find('"', colon + 1)
    if quote == -1:
        return None
    start = quote + 1
    segment = buffer[start:]
    last_quote = None
    escaped = False
    for i, ch in enumerate(segment):
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == '"':
            last_quote = i
            break
    if last_quote is None:
        partial = segment
    else:
        partial = segment[:last_quote]
    return _unescape_json_text(partial)


def _extract_nested_json_string_partial(buffer: str, parent_key: str, child_key: str) -> Optional[str]:
    parent = f'"{parent_key}"'
    idx = buffer.find(parent)
    if idx == -1:
        return None
    return _extract_json_string_partial(buffer[idx:], child_key)


def _stream_agent_decision(
    client: ChatCompletionsClient,
    messages: list[dict],
) -> Iterator[str]:
    buffer = ""
    call_tool_emitted = False
    call_tool_details = ""
    answer_emitted = False
    answer_text = ""

    for delta in client.stream_chat(messages):
        buffer += delta
        if not call_tool_emitted and re.search(r'"intent"\s*:\s*"call_tool"', buffer):
            call_tool_emitted = True
            yield _sse(
                "step",
                {
                    "step": "plan",
                    "title": "Planning",
                    "timestamp": time.time(),
                    "details": "",
                },
            )
        if call_tool_emitted:
            partial = _extract_nested_json_string_partial(buffer, "response", "text")
            if partial is not None and partial != call_tool_details:
                call_tool_details = partial
                yield _sse(
                    "step_update",
                    {
                        "step": "plan",
                        "details": call_tool_details,
                    },
                )
        if not answer_emitted and re.search(r'"intent"\s*:\s*"respond"', buffer):
            answer_emitted = True
            yield _sse(
                "step",
                {
                    "step": "answer",
                    "title": "Generating Answer",
                    "timestamp": time.time(),
                    "details": "",
                },
            )
        if answer_emitted:
            partial = _extract_nested_json_string_partial(buffer, "response", "text")
            if partial is not None:
                cleaned_partial = _clean_stream_text(partial)
                if cleaned_partial != answer_text:
                    delta_text = cleaned_partial[len(answer_text):]
                    answer_text = cleaned_partial
                    if delta_text:
                        yield _sse("answer_delta", {"delta": delta_text})

    return buffer, call_tool_emitted, call_tool_details, answer_emitted


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


def _chunk_text(text: str) -> Iterator[str]:
    if not text:
        return
    for token in re.findall(r"\S+|\s+", text):
        if token:
            yield token


def _stream_agent(
    project_id: str,
    question: str,
    context: Optional[list[str]] = None,
    use_notes: bool = False,
    notes: Optional[list[dict]] = None,
    history: Optional[list[dict]] = None,
) -> Iterator[str]:
    dispatch_ts = time.time()
    yield _sse("step", {"step": "dispatch", "title": "Thinking", "timestamp": dispatch_ts})
    config = _load_config()
    if not config:
        analysis = analyze(question, [])
        _, answer_markdown = _fallback_answer(analysis, [])
        if answer_markdown:
            yield _sse("answer_delta", {"delta": answer_markdown})
        yield _sse("done", {})
        return

    client = ChatCompletionsClient(config)
    messages = build_agent_messages(question, history, context=context, use_notes=use_notes, notes=notes)
    tool_calls = 0
    current_step: Optional[str] = "dispatch"
    malformed_retries = 0

    def end_step(phase: Optional[str]) -> None:
        if not phase:
            return
        yield _sse("step_update", {"step": phase, "endTime": int(time.time() * 1000)})

    for _ in range(6):
        try:
            stream_gen = _stream_agent_decision(client, messages)
            raw = ""
            call_tool_emitted = False
            call_tool_details = ""
            answer_emitted = False
            while True:
                try:
                    event = next(stream_gen)
                    yield event
                    if isinstance(event, str) and '"step": "plan"' in event:
                        if current_step != "plan":
                            for end_event in end_step(current_step):
                                yield end_event
                        current_step = "plan"
                    if isinstance(event, str) and '"step": "answer"' in event:
                        if current_step != "answer":
                            for end_event in end_step(current_step):
                                yield end_event
                        current_step = "answer"
                except StopIteration as stop:
                    if stop.value:
                        raw, call_tool_emitted, call_tool_details, answer_emitted = stop.value
                    break
        except Exception as e:
            error_msg = str(e)
            if "Content Exists Risk" in error_msg:
                summary = "The AI provider flagged this content. Try rephrasing your question or using different references."
                yield from _emit_error_step("CONTENT_FILTERED", summary)
                yield _sse("error", {"code": "CONTENT_FILTERED", "message": summary})
            else:
                max_len = 800
                trimmed = error_msg if len(error_msg) <= max_len else error_msg[:max_len] + "..."
                summary = f"AI generation failed: {trimmed}"
                yield from _emit_error_step("LLM_ERROR", summary)
                yield _sse("error", {"code": "LLM_ERROR", "message": summary})
            return

        decision = parse_agent_decision(raw)
        sys.stderr.write(f"[agent_stream] raw_response={raw}\n")
        sys.stderr.flush()
        messages.append({"role": "assistant", "content": raw})

        if not decision:
            if malformed_retries < 2:
                malformed_retries += 1
                yield _sse(
                    "step_update",
                    {
                        "step": current_step or "dispatch",
                        "details": "Malformed response detected. Retrying with stricter format.",
                    },
                )
                messages.append(
                    {
                        "role": "user",
                        "content": "Your last response was malformed. Respond again with exactly one JSON object that follows the schema in the system prompt. Do not include any extra text.",
                    }
                )
                continue
            summary = "Malformed agent response."
            yield from _emit_error_step("LLM_ERROR", summary)
            yield _sse("error", {"code": "LLM_ERROR", "message": summary})
            return

        if decision.intent == "call_tool":
            if not call_tool_emitted:
                for end_event in end_step(current_step):
                    yield end_event
                yield _sse(
                    "step",
                    {
                        "step": "plan",
                        "title": "Planning",
                        "timestamp": time.time(),
                        "plan": decision.response_text,
                        "details": decision.response_text,
                    },
                )
                current_step = "plan"
            elif decision.response_text and decision.response_text != call_tool_details:
                yield _sse(
                    "step_update",
                    {
                        "step": "plan",
                        "details": decision.response_text,
                    },
                )
            for end_event in end_step("plan"):
                yield end_event
            current_step = None

            for action in decision.actions:
                tool = (action.get("tool") or "").strip()
                if tool != "retrieve_evidence":
                    summary = f"Unknown tool requested: {tool or 'empty'}."
                    yield from _emit_error_step("LLM_ERROR", summary)
                    yield _sse("error", {"code": "LLM_ERROR", "message": summary})
                    return
                tool_calls += 1
                if tool_calls > 3:
                    summary = "Too many tool calls."
                    yield from _emit_error_step("LLM_ERROR", summary)
                    yield _sse("error", {"code": "LLM_ERROR", "message": summary})
                    return

                if not _bm25_path().exists() and not (use_notes and notes):
                    summary = "Indexes not found. Run ingest first."
                    yield from _emit_error_step("LACK_INGEST", summary)
                    yield _sse("error", {"code": "LACK_INGEST", "message": summary})
                    return

                _, idx_dir = _get_bank_paths()
                pre_filters = (action.get("args") or {}).get("filter_files") or context or []
                if pre_filters:
                    pre_filter_label = ", ".join(pre_filters[:5])
                    if len(pre_filters) > 5:
                        pre_filter_label += f" (+{len(pre_filters) - 5} more)"
                else:
                    pre_filter_label = "All files"
                pre_index_status = {
                    "bm25": (idx_dir / "bm25.pkl").exists(),
                    "vectors": (idx_dir / "vectors.faiss").exists(),
                }
                pre_query = (action.get("args") or {}).get("query") or question
                pre_k = (action.get("args") or {}).get("k") or 3
                pre_details = _format_details(
                    [
                        "Tool: retrieve_evidence",
                        f"Query: {pre_query}",
                        f"k: {pre_k}",
                        f"Filters: {pre_filter_label}",
                        f"Index: bm25={'on' if pre_index_status.get('bm25') else 'off'}, vectors={'on' if pre_index_status.get('vectors') else 'off'}",
                    ]
                )
                for end_event in end_step(current_step):
                    yield end_event
                yield _sse(
                    "step",
                    {
                        "step": "research",
                        "title": "Searching References",
                        "timestamp": time.time(),
                        "details": pre_details,
                    },
                )
                current_step = "research"
                tool_result = execute_retrieve_tool(
                    question=question,
                    context=context,
                    use_notes=use_notes,
                    notes=notes,
                    args=action.get("args") or {},
                    index_dir=idx_dir,
                )
                meta = tool_result.meta
                now_ts = time.time()
                retrieve_sec = float(meta.get("retrieve_ms") or 0.0) / 1000.0
                analyze_sec = float(meta.get("analyze_ms") or 0.0) / 1000.0
                research_ts = max(dispatch_ts + 0.001, now_ts - (retrieve_sec + analyze_sec))
                analyze_ts = max(research_ts + retrieve_sec, now_ts - analyze_sec)
                filters = meta.get("filter_files") or []
                if filters:
                    filter_label = ", ".join(filters[:5])
                    if len(filters) > 5:
                        filter_label += f" (+{len(filters) - 5} more)"
                else:
                    filter_label = "All files"
                index_status = meta.get("index_status") or {}
                research_lines = [
                    f"Tool: {meta.get('tool', 'retrieve_evidence')}",
                    f"Query: {meta.get('query', '')}",
                    f"k: {meta.get('k', 0)}",
                    f"Filters: {filter_label}",
                    f"Index: bm25={'on' if index_status.get('bm25') else 'off'}, vectors={'on' if index_status.get('vectors') else 'off'}",
                    f"Runtime: {_format_ms(float(meta.get('retrieve_ms') or 0.0))}",
                ]
                research_details = _format_details(
                    [
                        *research_lines,
                    ]
                )
                if current_step != "research":
                    for end_event in end_step(current_step):
                        yield end_event
                    yield _sse(
                        "step",
                        {
                            "step": "research",
                            "title": "Searching References",
                            "timestamp": research_ts,
                            "details": research_details,
                        },
                    )
                    current_step = "research"
                else:
                    yield _sse(
                        "step_update",
                        {
                            "step": "research",
                            "details": research_details,
                        },
                    )

                matched_titles: list[str] = []
                seen_titles: set[str] = set()
                for item in tool_result.evidence:
                    title = Path(item.path).name
                    if title in seen_titles:
                        continue
                    seen_titles.add(title)
                    matched_titles.append(title)
                    if len(matched_titles) >= 6:
                        break
                if matched_titles:
                    lines = research_lines + ["Matches:"]
                    for title in matched_titles:
                        lines.append(f"- {title}")
                        yield _sse(
                            "step_update",
                            {"step": "research", "details": _format_details(lines)},
                        )
                yield _sse("evidence", [asdict(e) for e in tool_result.evidence])
                top_paths = meta.get("top_paths") or []
                keywords = meta.get("keywords") or []
                analyze_details = _format_details(
                    [
                        f"Evidence count: {meta.get('evidence_count', 0)}",
                        f"Top files: {', '.join(top_paths) if top_paths else 'None'}",
                        f"Keywords: {', '.join(keywords) if keywords else 'None'}",
                        f"Time: {_format_ms(float(meta.get('analyze_ms') or 0.0))}",
                    ]
                )
                for end_event in end_step(current_step):
                    yield end_event
                yield _sse(
                    "step",
                    {
                        "step": "analyze",
                        "title": "Analyzing Evidence",
                        "timestamp": analyze_ts,
                        "details": analyze_details,
                    },
                )
                current_step = "analyze"
                messages.append(build_tool_result_message("retrieve_evidence", tool_result))
            continue

        if decision.intent == "respond":
            if not decision.response_text:
                summary = "Empty response from agent."
                yield from _emit_error_step("LLM_ERROR", summary)
                yield _sse("error", {"code": "LLM_ERROR", "message": summary})
                return
            cleaned_response = _clean_response_text(decision.response_text)
            answer_start = time.perf_counter()
            citation_ids = {
                match.group(1)
                for match in (re.match(r"^C(\d+)$", item.strip(), re.IGNORECASE) for item in decision.response_citations)
                if match
            }
            if decision.response_citations:
                filtered = _filter_evidence_by_citations(tool_result.evidence if 'tool_result' in locals() else [], decision.response_citations)
                if filtered:
                    yield _sse("evidence", [asdict(e) for e in filtered])
            language = "Chinese" if _contains_cjk(cleaned_response) else "English"
            answer_details = _format_details(
                [
                    f"Citations: {len(citation_ids)}",
                    f"Language: {language}",
                    f"Response length: {len(cleaned_response)} chars",
                    f"Time: {_format_ms((time.perf_counter() - answer_start) * 1000.0)}",
                ]
            )
            if not answer_emitted:
                for end_event in end_step(current_step):
                    yield end_event
                yield _sse(
                    "step",
                    {
                        "step": "answer",
                        "title": "Generating Answer",
                        "timestamp": time.time(),
                        "details": answer_details,
                    },
                )
                current_step = "answer"
                for chunk in _chunk_text(cleaned_response):
                    yield _sse("answer_delta", {"delta": chunk})
            else:
                yield _sse(
                    "step_update",
                    {
                        "step": "answer",
                        "details": answer_details,
                    },
                )
            for end_event in end_step("answer"):
                yield end_event
            yield _sse("step", {"step": "done", "title": "Complete", "timestamp": time.time()})
            yield _sse("done", {})
            return

        summary = "Unknown agent intent."
        yield from _emit_error_step("LLM_ERROR", summary)
        yield _sse("error", {"code": "LLM_ERROR", "message": summary})
        return


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


@app.get("/api/files/{rel_path:path}/highlights")
async def get_file_highlights(rel_path: str):
    """Return bounding boxes for all chunks in a file (PDF only)."""
    resolved_path = _resolve_rel_path(rel_path)
    highlights = _load_chunk_highlights(resolved_path)
    return highlights




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
    _, idx_dir = _get_bank_paths()
    result = run_agent(
        req.question,
        context=req.context,
        use_notes=req.use_notes,
        notes=req.notes,
        history=req.history,
        index_dir=idx_dir,
    )

    if result.response_text:
        filtered_evidence = _filter_evidence_by_citations(result.evidence, result.response_citations)
        evidence_payload = [asdict(item) for item in filtered_evidence]
    else:
        evidence_payload = [asdict(item) for item in result.evidence]
    analysis = result.analysis or analyze(req.question, result.evidence)

    if result.response_text:
        cleaned_response = _clean_response_text(result.response_text)
        _lines, citations = format_evidence(result.evidence)
        answer_blocks = parse_answer_text(cleaned_response, citations)
        resolved_citations = _resolve_response_citations(result.response_citations, citations)
        if resolved_citations:
            if all(not block.citations for block in answer_blocks):
                answer_blocks[0].citations = resolved_citations
            else:
                for block in answer_blocks:
                    if not block.citations:
                        block.citations = resolved_citations
        answer_payload = [
            {"heading": block.heading, "body": block.body, "citations": block.citations}
            for block in answer_blocks
        ]
        answer_markdown = blocks_to_markdown(answer_blocks)
    else:
        answer_payload, answer_markdown = _fallback_answer(analysis, result.evidence)

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
    generator = _stream_agent(
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
        client = ChatCompletionsClient(config)
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


def _clear_bank_indexes(index_dir: Path) -> None:
    files_to_delete = [
        "manifest.json",
        "chunks.jsonl",
        "bm25.pkl",
        "vectors.faiss",
        "vectors.meta.npz",
        "hash_registry.json",
    ]
    for filename in files_to_delete:
        file_path = index_dir / filename
        if file_path.exists():
            file_path.unlink()

    chats_dir = index_dir / "chats"
    if chats_dir.exists():
        for chat_file in chats_dir.glob("*.json"):
            chat_file.unlink()


def _write_chunks_file(chunks_path: Path, chunks_payload: list[dict]) -> None:
    with chunks_path.open("w", encoding="utf-8") as handle:
        for item in chunks_payload:
            handle.write(json.dumps(item, ensure_ascii=True) + "\n")


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
            yield _sse("duplicate", {"sha256": file_hash, "existing_path": existing_path})
            return

        yield _sse("progress", {"phase": "storing", "percent": 70})

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

        yield _sse("progress", {"phase": "extracting", "percent": 80})

        # Process the file
        try:
            entry = None
            if reuse_existing and not replace_existing:
                manifest = _load_manifest()
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
        status_value = "replaced" if existing_path and replace_existing else ("reused" if reuse_existing else "processed")

        if select_in_project and project_id:
            project_manager.add_selected_files(project_id, [entry.rel_path])

        yield _sse("complete", {
            "rel_path": entry.rel_path,
            "sha256": entry.sha256,
            "status": status_value,
            "manifest_entry": manifest_entry,
        })

    except Exception as e:
        yield _sse("error", {"code": "UPLOAD_ERROR", "message": str(e)})
    finally:
        # Cleanup temp file
        if temp_path.exists():
            temp_path.unlink()


async def _stream_reprocess() -> Iterator[str]:
    try:
        ref_dir, idx_dir = _get_bank_paths()
        idx_dir.mkdir(parents=True, exist_ok=True)

        yield _sse("progress", {"phase": "resetting", "percent": 5})
        await asyncio.sleep(0)
        await asyncio.to_thread(_clear_bank_indexes, idx_dir)

        yield _sse("progress", {"phase": "scanning", "percent": 10})
        await asyncio.sleep(0)
        manifest_entries = await asyncio.to_thread(build_manifest, references_dir=ref_dir)
        total_files = len(manifest_entries)
        yield _sse("start", {"total_files": total_files})
        await asyncio.sleep(0)

        chunks_payload: list[dict] = []
        for index, entry in enumerate(manifest_entries, start=1):
            yield _sse("file", {
                "rel_path": entry.rel_path,
                "status": "processing",
                "phase": "extracting",
                "index": index,
                "total": total_files,
            })
            await asyncio.sleep(0)

            path = Path(entry.path)
            extracted = await asyncio.to_thread(extract_document, path, entry.file_type)
            entry.abstract = extracted.abstract
            entry.page_count = extracted.page_count
            entry.title = extracted.title
            if extracted.text_blocks:
                chunks = await asyncio.to_thread(
                    chunk_text,
                    entry.rel_path,
                    extracted.text_blocks,
                    extracted.page_map,
                    extracted.section_map,
                    extracted.bbox_map,
                )
                for chunk in chunks:
                    chunks_payload.append(asdict(chunk))

            yield _sse("file", {
                "rel_path": entry.rel_path,
                "status": "complete",
                "index": index,
                "total": total_files,
            })
            await asyncio.sleep(0)

        await asyncio.to_thread(write_manifest, manifest_entries, index_dir=idx_dir)

        yield _sse("progress", {"phase": "indexing", "percent": 80})
        await asyncio.sleep(0)
        if chunks_payload:
            chunks_path = idx_dir / "chunks.jsonl"
            await asyncio.to_thread(_write_chunks_file, chunks_path, chunks_payload)

            bm25_index = await asyncio.to_thread(
                build_bm25,
                [(item["chunk_id"], item["text"]) for item in chunks_payload],
            )
            await asyncio.to_thread(save_bm25, bm25_index, idx_dir / "bm25.pkl")

            vectors_path = idx_dir / "vectors.faiss"
            try:
                vector_index = await asyncio.to_thread(
                    build_vectors,
                    [(item["chunk_id"], item["text"]) for item in chunks_payload],
                )
                await asyncio.to_thread(save_vectors, vector_index, vectors_path)
            except RuntimeError:
                pass

        registry = HashRegistry()
        for entry in manifest_entries:
            register_file(entry.rel_path, entry.sha256, registry)
        await asyncio.to_thread(save_registry, registry, index_dir=idx_dir, references_dir=ref_dir)

        yield _sse("complete", {
            "total_files": total_files,
            "total_chunks": len(chunks_payload),
        })
    except Exception as e:
        yield _sse("error", {"code": "REPROCESS_ERROR", "message": str(e)})


async def _stream_reprocess_file(rel_path: str) -> Iterator[str]:
    try:
        ref_dir, idx_dir = _get_bank_paths()
        resolved_path = _resolve_rel_path(rel_path)
        file_path = ref_dir / resolved_path
        if not file_path.exists():
            yield _sse("error", {"code": "NOT_FOUND", "message": f"File not found: {resolved_path}"})
            return

        yield _sse("file", {
            "rel_path": resolved_path,
            "status": "processing",
            "phase": "extracting",
        })
        await asyncio.sleep(0)

        await asyncio.to_thread(remove_file_from_index, resolved_path, index_dir=idx_dir, references_dir=ref_dir)
        entry = await asyncio.to_thread(
            full_ingest_single_file,
            file_path,
            references_dir=ref_dir,
            index_dir=idx_dir,
            build_vectors=True,
        )
        manifest_entry = {
            "rel_path": entry.rel_path,
            "file_type": entry.file_type,
            "title": entry.title,
            "abstract": entry.abstract,
            "page_count": entry.page_count,
            "size_bytes": entry.size_bytes,
        }

        yield _sse("complete", {"manifest_entry": manifest_entry})
    except Exception as e:
        yield _sse("error", {"code": "REPROCESS_FILE_ERROR", "message": str(e)})


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
