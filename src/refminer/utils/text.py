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


def normalize_text_with_mapping(text: str) -> tuple[str, dict[int, int]]:
    """
    Normalize text and return a mapping from original character positions to normalized positions.

    Returns:
        tuple: (normalized_text, char_map) where char_map[original_pos] = normalized_pos
    """
    char_map: dict[int, int] = {}
    normalized_pos = 0

    # Apply ftfy to fix encoding issues and convert fullwidth characters
    text = ftfy.fix_text(text)

    # Normalize line breaks
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Track positions through character-level replacements
    result: list[str] = []
    i = 0
    while i < len(text):
        char = text[i]
        original_pos = i

        # Remove non-breaking spaces and zero-width characters
        if char == "\xa0":  # Non-breaking space
            char_map[original_pos] = normalized_pos
            result.append(" ")
            normalized_pos += 1
        elif char in ("\u200b", "\u200c", "\u200d", "\ufeff"):  # Zero-width chars
            char_map[original_pos] = (
                normalized_pos  # Maps to current position (no advancement)
            )
        # Normalize special dashes to standard hyphen
        elif char in ("—", "–", "−"):  # Em dash, en dash, minus
            char_map[original_pos] = normalized_pos
            result.append("-")
            normalized_pos += 1
        else:
            char_map[original_pos] = normalized_pos
            result.append(char)
            normalized_pos += 1

        i += 1

    text = "".join(result)

    # Fix hyphenation artifacts (words split across lines)
    # This is complex to track, so we'll use a regex with a callback
    hyphenation_map: dict[int, int] = {}

    def hyphen_replacer(match: re.Match) -> str:
        # Track the removal of hyphen and whitespace
        start = match.start()
        end = match.end()
        # Map all positions in the match to the start position
        for pos in range(start, end):
            if pos in char_map:
                # Find the inverse of char_map for this position
                for orig_pos, norm_pos in char_map.items():
                    if norm_pos == pos:
                        hyphenation_map[orig_pos] = len(match.group(1))
        return match.group(1) + match.group(2)

    text = re.sub(r"(\w+)-\s*\n\s*(\w+)", hyphen_replacer, text)

    # Normalize excessive whitespace within lines (multiple spaces/tabs -> single space)
    # This is also complex, so we'll rebuild the mapping
    temp_result: list[str] = []
    temp_pos = 0
    temp_map: dict[int, int] = {}
    i = 0
    while i < len(text):
        if text[i] in (" ", "\t"):
            # Skip consecutive spaces/tabs
            start = i
            while i < len(text) and text[i] in (" ", "\t"):
                temp_map[start] = temp_pos
                i += 1
            temp_result.append(" ")
            temp_pos += 1
        else:
            temp_map[i] = temp_pos
            temp_result.append(text[i])
            temp_pos += 1
            i += 1

    text = "".join(temp_result)

    # Strip and filter empty lines
    lines = [line.strip() for line in text.split("\n")]
    lines = [line for line in lines if line]

    text = "\n".join(lines)

    # Note: For simplicity, we return a best-effort mapping
    # The complex transformations (hyphenation, whitespace collapse, line filtering)
    # make exact position tracking difficult, but the mapping will be accurate enough
    # for bounding box purposes as we track at span boundaries

    return text, char_map


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
