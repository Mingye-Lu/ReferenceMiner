from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable, Iterator, Optional

import httpx

from refminer.analyze.workflow import EvidenceChunk

if TYPE_CHECKING:
    from refminer.settings import SettingsManager

# Global settings manager instance (set by server at startup)
_settings_manager: Optional["SettingsManager"] = None


def set_settings_manager(manager: "SettingsManager") -> None:
    """Set the global settings manager for config loading."""
    global _settings_manager
    _settings_manager = manager


CITATION_RE = re.compile(r"\bC(\d+)\b")
SECTION_RE = re.compile(r"^(Summary|Evidence|Limitations|Open Questions|Cross-check):\s*", re.IGNORECASE)
BODY_RE = re.compile(r"^body:\s*", re.IGNORECASE)


@dataclass
class AnswerBlock:
    heading: str
    body: str
    citations: list[str]


@dataclass
class ChatCompletionsConfig:
    api_key: str
    base_url: str
    model: str
    timeout: float = 60.0


class ChatCompletionsClient:
    def __init__(self, config: ChatCompletionsConfig) -> None:
        self._config = config

    def _maybe_log_request(self, payload: dict) -> None:
        if os.getenv("LLM_DEBUG_REQUEST") != "1":
            return
        try:
            sys.stderr.write(f"[agent_stream] llm_request={json.dumps(payload, ensure_ascii=True)}\n")
            sys.stderr.flush()
        except Exception:
            sys.stderr.write("[agent_stream] llm_request=<failed to serialize request>\n")
            sys.stderr.flush()

    def chat(self, messages: list[dict]) -> str:
        url = f"{self._config.base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self._config.model,
            "messages": messages,
            "stream": False,
        }
        self._maybe_log_request(payload)
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self._config.timeout) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        return data["choices"][0]["message"]["content"].strip()

    def stream_chat(self, messages: list[dict]) -> Iterator[str]:
        url = f"{self._config.base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self._config.model,
            "messages": messages,
            "stream": True,
        }
        self._maybe_log_request(payload)
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self._config.timeout) as client:
            with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code >= 400:
                    # Read error body before raising
                    error_body = response.read().decode("utf-8", errors="replace")
                    raise httpx.HTTPStatusError(
                        f"HTTP {response.status_code}: {error_body}",
                        request=response.request,
                        response=response
                    )
                for line in response.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    payload_text = line.replace("data:", "", 1).strip()
                    if payload_text == "[DONE]":
                        break
                    data = httpx.Response(200, content=payload_text).json()
                    delta = data.get("choices", [{}])[0].get("delta", {}).get("content")
                    if delta:
                        yield delta


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def _format_evidence(evidence: Iterable[EvidenceChunk]) -> tuple[list[str], dict[int, str]]:
    lines: list[str] = []
    citations: dict[int, str] = {}
    for index, item in enumerate(evidence, start=1):
        citation = item.path
        if item.page:
            citation = f"{citation} p.{item.page}"
        elif item.section:
            citation = f"{citation} {item.section}"
        citations[index] = citation
        lines.append(f"[C{index}] (chunk_id={item.chunk_id}) {item.text}")
    return lines, citations


def format_evidence(evidence: Iterable[EvidenceChunk]) -> tuple[list[str], dict[int, str]]:
    return _format_evidence(evidence)


def _extract_citation_ids(text: str) -> list[int]:
    seen: set[int] = set()
    ordered: list[int] = []
    for match in CITATION_RE.finditer(text):
        value = int(match.group(1))
        if value not in seen:
            ordered.append(value)
            seen.add(value)
    return ordered


def _normalize_line(line: str) -> str:
    line = line.strip()
    if BODY_RE.match(line):
        return BODY_RE.sub("", line).strip()
    return line


def _parse_sections(text: str, citations: dict[int, str]) -> list[AnswerBlock]:
    blocks: list[AnswerBlock] = []
    current_heading = "Response"
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_heading, current_lines
        if not current_lines:
            return
        body = "\n".join(current_lines).strip()
        citation_ids = _extract_citation_ids(body)
        block_citations = [citations[idx] for idx in citation_ids if idx in citations]
        blocks.append(AnswerBlock(heading=current_heading, body=body, citations=block_citations))
        current_lines = []

    for line in text.splitlines():
        match = SECTION_RE.match(line)
        if match:
            flush()
            current_heading = match.group(1).title()
            line = SECTION_RE.sub("", line).strip()
            line = _normalize_line(line)
            if line:
                current_lines.append(line)
        else:
            line = _normalize_line(line)
            if line:
                current_lines.append(line)
    flush()

    if not blocks:
        text = "\n".join(_normalize_line(line) for line in text.splitlines()).strip()
        citation_ids = _extract_citation_ids(text)
        block_citations = [citations[idx] for idx in citation_ids if idx in citations]
        blocks.append(AnswerBlock(heading="Answer", body=text.strip(), citations=block_citations))

    return blocks


def _build_messages(question: str, evidence: list[EvidenceChunk], keywords: list[str], history: Optional[list[dict]] = None) -> list[dict]:
    evidence_lines, _ = _format_evidence(evidence)
    language_hint = "Use Chinese." if _contains_cjk(question) else "Use English."
    system = (
        "You are a knowledgeable research assistant. Answer naturally and conversationally "
        "based on the provided evidence. You may structure your response however best fits "
        "the question - use paragraphs, lists, or any format that communicates clearly. "
        "Every factual claim MUST cite evidence using [C#] markers. "
        "Be direct and insightful. If the evidence doesn't fully answer the question, "
        "acknowledge what's missing. "
        f"{language_hint}"
    )
    user = (
        f"Question: {question}\n\n"
        f"Keywords: {', '.join(keywords) if keywords else 'none'}\n\n"
        "Evidence:\n"
        + "\n".join(evidence_lines)
    )

    messages = [{"role": "system", "content": system}]

    # Include chat history if provided (exclude system messages from history)
    if history:
        for msg in history:
            if msg.get("role") in ["user", "assistant"]:
                messages.append({
                    "role": msg.get("role"),
                    "content": msg.get("content", "")
                })

    # Add the current question
    messages.append({"role": "user", "content": user})

    return messages


def _load_config() -> ChatCompletionsConfig | None:
    """Load LLM configuration from settings manager."""
    if _settings_manager is None:
        return None
    config = _settings_manager.get_chat_completions_config()
    if not config:
        return None
    return ChatCompletionsConfig(
        api_key=config.api_key,
        base_url=config.base_url,
        model=config.model
    )


def blocks_to_markdown(blocks: Iterable[AnswerBlock]) -> str:
    parts: list[str] = []
    block_list = list(blocks)
    single_block = len(block_list) == 1
    for block in block_list:
        if not (single_block and block.heading.lower() in {"response", "answer"}):
            parts.append(f"## {block.heading}")
        parts.append(block.body.strip())
        if block.citations:
            cite = ", ".join(f"`{item}`" for item in block.citations)
            parts.append("")
            parts.append(f"Citations: {cite}")
        parts.append("")
    return "\n".join(parts).strip()


def generate_answer(question: str, evidence: list[EvidenceChunk], keywords: list[str], history: Optional[list[dict]] = None) -> list[AnswerBlock] | None:
    config = _load_config()
    if not config:
        return None
    client = ChatCompletionsClient(config)
    messages = _build_messages(question, evidence, keywords, history=history)
    response = client.chat(messages)
    _, citations = _format_evidence(evidence)
    return _parse_sections(response, citations)


def stream_answer(question: str, evidence: list[EvidenceChunk], keywords: list[str], history: Optional[list[dict]] = None) -> tuple[Iterator[str], dict[int, str]] | None:
    config = _load_config()
    if not config:
        return None
    client = ChatCompletionsClient(config)
    messages = _build_messages(question, evidence, keywords, history=history)
    _, citations = _format_evidence(evidence)
    return client.stream_chat(messages), citations


def parse_answer_text(text: str, citations: dict[int, str]) -> list[AnswerBlock]:
    return _parse_sections(text, citations)
