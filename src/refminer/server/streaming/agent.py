"""Agent streaming logic for Q&A."""
from __future__ import annotations

import re
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Iterator, Optional

from refminer.analyze.workflow import analyze
from refminer.llm.agent import (
    build_agent_messages,
    build_tool_result_message,
    execute_retrieve_tool,
    execute_read_chunk_tool,
    execute_get_abstract_tool,
    parse_agent_decision,
)
from refminer.llm.client import ChatCompletionsClient, _load_config
from refminer.server.globals import get_bank_paths
from refminer.server.utils import (
    sse,
    chunk_text,
    format_ms,
    format_details,
    contains_cjk,
    clean_response_text,
    clean_stream_text,
    filter_evidence_by_citations,
    emit_error_step,
    extract_nested_json_string_partial,
    bm25_path,
    chunks_path,
    manifest_path,
)


def _fallback_answer(analysis: dict, evidence: list) -> tuple[list[dict], str]:
    """Generate fallback answer when LLM is unavailable."""
    from refminer.server.utils import format_citation
    citations = [format_citation(item.path, item.page, item.section) for item in evidence]
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


def _stream_agent_decision(
    client: ChatCompletionsClient,
    messages: list[dict],
) -> Iterator[str]:
    """Stream agent decision and yield SSE events."""
    buffer = ""
    call_tool_emitted = False
    call_tool_details = ""
    answer_emitted = False
    answer_text = ""

    for delta in client.stream_chat(messages):
        buffer += delta
        if not call_tool_emitted and re.search(r'"intent"\s*:\s*"call_tool"', buffer):
            call_tool_emitted = True
            yield sse(
                "step",
                {
                    "step": "plan",
                    "title": "Planning",
                    "timestamp": time.time(),
                    "details": "",
                },
            )
        if call_tool_emitted:
            partial = extract_nested_json_string_partial(buffer, "response", "text")
            if partial is not None and partial != call_tool_details:
                call_tool_details = partial
                yield sse(
                    "step_update",
                    {
                        "step": "plan",
                        "details": call_tool_details,
                    },
                )
        if not answer_emitted and re.search(r'"intent"\s*:\s*"respond"', buffer):
            answer_emitted = True
            yield sse(
                "step",
                {
                    "step": "answer",
                    "title": "Generating Answer",
                    "timestamp": time.time(),
                    "details": "",
                },
            )
        if answer_emitted:
            partial = extract_nested_json_string_partial(buffer, "response", "text")
            if partial is not None:
                cleaned_partial = clean_stream_text(partial)
                if cleaned_partial != answer_text:
                    delta_text = cleaned_partial[len(answer_text):]
                    answer_text = cleaned_partial
                    if delta_text:
                        yield sse("answer_delta", {"delta": delta_text})

    return buffer, call_tool_emitted, call_tool_details, answer_emitted


def stream_agent(
    project_id: str,
    question: str,
    context: Optional[list[str]] = None,
    use_notes: bool = False,
    notes: Optional[list[dict]] = None,
    history: Optional[list[dict]] = None,
) -> Iterator[str]:
    """Stream agent response with SSE events."""
    dispatch_ts = time.time()
    yield sse("step", {"step": "dispatch", "title": "Thinking", "timestamp": dispatch_ts})
    config = _load_config()
    if not config:
        analysis = analyze(question, [])
        _, answer_markdown = _fallback_answer(analysis, [])
        if answer_markdown:
            yield sse("answer_delta", {"delta": answer_markdown})
        yield sse("done", {})
        return

    client = ChatCompletionsClient(config)
    messages = build_agent_messages(question, history, context=context, use_notes=use_notes, notes=notes)
    tool_calls = 0
    current_step: Optional[str] = "dispatch"
    malformed_retries = 0

    def end_step(phase: Optional[str]) -> Iterator[str]:
        if not phase:
            return
        yield sse("step_update", {"step": phase, "endTime": int(time.time() * 1000)})

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
                yield from emit_error_step("CONTENT_FILTERED", summary)
                yield sse("error", {"code": "CONTENT_FILTERED", "message": summary})
            else:
                max_len = 800
                trimmed = error_msg if len(error_msg) <= max_len else error_msg[:max_len] + "..."
                summary = f"AI generation failed: {trimmed}"
                yield from emit_error_step("LLM_ERROR", summary)
                yield sse("error", {"code": "LLM_ERROR", "message": summary})
            return

        decision = parse_agent_decision(raw)
        sys.stderr.write(f"[agent_stream] raw_response={raw}\n")
        sys.stderr.flush()
        messages.append({"role": "assistant", "content": raw})

        if not decision:
            if malformed_retries < 2:
                malformed_retries += 1
                yield sse(
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
            yield from emit_error_step("LLM_ERROR", summary)
            yield sse("error", {"code": "LLM_ERROR", "message": summary})
            return

        if decision.intent == "call_tool":
            if not call_tool_emitted:
                for end_event in end_step(current_step):
                    yield end_event
                yield sse(
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
                yield sse(
                    "step_update",
                    {
                        "step": "plan",
                        "details": decision.response_text,
                    },
                )
            for end_event in end_step("plan"):
                yield end_event
            current_step = None

            _, idx_dir = get_bank_paths()

            for action in decision.actions:
                tool = (action.get("tool") or "").strip()
                if tool not in {"rag_search", "read_chunk", "get_abstract"}:
                    summary = f"Unknown tool requested: {tool or 'empty'}."
                    yield from emit_error_step("LLM_ERROR", summary)
                    yield sse("error", {"code": "LLM_ERROR", "message": summary})
                    return
                tool_calls += 1
                if tool_calls > 10:
                    summary = "Too many tool calls."
                    yield from emit_error_step("LLM_ERROR", summary)
                    yield sse("error", {"code": "LLM_ERROR", "message": summary})
                    return

                if tool == "rag_search":
                    if not bm25_path().exists() and not (use_notes and notes):
                        summary = "Indexes not found. Run ingest first."
                        yield from emit_error_step("LACK_INGEST", summary)
                        yield sse("error", {"code": "LACK_INGEST", "message": summary})
                        return
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
                    pre_details = format_details(
                        [
                            "Tool: rag_search",
                            f"Query: {pre_query}",
                            f"k: {pre_k}",
                            f"Filters: {pre_filter_label}",
                            f"Index: bm25={'on' if pre_index_status.get('bm25') else 'off'}, vectors={'on' if pre_index_status.get('vectors') else 'off'}",
                        ]
                    )
                    step_title = "Searching References"
                elif tool == "read_chunk":
                    if not chunks_path().exists():
                        summary = "Chunks not found. Run ingest first."
                        yield from emit_error_step("LACK_INGEST", summary)
                        yield sse("error", {"code": "LACK_INGEST", "message": summary})
                        return
                    pre_chunk_id = (action.get("args") or {}).get("chunk_id") or ""
                    pre_radius = (action.get("args") or {}).get("radius") or 1
                    pre_details = format_details(
                        [
                            "Tool: read_chunk",
                            f"Chunk ID: {pre_chunk_id}",
                            f"Radius: {pre_radius}",
                        ]
                    )
                    step_title = "Loading Chunk Context"
                else:
                    if not manifest_path().exists():
                        summary = "Manifest not found. Run ingest first."
                        yield from emit_error_step("LACK_INGEST", summary)
                        yield sse("error", {"code": "LACK_INGEST", "message": summary})
                        return
                    pre_rel_path = (action.get("args") or {}).get("rel_path") or ""
                    pre_details = format_details(
                        [
                            "Tool: get_abstract",
                            f"File: {pre_rel_path}",
                        ]
                    )
                    step_title = "Loading Abstract"
                for end_event in end_step(current_step):
                    yield end_event
                yield sse(
                    "step",
                    {
                        "step": "research",
                        "title": step_title,
                        "timestamp": time.time(),
                        "details": pre_details,
                    },
                )
                current_step = "research"
                if tool == "rag_search":
                    tool_result = execute_retrieve_tool(
                        question=question,
                        context=context,
                        use_notes=use_notes,
                        notes=notes,
                        args=action.get("args") or {},
                        index_dir=idx_dir,
                    )
                elif tool == "read_chunk":
                    tool_result = execute_read_chunk_tool(
                        question=question,
                        args=action.get("args") or {},
                        index_dir=idx_dir,
                    )
                else:
                    tool_result = execute_get_abstract_tool(
                        question=question,
                        args=action.get("args") or {},
                        index_dir=idx_dir,
                    )
                meta = tool_result.meta
                now_ts = time.time()
                retrieve_sec = float(meta.get("retrieve_ms") or 0.0) / 1000.0
                analyze_sec = float(meta.get("analyze_ms") or 0.0) / 1000.0
                research_ts = max(dispatch_ts + 0.001, now_ts - (retrieve_sec + analyze_sec))
                analyze_ts = max(research_ts + retrieve_sec, now_ts - analyze_sec)
                if tool == "rag_search":
                    filters = meta.get("filter_files") or []
                    if filters:
                        filter_label = ", ".join(filters[:5])
                        if len(filters) > 5:
                            filter_label += f" (+{len(filters) - 5} more)"
                    else:
                        filter_label = "All files"
                    index_status = meta.get("index_status") or {}
                    research_lines = [
                        f"Tool: {meta.get('tool', 'rag_search')}",
                        f"Query: {meta.get('query', '')}",
                        f"k: {meta.get('k', 0)}",
                        f"Filters: {filter_label}",
                        f"Index: bm25={'on' if index_status.get('bm25') else 'off'}, vectors={'on' if index_status.get('vectors') else 'off'}",
                        f"Runtime: {format_ms(float(meta.get('retrieve_ms') or 0.0))}",
                    ]
                elif tool == "read_chunk":
                    research_lines = [
                        f"Tool: {meta.get('tool', 'read_chunk')}",
                        f"Chunk ID: {meta.get('chunk_id', '')}",
                        f"Radius: {meta.get('radius', 0)}",
                        f"Found: {meta.get('found', 0)}",
                    ]
                else:
                    research_lines = [
                        f"Tool: {meta.get('tool', 'get_abstract')}",
                        f"File: {meta.get('rel_path', '')}",
                        f"Found: {meta.get('found', False)}",
                    ]
                research_details = format_details(
                    [
                        *research_lines,
                    ]
                )
                if current_step != "research":
                    for end_event in end_step(current_step):
                        yield end_event
                    yield sse(
                        "step",
                        {
                            "step": "research",
                            "title": step_title,
                            "timestamp": research_ts,
                            "details": research_details,
                        },
                    )
                    current_step = "research"
                else:
                    yield sse(
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
                        yield sse(
                            "step_update",
                            {"step": "research", "details": format_details(lines)},
                        )
                yield sse("evidence", [asdict(e) for e in tool_result.evidence])
                top_paths = meta.get("top_paths") or []
                keywords = meta.get("keywords") or []
                analyze_details = format_details(
                    [
                        f"Evidence count: {meta.get('evidence_count', 0)}",
                        f"Top files: {', '.join(top_paths) if top_paths else 'None'}",
                        f"Keywords: {', '.join(keywords) if keywords else 'None'}",
                        f"Time: {format_ms(float(meta.get('analyze_ms') or 0.0))}",
                    ]
                )
                for end_event in end_step(current_step):
                    yield end_event
                yield sse(
                    "step",
                    {
                        "step": "analyze",
                        "title": "Analyzing Evidence",
                        "timestamp": analyze_ts,
                        "details": analyze_details,
                    },
                )
                current_step = "analyze"
                messages.append(build_tool_result_message(tool, tool_result))
            continue

        if decision.intent == "respond":
            if not decision.response_text:
                summary = "Empty response from agent."
                yield from emit_error_step("LLM_ERROR", summary)
                yield sse("error", {"code": "LLM_ERROR", "message": summary})
                return
            cleaned_response = clean_response_text(decision.response_text)
            answer_start = time.perf_counter()
            citation_ids = {
                match.group(1)
                for match in (re.match(r"^C(\d+)$", item.strip(), re.IGNORECASE) for item in decision.response_citations)
                if match
            }
            if decision.response_citations:
                filtered = filter_evidence_by_citations(tool_result.evidence if 'tool_result' in locals() else [], decision.response_citations)
                if filtered:
                    yield sse("evidence", [asdict(e) for e in filtered])
            language = "Chinese" if contains_cjk(cleaned_response) else "English"
            answer_details = format_details(
                [
                    f"Citations: {len(citation_ids)}",
                    f"Language: {language}",
                    f"Response length: {len(cleaned_response)} chars",
                    f"Time: {format_ms((time.perf_counter() - answer_start) * 1000.0)}",
                ]
            )
            if not answer_emitted:
                for end_event in end_step(current_step):
                    yield end_event
                yield sse(
                    "step",
                    {
                        "step": "answer",
                        "title": "Generating Answer",
                        "timestamp": time.time(),
                        "details": answer_details,
                    },
                )
                current_step = "answer"
                for chunk in chunk_text(cleaned_response):
                    yield sse("answer_delta", {"delta": chunk})
            else:
                yield sse(
                    "step_update",
                    {
                        "step": "answer",
                        "details": answer_details,
                    },
                )
            for end_event in end_step("answer"):
                yield end_event
            yield sse("step", {"step": "done", "title": "Complete", "timestamp": time.time()})
            yield sse("done", {})
            return

        summary = "Unknown agent intent."
        yield from emit_error_step("LLM_ERROR", summary)
        yield sse("error", {"code": "LLM_ERROR", "message": summary})
        return
