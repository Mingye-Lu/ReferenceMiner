from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from refminer.analyze.workflow import EvidenceChunk, analyze, derive_scope
from refminer.ingest.manifest import ManifestEntry, load_manifest
from refminer.llm.client import ChatCompletionsClient, _load_config, format_evidence
from refminer.retrieve.search import load_chunks, retrieve
from refminer.utils.paths import get_index_dir


AGENT_PROMPT_PATH = Path(__file__).parent / "prompts" / "agent_prompt.md"


@dataclass
class ToolResult:
    evidence: list[EvidenceChunk]
    analysis: dict
    formatted_evidence: list[str]
    citations: dict[int, str]
    meta: dict[str, Any]


@dataclass
class AgentDecision:
    intent: str
    response_text: str
    response_citations: list[str]
    actions: list[dict[str, Any]]


@dataclass
class AgentResult:
    response_text: str
    response_citations: list[str]
    evidence: list[EvidenceChunk]
    analysis: dict
    plans: list[str]
    used_tool: bool


def _load_agent_prompt() -> str:
    try:
        return AGENT_PROMPT_PATH.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def _normalize_history(history: Optional[list[dict]]) -> list[dict]:
    if not history:
        return []
    normalized: list[dict] = []
    for msg in history:
        role = msg.get("role")
        if role == "ai":
            role = "assistant"
        if role not in ("user", "assistant"):
            continue
        normalized.append({"role": role, "content": msg.get("content", "")})
    return normalized


def stream_chat_text(client: ChatCompletionsClient, messages: list[dict]) -> str:
    try:
        sys.stderr.write(f"[agent_stream] llm_request={{\"messages\": {len(messages)}}}\n")
        sys.stderr.flush()
    except Exception:
        pass
    parts: list[str] = []
    for delta in client.stream_chat(messages):
        parts.append(delta)
    return "".join(parts)


def _extract_json(text: str) -> Optional[dict]:
    if not text:
        return None
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
    try:
        return json.loads(stripped)
    except Exception:
        pass
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(stripped[start : end + 1])
    except Exception:
        return None


def parse_agent_decision(text: str) -> Optional[AgentDecision]:
    payload = _extract_json(text)
    if not isinstance(payload, dict):
        return None
    response_payload = payload.get("response") or {}
    if not isinstance(response_payload, dict):
        response_payload = {}
    actions = payload.get("actions") or []
    if not isinstance(actions, list):
        actions = []
    return AgentDecision(
        intent=(payload.get("intent") or "").strip(),
        response_text=(response_payload.get("text") or "").strip(),
        response_citations=[
            str(item).strip()
            for item in (response_payload.get("citations") or [])
            if str(item).strip()
        ],
        actions=[item for item in actions if isinstance(item, dict)],
    )


def build_agent_messages(
    question: str,
    history: Optional[list[dict]],
    context: Optional[list[str]] = None,
    use_notes: bool = False,
    notes: Optional[list[dict]] = None,
) -> list[dict]:
    system_prompt = _load_agent_prompt()
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.extend(_normalize_history(history))
    meta_lines: list[str] = []
    if context:
        meta_lines.append("Selected files: " + ", ".join(context[:20]))
        if len(context) > 20:
            meta_lines.append(f"Selected files count: {len(context)}")
    if use_notes:
        note_count = len(notes or [])
        meta_lines.append(f"Notes available: {note_count}")
    if meta_lines:
        content = f"{question}\n\nContext:\n" + "\n".join(f"- {line}" for line in meta_lines)
    else:
        content = question
    messages.append({"role": "user", "content": content})
    return messages


def build_tool_result_message(tool_name: str, result: ToolResult) -> dict:
    payload = {
        "tool": tool_name,
        "result": {
            "meta": result.meta,
            "analysis": {
                "scope": result.analysis.get("scope", []),
                "keywords": result.analysis.get("keywords", []),
                "crosscheck": result.analysis.get("crosscheck", ""),
            },
            "formatted_evidence": result.formatted_evidence,
            "evidence": [
                {
                    "chunk_id": item.chunk_id,
                    "path": item.path,
                    "page": item.page,
                    "section": item.section,
                    "text": item.text,
                    "score": item.score,
                    "bbox": item.bbox,
                }
                for item in result.evidence
            ],
        },
    }
    return {"role": "user", "content": f"TOOL_RESULT: {json.dumps(payload, ensure_ascii=False)}"}


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


def execute_retrieve_tool(
    question: str,
    context: Optional[list[str]],
    use_notes: bool,
    notes: Optional[list[dict]],
    args: dict[str, Any],
    index_dir: Optional[Path] = None,
) -> ToolResult:
    from time import perf_counter

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


def execute_get_abstract_tool(
    question: str,
    args: dict[str, Any],
    index_dir: Optional[Path] = None,
) -> ToolResult:
    from time import perf_counter

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


def execute_read_chunk_tool(
    question: str,
    args: dict[str, Any],
    index_dir: Optional[Path] = None,
) -> ToolResult:
    from time import perf_counter

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


def run_agent(
    question: str,
    context: Optional[list[str]] = None,
    use_notes: bool = False,
    notes: Optional[list[dict]] = None,
    history: Optional[list[dict]] = None,
    index_dir: Optional[Path] = None,
    max_turns: int = 6,
    max_tool_calls: int = 10,
) -> AgentResult:
    config = _load_config()
    if not config:
        return AgentResult(
            response_text="",
            response_citations=[],
            evidence=[],
            analysis={"scope": derive_scope(question)},
            plans=[],
            used_tool=False,
        )

    client = ChatCompletionsClient(config)
    messages = build_agent_messages(question, history, context=context, use_notes=use_notes, notes=notes)
    plans: list[str] = []
    evidence: list[EvidenceChunk] = []
    analysis: dict = {"scope": derive_scope(question)}
    tool_calls = 0
    used_tool = False
    malformed_retries = 0

    for _ in range(max_turns):
        try:
            raw = stream_chat_text(client, messages)
        except Exception:
            break
        sys.stderr.write(f"[agent] raw_response={raw}\n")
        sys.stderr.flush()
        decision = parse_agent_decision(raw)
        messages.append({"role": "assistant", "content": raw})

        if not decision:
            if malformed_retries < 2:
                malformed_retries += 1
                messages.append(
                    {
                        "role": "user",
                        "content": "Your last response was malformed. Respond again with exactly one JSON object that follows the schema in the system prompt. Do not include any extra text.",
                    }
                )
                continue
            break

        if decision.intent == "call_tool":
            if decision.response_text:
                plans.append(decision.response_text)
            for action in decision.actions:
                tool = (action.get("tool") or "").strip()
                if tool not in {"rag_search", "read_chunk", "get_abstract"}:
                    return AgentResult(
                        response_text="",
                        response_citations=[],
                        evidence=evidence,
                        analysis=analysis,
                        plans=plans,
                        used_tool=used_tool,
                    )
                tool_calls += 1
                if tool_calls > max_tool_calls:
                    return AgentResult(
                        response_text="",
                        response_citations=[],
                        evidence=evidence,
                        analysis=analysis,
                        plans=plans,
                        used_tool=used_tool,
                    )
                used_tool = True
                if tool == "rag_search":
                    tool_result = execute_retrieve_tool(
                        question=question,
                        context=context,
                        use_notes=use_notes,
                        notes=notes,
                        args=action.get("args") or {},
                        index_dir=index_dir,
                    )
                elif tool == "read_chunk":
                    tool_result = execute_read_chunk_tool(
                        question=question,
                        args=action.get("args") or {},
                        index_dir=index_dir,
                    )
                else:
                    tool_result = execute_get_abstract_tool(
                        question=question,
                        args=action.get("args") or {},
                        index_dir=index_dir,
                    )
                evidence = tool_result.evidence
                analysis = tool_result.analysis
                messages.append(build_tool_result_message(tool, tool_result))
            continue

        if decision.intent == "respond":
            if not decision.response_text:
                break
            return AgentResult(
                response_text=decision.response_text,
                response_citations=decision.response_citations,
                evidence=evidence,
                analysis=analysis,
                plans=plans,
                used_tool=used_tool,
            )

    return AgentResult(
        response_text="",
        response_citations=[],
        evidence=evidence,
        analysis=analysis,
        plans=plans,
        used_tool=used_tool,
    )

