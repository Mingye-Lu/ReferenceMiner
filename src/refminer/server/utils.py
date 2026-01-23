"""Utility functions for the server: SSE helpers, formatting, path utilities."""
from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Optional

from fastapi import HTTPException

from refminer.ingest.manifest import load_manifest, write_manifest
from refminer.server.globals import get_bank_paths


def sse(event: str, payload: Any) -> str:
    """Format a Server-Sent Event message."""
    data = json.dumps(payload, ensure_ascii=False)
    return f"event: {event}\ndata: {data}\n\n"


def chunk_text(text: str) -> Iterator[str]:
    """Yield word/whitespace tokens for streaming."""
    if not text:
        return
    for token in re.findall(r"\S+|\s+", text):
        if token:
            yield token


def format_ms(ms: float) -> str:
    """Format milliseconds as seconds string."""
    return f"{ms / 1000.0:.2f}s"


def format_timestamp(epoch: Optional[float]) -> Optional[str]:
    """Format Unix timestamp as readable date string."""
    if not epoch:
        return None
    return datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M")


def format_details(lines: list[str]) -> str:
    """Join non-empty lines for step details."""
    return "\n".join(line for line in lines if line)


def contains_cjk(text: str) -> bool:
    """Check if text contains CJK characters."""
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def clean_response_text(text: str) -> str:
    """Clean up response text by removing backslash artifacts."""
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


def clean_stream_text(text: str) -> str:
    """Clean up streaming text by removing backslash artifacts."""
    if not text:
        return text
    cleaned = text.replace("\r", "")
    cleaned = re.sub(r"\\(?=\d+\.)", "\n", cleaned)
    cleaned = re.sub(r"\\(?=[*-]\s)", "\n", cleaned)
    cleaned = cleaned.replace("\\", "")
    return cleaned


# Path utilities

def manifest_path() -> Path:
    """Get path to manifest.json."""
    _, index_dir = get_bank_paths()
    return index_dir / "manifest.json"


def chunks_path() -> Path:
    """Get path to chunks.jsonl."""
    _, index_dir = get_bank_paths()
    return index_dir / "chunks.jsonl"


def bm25_path() -> Path:
    """Get path to bm25.pkl."""
    _, index_dir = get_bank_paths()
    return index_dir / "bm25.pkl"


def load_manifest_entries() -> list:
    """Load manifest entries, returning empty list on error."""
    try:
        _, idx_dir = get_bank_paths()
        return load_manifest(index_dir=idx_dir)
    except Exception:
        return []


def update_manifest_entry(rel_path: str, update_fn) -> Optional[Any]:
    """Update a manifest entry in-place and persist changes."""
    try:
        _, idx_dir = get_bank_paths()
        manifest = load_manifest(index_dir=idx_dir)
    except Exception:
        return None

    target = None
    for entry in manifest:
        if entry.rel_path == rel_path:
            target = entry
            break

    if not target:
        return None

    update_fn(target)
    try:
        write_manifest(manifest, index_dir=idx_dir)
    except Exception:
        return None
    return target


def load_chunk_highlights(rel_path: str) -> list[dict[str, Any]]:
    """Load bounding boxes for chunks in a file (PDF only)."""
    _, idx_dir = get_bank_paths()
    chunks_file = idx_dir / "chunks.jsonl"
    if not chunks_file.exists():
        return []
    results: list[dict[str, Any]] = []
    try:
        with chunks_file.open("r", encoding="utf-8") as handle:
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


def resolve_rel_path(rel_path: str) -> str:
    """Resolve a relative path, handling ambiguous filenames."""
    ref_dir, _ = get_bank_paths()
    file_path = ref_dir / rel_path
    if file_path.exists():
        return rel_path

    name = Path(rel_path).name
    if not name:
        return rel_path

    matches = [entry.rel_path for entry in load_manifest_entries() if Path(entry.rel_path).name == name]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise HTTPException(status_code=409, detail=f"Multiple files named '{name}'. Provide full path.")
    return rel_path


def count_chunks() -> int:
    """Count total chunks in index."""
    path = chunks_path()
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for _ in handle)


# Citation utilities

def format_citation(path: str, page: Optional[int], section: Optional[str]) -> str:
    """Format a citation string from path, page, and section."""
    if page:
        return f"{path} p.{page}"
    if section:
        return f"{path} {section}"
    return path


def resolve_response_citations(
    response_citations: list[str],
    citations_map: dict[int, str],
) -> list[str]:
    """Resolve citation IDs to citation strings."""
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


def filter_evidence_by_citations(
    evidence: list[Any],
    response_citations: list[str],
) -> list[Any]:
    """Filter evidence list to only include cited items."""
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


# Error helpers

def emit_error_step(code: str, message: str) -> Iterator[str]:
    """Emit an error step SSE event."""
    details = format_details(
        [
            f"Provider code: {code}",
            f"Summary: {message}",
            "Retry count: 0",
        ]
    )
    yield sse(
        "step",
        {
            "step": "error",
            "title": "Error",
            "timestamp": time.time(),
            "details": details,
        },
    )


# JSON parsing utilities for streaming

def unescape_json_text(text: str) -> str:
    """Unescape common JSON escape sequences."""
    return (
        text.replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace('\\"', '"')
        .replace("\\\\", "\\")
    )


def extract_json_string_partial(buffer: str, key_name: str) -> Optional[str]:
    """Extract a partial JSON string value from a streaming buffer."""
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
    return unescape_json_text(partial)


def extract_nested_json_string_partial(buffer: str, parent_key: str, child_key: str) -> Optional[str]:
    """Extract a nested JSON string value from a streaming buffer."""
    parent = f'"{parent_key}"'
    idx = buffer.find(parent)
    if idx == -1:
        return None
    return extract_json_string_partial(buffer[idx:], child_key)


# Temp directory

def get_temp_dir() -> Path:
    """Get or create the temp directory for uploads."""
    _, index_dir = get_bank_paths()
    temp_dir = index_dir / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


# Index management

def clear_bank_indexes(index_dir: Path) -> None:
    """Delete all index files (but not reference files)."""
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


def write_chunks_file(chunks_path: Path, chunks_payload: list[dict]) -> None:
    """Write chunks to JSONL file."""
    with chunks_path.open("w", encoding="utf-8") as handle:
        for item in chunks_payload:
            handle.write(json.dumps(item, ensure_ascii=True) + "\n")
