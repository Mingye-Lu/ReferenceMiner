"""Agent tools for retrieving and reading evidence."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Optional

from refminer.analyze.workflow import EvidenceChunk, analyze
from refminer.ingest.manifest import ManifestEntry, load_manifest
from refminer.llm.client import format_evidence
from refminer.retrieve.search import load_chunks, retrieve
from refminer.utils.paths import get_index_dir


@dataclass
class ToolResult:
    evidence: list[EvidenceChunk]
    analysis: dict
    formatted_evidence: list[str]
    citations: dict[int, str]
    meta: dict[str, Any]


def _notes_to_evidence(notes: list[dict]) -> list[EvidenceChunk]:
    evidence: list[EvidenceChunk] = []
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
                    bbox=note.get("bbox"),
                )
            )
        except Exception:
            continue
    return evidence


def _split_chunk_id(chunk_id: str) -> tuple[str | None, int | None]:
    if not chunk_id:
        return None, None
    if ":" not in chunk_id:
        return None, None
    path_part, index_part = chunk_id.rsplit(":", 1)
    try:
        index = int(index_part)
    except ValueError:
        return None, None
    if index < 1:
        return None, None
    return path_part, index


def _resolve_manifest_entry(target: str, manifest: list[ManifestEntry]) -> ManifestEntry | None:
    if not target:
        return None
    for entry in manifest:
        if entry.rel_path == target:
            return entry
    name = Path(target).name
    if not name:
        return None
    matches = [entry for entry in manifest if Path(entry.rel_path).name == name]
    if len(matches) == 1:
        return matches[0]
    return None


def execute_retrieve_tool(
    question: str,
    context: Optional[list[str]],
    use_notes: bool,
    notes: Optional[list[dict]],
    args: dict[str, Any],
    index_dir: Optional[Path] = None,
) -> ToolResult:
    idx_dir = index_dir or get_index_dir(None)
    query = (args.get("query") or question).strip()
    k = int(args.get("k") or 3)
    filter_files = args.get("filter_files") or context
    bm25_exists = (idx_dir / "bm25.pkl").exists()
    vectors_exists = (idx_dir / "vectors.faiss").exists()

    retrieve_start = perf_counter()
    if use_notes and notes:
        query = "notes"
        evidence = _notes_to_evidence(notes)
    else:
        evidence = retrieve(query, index_dir=idx_dir, k=k, filter_files=filter_files)
    retrieve_ms = (perf_counter() - retrieve_start) * 1000.0

    analyze_start = perf_counter()
    analysis = analyze(question, evidence)
    analyze_ms = (perf_counter() - analyze_start) * 1000.0
    formatted_evidence, citations = format_evidence(evidence)

    top_paths: list[str] = []
    seen_paths: set[str] = set()
    for item in evidence:
        if item.path in seen_paths:
            continue
        seen_paths.add(item.path)
        top_paths.append(item.path)
        if len(top_paths) >= 3:
            break

    meta = {
        "tool": "rag_search",
        "query": query,
        "k": k,
        "filter_files": filter_files or [],
        "index_status": {"bm25": bm25_exists, "vectors": vectors_exists},
        "retrieve_ms": retrieve_ms,
        "analyze_ms": analyze_ms,
        "evidence_count": len(evidence),
        "top_paths": top_paths,
        "keywords": analysis.get("keywords", []),
    }
    return ToolResult(
        evidence=evidence,
        analysis=analysis,
        formatted_evidence=formatted_evidence,
        citations=citations,
        meta=meta,
    )


def execute_get_abstract_tool(
    question: str,
    args: dict[str, Any],
    index_dir: Optional[Path] = None,
) -> ToolResult:
    idx_dir = index_dir or get_index_dir(None)
    rel_path = (args.get("rel_path") or args.get("path") or args.get("file") or "").strip()

    retrieve_start = perf_counter()
    manifest = load_manifest(index_dir=idx_dir)
    entry = _resolve_manifest_entry(rel_path, manifest)
    retrieve_ms = (perf_counter() - retrieve_start) * 1000.0

    evidence: list[EvidenceChunk] = []
    resolved_path = entry.rel_path if entry else rel_path
    abstract_text = entry.abstract if entry else None
    if abstract_text:
        evidence.append(
            EvidenceChunk(
                chunk_id=f"{resolved_path}:abstract",
                path=resolved_path,
                page=None,
                section="abstract",
                text=abstract_text,
                score=1.0,
                bbox=None,
            )
        )

    analyze_start = perf_counter()
    analysis = analyze(question, evidence)
    analyze_ms = (perf_counter() - analyze_start) * 1000.0
    formatted_evidence, citations = format_evidence(evidence)
    meta = {
        "tool": "get_abstract",
        "rel_path": resolved_path,
        "title": entry.title if entry else None,
        "found": bool(abstract_text),
        "retrieve_ms": retrieve_ms,
        "analyze_ms": analyze_ms,
        "evidence_count": len(evidence),
        "keywords": analysis.get("keywords", []),
    }
    return ToolResult(
        evidence=evidence,
        analysis=analysis,
        formatted_evidence=formatted_evidence,
        citations=citations,
        meta=meta,
    )


def _format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable form."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def execute_list_files_tool(
    args: dict[str, Any],
    context: Optional[list[str]] = None,
    index_dir: Optional[Path] = None,
) -> ToolResult:
    """List available files in the reference bank with metadata."""
    idx_dir = index_dir or get_index_dir(None)
    file_type_filter = (args.get("file_type") or "").strip().lower()
    pattern = (args.get("pattern") or "").strip().lower()
    only_selected = args.get("only_selected", False)

    retrieve_start = perf_counter()
    manifest = load_manifest(index_dir=idx_dir)

    # Apply filters
    filtered: list[ManifestEntry] = []
    for entry in manifest:
        # Filter by file type if specified
        if file_type_filter and entry.file_type != file_type_filter:
            continue
        # Filter by pattern in filename or title
        if pattern:
            name_match = pattern in entry.rel_path.lower()
            title_match = entry.title and pattern in entry.title.lower()
            if not (name_match or title_match):
                continue
        # Filter to only selected files if requested
        if only_selected and context:
            if entry.rel_path not in context:
                continue
        filtered.append(entry)

    retrieve_ms = (perf_counter() - retrieve_start) * 1000.0

    # Format file list for LLM consumption
    formatted_lines: list[str] = []
    by_type: dict[str, int] = {}
    for entry in filtered:
        by_type[entry.file_type] = by_type.get(entry.file_type, 0) + 1
        title_part = f' "{entry.title}"' if entry.title else ""
        pages_part = f", {entry.page_count} pages" if entry.page_count else ""
        size_part = _format_file_size(entry.size_bytes)
        has_abstract = " [has abstract]" if entry.abstract else ""
        formatted_lines.append(
            f"- {entry.rel_path}{title_part} ({entry.file_type}, {size_part}{pages_part}){has_abstract}"
        )

    # Summary line
    type_summary = ", ".join(f"{count} {ftype}" for ftype, count in sorted(by_type.items()))
    summary = f"Found {len(filtered)} files: {type_summary}" if type_summary else f"Found {len(filtered)} files"

    meta = {
        "tool": "list_files",
        "file_type_filter": file_type_filter or None,
        "pattern": pattern or None,
        "only_selected": only_selected,
        "total_in_bank": len(manifest),
        "matched_count": len(filtered),
        "by_type": by_type,
        "retrieve_ms": retrieve_ms,
    }

    return ToolResult(
        evidence=[],
        analysis={"summary": summary, "file_count": len(filtered)},
        formatted_evidence=[summary] + formatted_lines,
        citations={},
        meta=meta,
    )


def execute_read_chunk_tool(
    question: str,
    args: dict[str, Any],
    index_dir: Optional[Path] = None,
) -> ToolResult:
    idx_dir = index_dir or get_index_dir(None)
    chunk_id = (args.get("chunk_id") or "").strip()
    radius = int(args.get("radius") or 1)
    radius = max(0, radius)

    retrieve_start = perf_counter()
    chunks = load_chunks(idx_dir)
    target_ids: list[str] = []
    path_part, index = _split_chunk_id(chunk_id)

    if path_part and index:
        start = max(1, index - radius)
        end = index + radius
        for i in range(start, end + 1):
            candidate = f"{path_part}:{i}"
            if candidate in chunks:
                target_ids.append(candidate)
    elif chunk_id and chunk_id in chunks:
        target_ids.append(chunk_id)

    evidence: list[EvidenceChunk] = []
    for cid in target_ids:
        item = chunks.get(cid)
        if not item:
            continue
        score = 1.0
        if index is not None:
            _, current_index = _split_chunk_id(cid)
            if current_index is not None:
                score = 1.0 / (1 + abs(current_index - index))
        evidence.append(
            EvidenceChunk(
                chunk_id=cid,
                path=item.get("path") or "",
                page=item.get("page"),
                section=item.get("section"),
                text=item.get("text") or "",
                score=score,
                bbox=item.get("bbox"),
            )
        )
    retrieve_ms = (perf_counter() - retrieve_start) * 1000.0

    analyze_start = perf_counter()
    analysis = analyze(question, evidence)
    analyze_ms = (perf_counter() - analyze_start) * 1000.0
    formatted_evidence, citations = format_evidence(evidence)
    top_paths: list[str] = []
    seen_paths: set[str] = set()
    for item in evidence:
        if item.path in seen_paths:
            continue
        seen_paths.add(item.path)
        top_paths.append(item.path)
        if len(top_paths) >= 3:
            break
    meta = {
        "tool": "read_chunk",
        "chunk_id": chunk_id,
        "radius": radius,
        "resolved_ids": target_ids,
        "found": len(evidence),
        "retrieve_ms": retrieve_ms,
        "analyze_ms": analyze_ms,
        "evidence_count": len(evidence),
        "top_paths": top_paths,
        "keywords": analysis.get("keywords", []),
    }
    return ToolResult(
        evidence=evidence,
        analysis=analysis,
        formatted_evidence=formatted_evidence,
        citations=citations,
        meta=meta,
    )


def execute_keyword_search_tool(
    question: str,
    args: dict[str, Any],
    context: Optional[list[str]] = None,
    index_dir: Optional[Path] = None,
) -> ToolResult:
    """Search for exact keyword matches in chunks. Better than rag_search for precise terms."""
    import re

    idx_dir = index_dir or get_index_dir(None)
    keywords_input = args.get("keywords") or args.get("keyword") or ""
    if isinstance(keywords_input, list):
        keywords = [k.strip() for k in keywords_input if k.strip()]
    else:
        keywords = [k.strip() for k in str(keywords_input).split(",") if k.strip()]

    match_all = args.get("match_all", True)
    case_sensitive = args.get("case_sensitive", False)
    k = int(args.get("k") or 10)
    filter_files = args.get("filter_files") or context
    # Cap on chunks to search (default 50k, can be overridden)
    max_search = int(args.get("max_search") or 50000)

    retrieve_start = perf_counter()
    chunks = load_chunks(idx_dir)
    total_chunks = len(chunks)

    # Build regex patterns for each keyword
    flags = 0 if case_sensitive else re.IGNORECASE
    patterns = []
    for kw in keywords:
        try:
            # Escape special regex chars but allow word boundaries
            escaped = re.escape(kw)
            patterns.append(re.compile(escaped, flags))
        except re.error:
            continue

    if not patterns:
        return ToolResult(
            evidence=[],
            analysis={"summary": "No valid keywords provided"},
            formatted_evidence=["No valid keywords provided"],
            citations={},
            meta={"tool": "keyword_search", "keywords": keywords, "error": "no_valid_keywords"},
        )

    # Search through chunks with caps
    matches: list[tuple[str, dict, int, list[str]]] = []
    chunks_searched = 0
    early_termination = False
    # Early termination threshold: stop if we have k*10 matches (enough to sort and pick top k)
    early_termination_threshold = k * 10

    for chunk_id, chunk in chunks.items():
        # Cap on total chunks searched
        if chunks_searched >= max_search:
            early_termination = True
            break

        # Apply file filter (doesn't count toward search cap)
        if filter_files and chunk.get("path") not in filter_files:
            continue

        chunks_searched += 1
        text = chunk.get("text") or ""
        matched_keywords: list[str] = []
        total_matches = 0

        for i, pattern in enumerate(patterns):
            found = pattern.findall(text)
            if found:
                matched_keywords.append(keywords[i])
                total_matches += len(found)

        # Check match criteria
        if match_all and len(matched_keywords) < len(keywords):
            continue
        if not match_all and not matched_keywords:
            continue

        matches.append((chunk_id, chunk, total_matches, matched_keywords))

        # Early termination if we have enough good matches
        if len(matches) >= early_termination_threshold:
            early_termination = True
            break

    # Sort by match count (more matches = higher score)
    matches.sort(key=lambda x: x[2], reverse=True)
    matches = matches[:k]

    retrieve_ms = (perf_counter() - retrieve_start) * 1000.0

    # Build evidence
    evidence: list[EvidenceChunk] = []
    for chunk_id, chunk, match_count, matched_kws in matches:
        score = match_count / max(len(keywords), 1)
        evidence.append(
            EvidenceChunk(
                chunk_id=chunk_id,
                path=chunk.get("path") or "",
                page=chunk.get("page"),
                section=chunk.get("section"),
                text=chunk.get("text") or "",
                score=score,
                bbox=chunk.get("bbox"),
            )
        )

    analyze_start = perf_counter()
    analysis = analyze(question, evidence)
    analyze_ms = (perf_counter() - analyze_start) * 1000.0
    formatted_evidence, citations = format_evidence(evidence)

    top_paths: list[str] = []
    seen_paths: set[str] = set()
    for item in evidence:
        if item.path in seen_paths:
            continue
        seen_paths.add(item.path)
        top_paths.append(item.path)
        if len(top_paths) >= 3:
            break

    meta = {
        "tool": "keyword_search",
        "keywords": keywords,
        "match_all": match_all,
        "case_sensitive": case_sensitive,
        "k": k,
        "filter_files": filter_files or [],
        "total_chunks": total_chunks,
        "chunks_searched": chunks_searched,
        "early_termination": early_termination,
        "matches_found": len(evidence),
        "retrieve_ms": retrieve_ms,
        "analyze_ms": analyze_ms,
        "evidence_count": len(evidence),
        "top_paths": top_paths,
    }

    return ToolResult(
        evidence=evidence,
        analysis=analysis,
        formatted_evidence=formatted_evidence,
        citations=citations,
        meta=meta,
    )
