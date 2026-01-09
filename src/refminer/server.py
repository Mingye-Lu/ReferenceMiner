from __future__ import annotations

import json
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from refminer.analyze.workflow import analyze
from refminer.ingest.pipeline import ingest_all
from refminer.llm.deepseek import generate_answer, parse_answer_text, stream_answer
from refminer.retrieve.search import retrieve
from refminer.utils.paths import get_index_dir


app = FastAPI(title="ReferenceMiner API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str


def _manifest_path(root: Path | None = None) -> Path:
    return get_index_dir(root) / "manifest.json"


def _chunks_path(root: Path | None = None) -> Path:
    return get_index_dir(root) / "chunks.jsonl"


def _bm25_path(root: Path | None = None) -> Path:
    return get_index_dir(root) / "bm25.pkl"


def _load_manifest(root: Path | None = None) -> list[dict[str, Any]]:
    path = _manifest_path(root)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Manifest not found. Run ingest first.")
    return json.loads(path.read_text(encoding="utf-8"))


def _count_chunks(root: Path | None = None) -> int:
    path = _chunks_path(root)
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for _ in handle)


def _format_citation(path: str, page: int | None, section: str | None) -> str:
    if page:
        return f"{path} p.{page}"
    if section:
        return f"{path} {section}"
    return path


def _format_timestamp(epoch: float | None) -> str | None:
    if not epoch:
        return None
    return datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M")


def _ensure_index() -> None:
    manifest_exists = _manifest_path().exists()
    bm25_exists = _bm25_path().exists()
    if manifest_exists and bm25_exists:
        return
    ingest_all(build_vectors_index=True)


def _fallback_answer(analysis: dict, evidence: list) -> list[dict[str, Any]]:
    citations = [_format_citation(item.path, item.page, item.section) for item in evidence]
    return [
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


def _sse(event: str, payload: Any) -> str:
    data = json.dumps(payload, ensure_ascii=False)
    return f"event: {event}\ndata: {data}\n\n"


def _stream_rag(question: str) -> Iterator[str]:
    yield _sse("status", {"phase": "ingest", "message": "Checking index"})
    _ensure_index()

    if not _bm25_path().exists():
        yield _sse("error", {"message": "Indexes not found. Run ingest first."})
        return

    yield _sse("status", {"phase": "retrieve", "message": "Retrieving evidence"})
    evidence = retrieve(question, k=8)
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
        yield _sse("answer_done", _fallback_answer(analysis, evidence))
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
    yield _sse("answer_done", answer_payload)


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

    evidence = retrieve(request.question, k=8)
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
    else:
        answer_payload = _fallback_answer(analysis, evidence)

    return {
        "question": request.question,
        "scope": analysis.get("scope", []),
        "evidence": evidence_payload,
        "answer": answer_payload,
        "crosscheck": analysis.get("crosscheck", ""),
    }


@app.post("/ask/stream")
def ask_stream(request: AskRequest) -> StreamingResponse:
    generator = _stream_rag(request.question)
    return StreamingResponse(generator, media_type="text/event-stream")
