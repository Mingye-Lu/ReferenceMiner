from __future__ import annotations

import json
import time
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from refminer.analyze.workflow import analyze, EvidenceChunk
from refminer.ingest.pipeline import ingest_all
from refminer.llm.deepseek import blocks_to_markdown, generate_answer, parse_answer_text, stream_answer, DeepSeekClient, _load_config
from refminer.retrieve.search import retrieve
from refminer.utils.paths import get_index_dir


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
