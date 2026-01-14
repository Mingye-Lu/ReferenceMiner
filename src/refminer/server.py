from __future__ import annotations

import json
import time
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Optional

import shutil
import tempfile

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from refminer.analyze.workflow import analyze, EvidenceChunk
from refminer.ingest.incremental import full_ingest_single_file, remove_file_from_index
from refminer.ingest.manifest import SUPPORTED_EXTENSIONS
from refminer.ingest.pipeline import ingest_all
from refminer.ingest.registry import check_duplicate, load_registry, save_registry
from refminer.llm.deepseek import blocks_to_markdown, generate_answer, parse_answer_text, stream_answer, DeepSeekClient, _load_config
from refminer.retrieve.search import retrieve
from refminer.utils.hashing import sha256_file
from refminer.utils.paths import get_index_dir, get_references_dir


from fastapi.staticfiles import StaticFiles

app = FastAPI(title="ReferenceMiner API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the references directory to serve files
# WARNING: In production this should be restricted. For local tool it is fine.
app.mount("/files", StaticFiles(directory="references"), name="files")


class AskRequest(BaseModel):
    question: str
    context: Optional[list[str]] = None
    use_notes: bool = False
    notes: Optional[list[dict]] = None


def _manifest_path(root: Optional[Path] = None) -> Path:
    return get_index_dir(root) / "manifest.json"


def _chunks_path(root: Optional[Path] = None) -> Path:
    return get_index_dir(root) / "chunks.jsonl"


def _bm25_path(root: Optional[Path] = None) -> Path:
    return get_index_dir(root) / "bm25.pkl"


def _load_manifest(root: Optional[Path] = None) -> list[dict[str, Any]]:
    path = _manifest_path(root)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Manifest not found. Run ingest first.")
    return json.loads(path.read_text(encoding="utf-8"))


def _count_chunks(root: Optional[Path] = None) -> int:
    path = _chunks_path(root)
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
    ingest_all(build_vectors_index=True)


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
    question: str,
    context: Optional[list[str]] = None,
    use_notes: bool = False,
    notes: Optional[list[dict]] = None,
) -> Iterator[str]:
    yield _sse("status", {"phase": "ingest", "message": "Checking index"})
    _ensure_index()

    if not _bm25_path().exists():
        yield _sse("error", {"message": "Indexes not found. Run ingest first."})
        return

    evidence: list[EvidenceChunk] = []

    if use_notes and notes:
        yield _sse("status", {"phase": "retrieve", "message": "Using pinned notes"})
        for note in notes:
            # Reconstruct EvidenceChunk from dictionary
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
        yield _sse("status", {"phase": "retrieve", "message": "Retrieving evidence"})
        evidence = retrieve(question, k=8, filter_files=context)

    analysis = analyze(question, evidence)

    yield _sse(
        "analysis",
        {
            "scope": analysis.get("scope", []),
            "keywords": analysis.get("keywords", []),
        },
    )

    yield _sse("evidence", [asdict(item) for item in evidence])

    llm_stream = stream_answer(question, evidence, analysis.get("keywords", []))
    if not llm_stream:
        yield _sse("status", {"phase": "llm", "message": "LLM unavailable, using fallback"})
        blocks, markdown = _fallback_answer(analysis, evidence)
        yield _sse("answer_done", {"blocks": blocks, "markdown": markdown})
        return

    stream_iter, citations = llm_stream
    yield _sse("status", {"phase": "llm", "message": "Drafting answer"})

    full_text = ""
    for delta in stream_iter:
        full_text += delta
        yield _sse("llm_delta", {"delta": delta})

    answer_blocks = parse_answer_text(full_text, citations)
    answer_payload = [
        {"heading": block.heading, "body": block.body, "citations": block.citations}
        for block in answer_blocks
    ]
    markdown = blocks_to_markdown(answer_blocks)
    yield _sse("answer_done", {"blocks": answer_payload, "markdown": markdown})


@app.get("/manifest")
def manifest() -> list[dict[str, Any]]:
    if not _manifest_path().exists():
        _ensure_index()
    return _load_manifest()


@app.get("/status")
def status() -> dict[str, Any]:
    manifest_exists = _manifest_path().exists()
    bm25_exists = _bm25_path().exists()
    last_ingest = _format_timestamp(_manifest_path().stat().st_mtime) if manifest_exists else None
    return {
        "indexed": manifest_exists and bm25_exists,
        "last_ingest": last_ingest,
        "total_files": len(_load_manifest()) if manifest_exists else 0,
        "total_chunks": _count_chunks(),
    }


@app.post("/ask")
def ask(request: AskRequest) -> dict[str, Any]:
    if not _bm25_path().exists():
        _ensure_index()
    if not _bm25_path().exists():
        raise HTTPException(status_code=400, detail="Indexes not found. Run ingest first.")

    evidence: list[EvidenceChunk] = []

    if request.use_notes and request.notes:
        for note in request.notes:
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
        evidence = retrieve(request.question, k=8, filter_files=request.context)
    analysis = analyze(request.question, evidence)

    evidence_payload = [asdict(item) for item in evidence]

    answer_blocks = None
    try:
        answer_blocks = generate_answer(request.question, evidence, analysis.get("keywords", []))
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
        "question": request.question,
        "scope": analysis.get("scope", []),
        "evidence": evidence_payload,
        "answer": answer_payload,
        "answer_markdown": answer_markdown,
        "crosscheck": analysis.get("crosscheck", ""),
    }

@app.post("/ask/stream")
def ask_stream(request: AskRequest) -> StreamingResponse:
    generator = _stream_rag(
        request.question,
        context=request.context,
        use_notes=request.use_notes,
        notes=request.notes,
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


@app.post("/summarize")
def summarize(request: SummarizeRequest) -> StreamingResponse:
    if not request.messages:
        def empty_gen() -> Iterator[str]:
            yield _sse("title_done", {"title": "New Chat"})
        return StreamingResponse(empty_gen(), media_type="text/event-stream")

    return StreamingResponse(_stream_summarize(request.messages), media_type="text/event-stream")


# =============================================================================
# File Upload Endpoints
# =============================================================================

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB


def _get_temp_dir() -> Path:
    temp_dir = get_index_dir() / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def _stream_upload(
    file: UploadFile,
    replace_existing: bool = False,
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
        registry = load_registry()
        existing_path = check_duplicate(file_hash, registry)

        if existing_path and not replace_existing:
            yield _sse("duplicate", {"sha256": file_hash, "existing_path": existing_path})
            return

        yield _sse("progress", {"phase": "storing", "percent": 70})

        # Determine final path
        references_dir = get_references_dir()
        references_dir.mkdir(parents=True, exist_ok=True)
        final_name = file.filename or f"file{suffix}"

        # Handle name collisions (unless replacing)
        if existing_path and replace_existing:
            final_path = references_dir / existing_path
            # Remove old file from index first
            remove_file_from_index(existing_path)
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
            entry = full_ingest_single_file(final_path, build_vectors=True)
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


@app.post("/upload/stream")
async def upload_stream(
    file: UploadFile = File(...),
    replace_existing: bool = Form(False),
) -> StreamingResponse:
    """Upload a file with SSE progress events."""
    return StreamingResponse(
        _stream_upload(file, replace_existing),
        media_type="text/event-stream",
    )


@app.delete("/files/{rel_path:path}")
def delete_file(rel_path: str) -> dict[str, Any]:
    """Delete a file and remove it from the index."""
    references_dir = get_references_dir()
    file_path = references_dir / rel_path

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {rel_path}")

    # Remove from index
    removed_chunks = remove_file_from_index(rel_path)

    # Delete the actual file
    file_path.unlink()

    return {
        "success": True,
        "removed_chunks": removed_chunks,
        "message": f"Deleted {rel_path} and removed {removed_chunks} chunks from index",
    }


@app.get("/files/check-duplicate")
def check_duplicate_endpoint(sha256: str) -> dict[str, Any]:
    """Check if a file with the given SHA256 hash already exists."""
    registry = load_registry()
    existing_path = check_duplicate(sha256, registry)

    if existing_path:
        # Load manifest to get full entry
        try:
            manifest = _load_manifest()
            entry = next((e for e in manifest if e.get("rel_path") == existing_path), None)
        except HTTPException:
            entry = None

        return {
            "is_duplicate": True,
            "existing_path": existing_path,
            "existing_entry": entry,
        }

    return {
        "is_duplicate": False,
        "existing_path": None,
        "existing_entry": None,
    }
