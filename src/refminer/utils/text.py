from __future__ import annotations

import re
from typing import Iterable


ABSTRACT_RE = re.compile(
    r"^\s*(?:abstract|摘要|摘\s*要)\s*[:：\-–—]?\s*(.*)$",
    re.IGNORECASE,
)
SECTION_BREAK_RE = re.compile(
    r"^\s*(?:"
    r"(?:\d+\s*[\.、]?\s*)?introduction|"
    r"(?:\d+\s*[\.、]?\s*)?(?:引言|绪论|前言)|"
    r"keywords?|key\s*words|index\s*terms|"
    r"(?:关键词|关键字|主题词)"
    r")\s*[:：]?\s*.*$",
    re.IGNORECASE,
)


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in text.split("\n")]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def detect_abstract(lines: Iterable[str]) -> str | None:
    collecting = False
    collected: list[str] = []
    for line in lines:
        header_match = ABSTRACT_RE.match(line)
        if header_match:
            collecting = True
            trailing = header_match.group(1).strip()
            if trailing:
                collected.append(trailing)
            continue
        if collecting and SECTION_BREAK_RE.match(line):
            break
        if collecting:
            collected.append(line)
    if not collected:
        return None
    return " ".join(collected).strip()


def simple_sectionize(lines: Iterable[str]) -> list[tuple[str, list[str]]]:
    sections: list[tuple[str, list[str]]] = []
    current_title = "Body"
    current_lines: list[str] = []
    for line in lines:
        if len(line) <= 80 and line.isupper():
            if current_lines:
                sections.append((current_title, current_lines))
            current_title = line.strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines:
        sections.append((current_title, current_lines))
    return sections
