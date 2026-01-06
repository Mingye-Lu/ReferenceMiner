from __future__ import annotations

import re
from typing import Iterable


ABSTRACT_RE = re.compile(r"^\s*abstract\s*$", re.IGNORECASE)
INTRO_RE = re.compile(r"^\s*(introduction|1\.\s*introduction|keywords)\s*$", re.IGNORECASE)


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in text.split("\n")]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def detect_abstract(lines: Iterable[str]) -> str | None:
    collecting = False
    collected: list[str] = []
    for line in lines:
        if ABSTRACT_RE.match(line):
            collecting = True
            continue
        if collecting and INTRO_RE.match(line):
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
