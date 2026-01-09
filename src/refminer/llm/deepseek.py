from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Iterable, Iterator

import httpx

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency
    load_dotenv = None

if load_dotenv:
    load_dotenv()

from refminer.analyze.workflow import EvidenceChunk


CITATION_RE = re.compile(r"\[C(\d+)\]")
SECTION_RE = re.compile(r"^(Summary|Evidence|Limitations|Open Questions|Cross-check):\s*", re.IGNORECASE)
BODY_RE = re.compile(r"^body:\s*", re.IGNORECASE)


@dataclass
class AnswerBlock:
    heading: str
    body: str
    citations: list[str]


@dataclass
class DeepSeekConfig:
    api_key: str
    base_url: str
    model: str
    timeout: float = 60.0


class DeepSeekClient:
    def __init__(self, config: DeepSeekConfig) -> None:
        self._config = config

    def chat(self, messages: list[dict]) -> str:
        url = f"{self._config.base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self._config.model,
            "messages": messages,
            "stream": False,
        }
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
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self._config.timeout) as client:
            with client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()
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
        lines.append(f"[C{index}] {item.text}")
    return lines, citations


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


def _build_messages(question: str, evidence: list[EvidenceChunk], keywords: list[str]) -> list[dict]:
    evidence_lines, _ = _format_evidence(evidence)
    language_hint = "Use Chinese." if _contains_cjk(question) else "Use English."
    system = (
        "You are a research assistant. Use ONLY the provided evidence. "
        "Every factual claim must cite evidence using [C#]. "
        "If evidence is insufficient, say so. "
        "Return sections labeled: Summary, Evidence, Limitations, Open Questions. "
        "Do not add a 'Body:' label. "
        f"{language_hint}"
    )
    user = (
        f"Question: {question}\n\n"
        f"Keywords: {', '.join(keywords) if keywords else 'none'}\n\n"
        "Evidence list:\n"
        + "\n".join(evidence_lines)
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _load_config() -> DeepSeekConfig | None:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return None
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    return DeepSeekConfig(api_key=api_key, base_url=base_url, model=model)


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


def generate_answer(question: str, evidence: list[EvidenceChunk], keywords: list[str]) -> list[AnswerBlock] | None:
    config = _load_config()
    if not config:
        return None
    client = DeepSeekClient(config)
    messages = _build_messages(question, evidence, keywords)
    response = client.chat(messages)
    _, citations = _format_evidence(evidence)
    return _parse_sections(response, citations)


def stream_answer(question: str, evidence: list[EvidenceChunk], keywords: list[str]) -> tuple[Iterator[str], dict[int, str]] | None:
    config = _load_config()
    if not config:
        return None
    client = DeepSeekClient(config)
    messages = _build_messages(question, evidence, keywords)
    _, citations = _format_evidence(evidence)
    return client.stream_chat(messages), citations


def parse_answer_text(text: str, citations: dict[int, str]) -> list[AnswerBlock]:
    return _parse_sections(text, citations)
