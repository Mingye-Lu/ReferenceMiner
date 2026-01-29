from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from refminer.analyze.workflow import EvidenceChunk, derive_scope
from refminer.llm.client import ChatCompletionsClient, _load_config
from refminer.llm.tools import (
    ToolResult,
    execute_get_document_outline_tool,
    execute_get_abstract_tool,
    execute_keyword_search_tool,
    execute_list_files_tool,
    execute_read_chunk_tool,
    execute_retrieve_tool,
)

AGENT_PROMPT_PATH = Path(__file__).parent / "prompts" / "agent_prompt.md"


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
        sys.stderr.write(
            f'[agent_stream] llm_request={{"messages": {len(messages)}}}\n'
        )
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
        content = f"{question}\n\nContext:\n" + "\n".join(
            f"- {line}" for line in meta_lines
        )
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
    return {
        "role": "user",
        "content": f"TOOL_RESULT: {json.dumps(payload, ensure_ascii=False)}",
    }


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
    messages = build_agent_messages(
        question, history, context=context, use_notes=use_notes, notes=notes
    )
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
                if tool not in {
                    "rag_search",
                    "read_chunk",
                    "get_abstract",
                    "list_files",
                    "keyword_search",
                    "get_document_outline",
                }:
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
                elif tool == "list_files":
                    tool_result = execute_list_files_tool(
                        args=action.get("args") or {},
                        context=context,
                        index_dir=index_dir,
                    )
                elif tool == "keyword_search":
                    tool_result = execute_keyword_search_tool(
                        question=question,
                        args=action.get("args") or {},
                        context=context,
                        index_dir=index_dir,
                    )
                elif tool == "get_document_outline":
                    tool_result = execute_get_document_outline_tool(
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
