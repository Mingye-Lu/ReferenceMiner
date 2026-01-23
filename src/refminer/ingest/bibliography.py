from __future__ import annotations

import re
from typing import Any


DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s\"<>]+", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
LABEL_RE = re.compile(r"^(original article|article|abstract|keywords?|introduction)$", re.IGNORECASE)
META_KV_RE = re.compile(r"^(?P<key>[^=]{1,20})=(?P<value>.+)$")

KV_TITLE_KEYS = ("书名", "题名")
KV_AUTHOR_KEYS = ("作者", "作者名", "编者", "主编")
KV_YEAR_KEYS = ("出版年", "出版日期", "年份", "年")

# Chinese journal patterns
# Article number format: 文章编号：1001-7518（2025）12-077-11
ARTICLE_NUMBER_RE = re.compile(r"文章编号[：:]\s*[\d\-]+[（(](\d{4})[）)]")
# Author bio format: 作者简介：黄家乐（1993—），女，...
AUTHOR_BIO_RE = re.compile(r"作者简介[：:]\s*(.+?)(?:[（(]\d{4}|$)")
# Chinese name with affiliation superscripts: □黄家乐 1，2 or 黄家乐1,2
CHINESE_AUTHOR_LINE_RE = re.compile(
    r"^[□■◆●○]?\s*"  # Optional prefix symbols
    r"([\u4e00-\u9fff]{2,4})"  # Chinese name (2-4 chars)
    r"(?:\s*[1-9,，、\s]+)*"  # Optional affiliation numbers
)
# Multiple Chinese authors pattern
CHINESE_AUTHORS_BLOCK_RE = re.compile(
    r"[□■◆●○]?\s*([\u4e00-\u9fff]{2,4})\s*[1-9,，、\s]*"
)


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def _normalize_line(line: str) -> str:
    return " ".join(line.strip().split())


def _first_kv_value(kv_fields: dict[str, str], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = kv_fields.get(key)
        if value:
            return value
    return None


def _clean_doi(doi: str) -> str:
    return doi.rstrip(").,;").strip()


def _extract_doi(text: str) -> str | None:
    matches = [m.group(0) for m in DOI_RE.finditer(text)]
    if not matches:
        return None
    cleaned = [_clean_doi(m) for m in matches]
    # Prefer the most frequent DOI if multiple candidates appear.
    freq: dict[str, int] = {}
    for item in cleaned:
        freq[item] = freq.get(item, 0) + 1
    return sorted(freq.items(), key=lambda item: (-item[1], len(item[0])))[0][0]


def _clean_author_name(text: str) -> str:
    name = text.strip()
    name = re.sub(r"^and\s+", "", name, flags=re.IGNORECASE).strip()
    if "," in name:
        name = name.split(",", 1)[0].strip()
    return name


def _is_author_line(line: str) -> bool:
    lowered = line.lower()
    if ";" in line:
        return True
    if " and " in lowered:
        return True
    if line.count(",") >= 2:
        return True
    return False


def _is_likely_author_block(text: str) -> bool:
    """Check if text looks like a Chinese author block.

    Author blocks typically have:
    - □ or similar symbols before names
    - Affiliation superscript numbers like 1,2 or 1，2
    - Short length (< 100 chars typically)
    - No sentence-ending punctuation patterns
    """
    if len(text) > 150:
        return False

    # Skip obvious non-author blocks
    skip_patterns = ("摘要", "关键词", "基金项目", "中图分类号", "文献标志码",
                     "文章编号", "作者简介", "。", "；", "，", "：")
    # Allow single Chinese comma but not multiple sentence structures
    text_normalized = text.replace("\n", " ")
    if any(p in text_normalized for p in skip_patterns[:7]):
        return False
    # Check for sentence-ending punctuation (indicates body text)
    if text_normalized.count("。") > 0:
        return False
    if text_normalized.count("；") > 0:
        return False

    # Positive signals for author block
    signals = 0
    # Has □ or similar author marker symbols
    if re.search(r"[□■◆●○]", text):
        signals += 2
    # Has affiliation numbers pattern (1,2 or 1，2)
    if re.search(r"\d\s*[,，、]\s*\d", text):
        signals += 2
    # Has standalone numbers (superscripts)
    if re.search(r"(?:^|\s)[1-9](?:\s|$|[,，])", text):
        signals += 1
    # Short block with Chinese chars
    if len(text) < 80 and _contains_cjk(text):
        signals += 1

    return signals >= 2


def _extract_chinese_authors(text: str) -> list[dict[str, Any]]:
    """Extract Chinese author names from text with affiliation numbers.

    Handles formats like:
    - □黄家乐 1，2  宋亦芳 1，2
    - 黄家乐1,2 宋亦芳1,2
    - 黄家乐  宋亦芳
    - 1,2   宋亦芳 (numbers before name)
    """
    # First check if this looks like an author block at all
    if not _is_likely_author_block(text):
        return []

    authors = []

    # Pattern: Find Chinese names (2-4 chars) that appear near affiliation numbers or symbols
    # Remove affiliation numbers and symbols to isolate names
    cleaned = re.sub(r"[□■◆●○]", " ", text)
    cleaned = re.sub(r"\d+[,，、\s]*\d*", " ", cleaned)  # Remove "1,2" style numbers
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # Find sequences of 2-4 Chinese characters
    name_pattern = re.compile(r"([\u4e00-\u9fff]{2,4})")
    matches = name_pattern.findall(cleaned)

    for name in matches:
        name = name.strip()
        if len(name) >= 2 and len(name) <= 4:
            authors.append({"literal": name})

    return authors


def _extract_authors_from_bio(text: str) -> list[dict[str, Any]]:
    """Extract author names from 作者简介 section.

    Format: 作者简介：黄家乐（1993—），女，山东临沂人，...；宋亦芳（1959 —），男，...
    """
    # Pattern to find names before birth years
    bio_author_re = re.compile(r"([\u4e00-\u9fff]{2,4})\s*[（(]\s*\d{4}\s*[-—]")
    matches = bio_author_re.findall(text)
    return [{"literal": name} for name in matches if len(name) >= 2]


def _guess_authors(lines: list[str]) -> list[dict[str, Any]]:
    # First pass: look for Chinese author blocks specifically
    for line in lines:
        if not line:
            continue
        if len(line) > 200:
            continue
        if any(token in line for token in ("摘要", "关键词", "基金项目")):
            continue

        # Try Chinese author extraction (requires author block detection)
        if _contains_cjk(line):
            chinese_authors = _extract_chinese_authors(line)
            if chinese_authors:
                return chinese_authors

    # Second pass: look for Western-style author lines (for English papers)
    for line in lines:
        if not line:
            continue
        if len(line) > 200:
            continue
        lowered = line.lower()
        if any(token in lowered for token in ("abstract", "keywords")):
            continue
        # Skip Chinese text in this pass - it should have been handled above
        if _contains_cjk(line):
            continue
        if not _is_author_line(line):
            continue
        if ";" in line:
            segments = [seg.strip() for seg in line.split(";") if seg.strip()]
        else:
            segments = re.split(r"\s+and\s+|\s*,\s*|\s*，\s*", line)
        authors = []
        for segment in segments:
            name = _clean_author_name(segment)
            if not name or len(name) < 2:
                continue
            authors.append({"literal": name})
        if authors:
            return authors
    return []


def _guess_year(text: str) -> int | None:
    match = YEAR_RE.search(text)
    if not match:
        return None
    try:
        return int(match.group(0))
    except ValueError:
        return None


def _extract_publication_year(text: str) -> int | None:
    """Extract publication year from Chinese journal article metadata.

    Prioritizes structured sources:
    1. 文章编号：1001-7518（2025）12-077-11
    2. General year pattern as fallback
    """
    # Try article number pattern first (most reliable for publication year)
    match = ARTICLE_NUMBER_RE.search(text)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass

    # Fallback to general year extraction
    return _guess_year(text)


def _guess_doc_type(text: str) -> str | None:
    lowered = text.lower()
    if "journal" in lowered or "original article" in lowered:
        return "J"
    if "proceedings" in lowered or "conference" in lowered:
        return "C"
    if "thesis" in lowered or "dissertation" in lowered:
        return "D"
    return None


def extract_pdf_bibliography(text_blocks: list[str], title: str | None = None) -> dict[str, Any] | None:
    if not text_blocks:
        return None

    # Use more blocks for Chinese journals (metadata often at bottom of first page)
    blocks = text_blocks[:15]
    kv_fields: dict[str, str] = {}
    for block in blocks:
        for raw_line in block.splitlines():
            line = _normalize_line(raw_line)
            if not line:
                continue
            match = META_KV_RE.match(line)
            if not match:
                continue
            key = match.group("key").strip()
            value = match.group("value").strip()
            if key and value and key not in kv_fields:
                kv_fields[key] = value
    block_lines: list[list[str]] = []
    for block in blocks:
        lines = [_normalize_line(line) for line in block.splitlines() if line.strip()]
        block_lines.append(lines)

    flattened = [line for lines in block_lines for line in lines]
    combined_text = "\n".join(flattened)

    title_value = title or _first_kv_value(kv_fields, KV_TITLE_KEYS)
    author_value = _first_kv_value(kv_fields, KV_AUTHOR_KEYS)
    year_value = _first_kv_value(kv_fields, KV_YEAR_KEYS)
    title_block_index = None
    for idx, lines in enumerate(block_lines):
        if not lines:
            continue
        if len(lines) >= 2 and all(not LABEL_RE.match(line.lower()) for line in lines[:2]):
            if not _is_author_line(" ".join(lines)):
                title_block_index = idx
                if not title_value:
                    title_value = " ".join(lines).strip()
                break
    if not title_value and flattened:
        for line in flattened:
            if LABEL_RE.match(line.lower()):
                continue
            if len(line) > 8 and not _is_author_line(line):
                title_value = line
                break

    # For Chinese journals, search all early blocks for author patterns
    # (author block may not be immediately after title due to subtitles, etc.)
    authors = []
    for block in blocks[:10]:
        if _is_likely_author_block(block):
            authors = _extract_chinese_authors(block)
            if authors:
                break

    # Fallback: traditional author line detection
    if not authors:
        author_lines: list[str] = []
        if title_block_index is not None and title_block_index + 1 < len(block_lines):
            next_block_lines = block_lines[title_block_index + 1]
            if next_block_lines:
                author_lines.append(" ".join(next_block_lines))
                author_lines.extend(next_block_lines)
        author_lines.extend(flattened[:8])
        authors = _guess_authors(author_lines)

    # Fallback: try extracting from author bio section (作者简介)
    if not authors:
        for line in flattened:
            if "作者简介" in line:
                authors = _extract_authors_from_bio(line)
                if authors:
                    break

    if not authors and author_value:
        authors = _guess_authors([author_value]) or [{"literal": author_value}]

    # Use publication year extraction (prioritizes article number format)
    year = _extract_publication_year(combined_text)
    if not year and year_value:
        match = YEAR_RE.search(year_value)
        if match:
            try:
                year = int(match.group(0))
            except ValueError:
                year = None

    doi = _extract_doi(combined_text)
    doc_type = _guess_doc_type(combined_text)

    # Detect Chinese journal articles by article number pattern
    if not doc_type and ARTICLE_NUMBER_RE.search(combined_text):
        doc_type = "J"

    if not doc_type and any(key in kv_fields for key in KV_TITLE_KEYS):
        doc_type = "M"

    bibliography: dict[str, Any] = {}
    if title_value:
        bibliography["title"] = title_value
    if authors:
        bibliography["authors"] = authors
    if year:
        bibliography["year"] = year
    if doi:
        bibliography["doi"] = doi
        bibliography["doi_status"] = "extracted"
    if doc_type:
        bibliography["doc_type"] = doc_type
    if title_value:
        bibliography["language"] = "zh" if _contains_cjk(title_value) else "en"

    if bibliography:
        bibliography["extraction"] = {"source": "pdf_text"}
    return bibliography or None


def merge_bibliography(existing: dict[str, Any] | None, extracted: dict[str, Any] | None) -> dict[str, Any] | None:
    if not extracted:
        return existing
    if not existing:
        return extracted

    merged = dict(existing)
    for key, value in extracted.items():
        if value is None:
            continue
        if key == "authors":
            if not merged.get("authors"):
                merged["authors"] = value
            continue
        if key == "extraction":
            if "extraction" not in merged:
                merged["extraction"] = value
            continue
        if not merged.get(key):
            merged[key] = value
    return merged
