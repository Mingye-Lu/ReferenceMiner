from __future__ import annotations

import re
from typing import Iterable

import ftfy


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
    """
    Normalize text by fixing encoding issues, converting fullwidth characters,
    and cleaning whitespace.

    This handles:
    - Fullwidth characters
    - Mojibake and encoding errors
    - HTML entities
    - Hyphenation artifacts from PDFs (e.g., "compre-\nhensive" -> "comprehensive")
    - Special dashes and hyphens (em dash, en dash, minus)
    - Non-breaking spaces and zero-width characters
    - Excessive whitespace
    """
    # Apply ftfy to fix encoding issues and convert fullwidth characters
    text = ftfy.fix_text(text)

    # Normalize line breaks
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove non-breaking spaces and zero-width characters
    text = text.replace("\xa0", " ")  # Non-breaking space
    text = text.replace("\u200b", "")  # Zero-width space
    text = text.replace("\u200c", "")  # Zero-width non-joiner
    text = text.replace("\u200d", "")  # Zero-width joiner
    text = text.replace("\ufeff", "")  # Zero-width no-break space (BOM)

    # Normalize special dashes to standard hyphen
    text = text.replace("—", "-")  # Em dash
    text = text.replace("–", "-")  # En dash
    text = text.replace("−", "-")  # Minus sign

    # Fix hyphenation artifacts (words split across lines)
    # Match: word + hyphen + optional whitespace + newline + optional whitespace + word
    text = re.sub(r"(\w+)-\s*\n\s*(\w+)", r"\1\2", text)

    # Normalize excessive whitespace within lines (multiple spaces/tabs -> single space)
    text = re.sub(r"[ \t]+", " ", text)

    # Strip and filter empty lines
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
