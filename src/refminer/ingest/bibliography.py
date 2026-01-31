from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

try:
    import pdf2bib
    PDF2BIB_AVAILABLE = True
except (ImportError, Exception):
    PDF2BIB_AVAILABLE = False

logger = logging.getLogger(__name__)

DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s\"<>]+", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
LABEL_RE = re.compile(
    r"^(original article|article|abstract|keywords?|introduction)$", re.IGNORECASE
)
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
# Citation line format: 作者1,作者2 . 标题[J] . 期刊名
CITATION_LINE_RE = re.compile(
    r"^([\u4e00-\u9fff]{2,4}(?:\s*[,，]\s*[\u4e00-\u9fff]{2,4})*)\s*[\.．。]\s*"
)
# Thesis author format: 作者姓名:刘 欢 or 作者姓名：刘欢
# Use [ ] instead of \s to avoid matching newlines in the name
THESIS_AUTHOR_RE = re.compile(r"作者姓名\s*[：:]\s*([\u4e00-\u9fff ]{2,6})")
# Journal header patterns to skip (not titles)
HEADER_PATTERNS = (
    re.compile(r"^第?\s*\d+\s*卷"),  # 第 29 卷 or 29卷
    re.compile(r"^Vol\.?\s*\d+", re.IGNORECASE),  # Vol.41
    re.compile(r"^\d+$"),  # Just a number like "54"
    re.compile(r"^\d{4}\s*年\s*第?\s*\d+\s*[期号]"),  # 2021年第7期
    re.compile(r"^[\d\s/年月期卷号]+$"),  # Just numbers/dates
)


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def _is_header_block(text: str) -> bool:
    """Check if text looks like a journal header (volume/issue info)."""
    # Check first line only (blocks can be multiline)
    first_line = text.strip().split("\n")[0].strip()
    if not first_line or len(first_line) > 100:
        return False
    for pattern in HEADER_PATTERNS:
        if pattern.match(first_line):
            return True
    # Also check for common header patterns
    if re.match(r"^\d+\s*$", first_line):  # Just a number
        return True
    if "年第" in first_line and "期" in first_line:  # 2024年第52期
        return True
    return False


def _extract_citation_authors(text: str) -> list[dict[str, Any]]:
    """Extract authors from citation format: 作者1,作者2 . 标题[J]..."""
    match = CITATION_LINE_RE.match(text.strip())
    if not match:
        return []
    author_part = match.group(1)
    # Split by comma
    names = re.split(r"\s*[,，]\s*", author_part)
    authors = []
    for name in names:
        name = name.strip()
        if len(name) >= 2 and len(name) <= 4 and _contains_cjk(name):
            authors.append({"literal": name})
    return authors


def _extract_thesis_author(text: str) -> list[dict[str, Any]]:
    """Extract author from thesis format: 作者姓名:刘 欢."""
    # Check for thesis indicator
    if "作者姓名" not in text:
        return []
    match = THESIS_AUTHOR_RE.search(text)
    if not match:
        return []
    name = match.group(1).replace(" ", "").strip()
    if len(name) >= 2 and len(name) <= 4 and _contains_cjk(name):
        return [{"literal": name}]
    return []


def _is_thesis_metadata_block(text: str) -> bool:
    """Check if block looks like thesis metadata."""
    indicators = ("作者姓名", "专业名称", "指导教师", "学位类别", "论文答辩")
    count = sum(1 for ind in indicators if ind in text)
    return count >= 2


def _extract_comma_separated_authors(text: str) -> list[dict[str, Any]]:
    """Extract authors from comma-separated format: 龙井然,杜姗姗※,张景秋."""
    # Skip thesis metadata blocks - they have different format
    if _is_thesis_metadata_block(text):
        return []

    # Normalize: remove newlines, symbols, numbers
    cleaned = text.replace("\n", " ")
    cleaned = re.sub(r"[※*†‡§¶◆●○□■]", "", cleaned)
    cleaned = re.sub(r"\d+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # Check if this looks like an author line (short, comma-separated names)
    if len(cleaned) > 100:
        return []
    skip_words = ("摘要", "关键词", "基金", "项目", "作者姓名", "专业名称", "指导教师")
    if any(word in text for word in skip_words):
        return []

    # Split by commas
    parts = re.split(r"\s*[,，]\s*", cleaned)
    authors = []
    for part in parts:
        part = part.strip()
        if len(part) >= 2 and len(part) <= 4 and _contains_cjk(part):
            authors.append({"literal": part})

    # Only return if we found reasonable number of authors (2-10)
    # Single author comma-separated is unlikely
    if len(authors) >= 2 and len(authors) <= 10:
        return authors
    return []


def _deduplicate_authors(authors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove duplicate authors while preserving order."""
    seen = set()
    unique = []
    for author in authors:
        name = author.get("literal", "")
        if name and name not in seen:
            seen.add(name)
            unique.append(author)
    return unique


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

    # Skip header blocks (journal volume/issue info)
    if _is_header_block(text):
        return False

    # Skip obvious non-author blocks
    skip_patterns = (
        "摘要",
        "关键词",
        "基金项目",
        "中图分类号",
        "文献标志码",
        "文章编号",
        "作者简介",
        "。",
        "；",
    )
    text_normalized = text.replace("\n", " ")
    if any(p in text_normalized for p in skip_patterns):
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
    # Has standalone numbers (superscripts) - but not in "第X卷" pattern
    if (
        re.search(r"(?:^|\s)[1-9](?:\s|$|[,，])", text)
        and "卷" not in text
        and "期" not in text
    ):
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


def _extract_author_from_filename(filename: str) -> list[dict[str, Any]]:
    """Extract author from Chinese filename pattern: 标题_作者.pdf or 标题_作者 (1).pdf."""
    if not filename:
        return []
    # Remove extension and copy indicators like (1)
    name = re.sub(r"\s*\(\d+\)\s*\.pdf$", ".pdf", filename, flags=re.IGNORECASE)
    name = re.sub(r"\.pdf$", "", name, flags=re.IGNORECASE)

    # Pattern: 标题_作者 where 作者 is 2-4 Chinese characters
    match = re.search(r"_([\u4e00-\u9fff]{2,4})$", name)
    if match:
        author = match.group(1)
        return [{"literal": author}]
    return []


def extract_pdf_bibliography(
    text_blocks: list[str], title: str | None = None, filename: str | None = None
) -> dict[str, Any] | None:
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

    # Check if passed title looks like a header (junk from PDF metadata)
    title_from_param = title
    if title_from_param and _is_header_block(title_from_param):
        title_from_param = None  # Reject bad title

    title_value = title_from_param or _first_kv_value(kv_fields, KV_TITLE_KEYS)
    author_value = _first_kv_value(kv_fields, KV_AUTHOR_KEYS)
    year_value = _first_kv_value(kv_fields, KV_YEAR_KEYS)

    # Find title block, skipping headers (volume/issue info)
    title_block_index = None
    for idx, lines in enumerate(block_lines):
        if not lines:
            continue
        first_line = lines[0] if lines else ""
        # Skip header blocks
        if _is_header_block(first_line):
            continue
        # Skip English title blocks (usually subtitle)
        if not _contains_cjk(first_line) and len(first_line) > 10:
            continue
        # Skip affiliation blocks (contain location/university info)
        if re.search(r"[（(].*?大学|学院|研究院|北京|上海|广州", first_line):
            continue
        # Skip abstract blocks
        if "摘要" in first_line or "关键词" in first_line:
            continue
        # Accept single-line blocks with CJK content as title candidates
        if _contains_cjk(first_line) and len(first_line) > 8:
            if not _is_author_line(first_line):
                title_block_index = idx
                if not title_value:
                    title_value = first_line.strip()
                break

    # Fallback title extraction - skip headers
    if not title_value and flattened:
        for line in flattened:
            if _is_header_block(line):
                continue
            if LABEL_RE.match(line.lower()):
                continue
            # Skip non-CJK lines, affiliations, abstracts
            if not _contains_cjk(line):
                continue
            if re.search(r"[（(].*?大学|学院|研究院", line):
                continue
            if "摘要" in line or "关键词" in line:
                continue
            if len(line) > 8 and not _is_author_line(line):
                title_value = line
                break

    # Multi-strategy author extraction for Chinese journals
    authors = []

    # Strategy 1: Citation line format (作者1,作者2 . 标题[J]...)
    for block in blocks[:5]:
        citation_authors = _extract_citation_authors(block)
        if citation_authors:
            authors = citation_authors
            break

    # Strategy 2: Thesis author format (作者姓名:刘 欢) - check early!
    if not authors:
        for block in blocks[:10]:
            if _is_thesis_metadata_block(block):
                thesis_authors = _extract_thesis_author(block)
                if thesis_authors:
                    authors = thesis_authors
                    break

    # Strategy 3: Author block with affiliation markers (□黄家乐 1,2)
    # Skip thesis metadata blocks
    if not authors:
        for block in blocks[:10]:
            if _is_thesis_metadata_block(block):
                continue
            if _is_likely_author_block(block):
                authors = _extract_chinese_authors(block)
                if authors:
                    break

    # Strategy 4: Comma-separated author line (龙井然,杜姗姗,张景秋)
    if not authors:
        for block in blocks[:10]:
            # Skip if block looks like abstract or body text
            if "摘要" in block or block.count("。") > 1:
                continue
            comma_authors = _extract_comma_separated_authors(block)
            if comma_authors:
                authors = comma_authors
                break

    # Strategy 5: Traditional author line detection
    if not authors:
        author_lines: list[str] = []
        if title_block_index is not None and title_block_index + 1 < len(block_lines):
            next_block_lines = block_lines[title_block_index + 1]
            if next_block_lines:
                author_lines.append(" ".join(next_block_lines))
                author_lines.extend(next_block_lines)
        author_lines.extend(flattened[:8])
        authors = _guess_authors(author_lines)

    # Strategy 6: Author bio section (作者简介：黄家乐（1993—）...)
    if not authors:
        for line in flattened:
            if "作者简介" in line:
                authors = _extract_authors_from_bio(line)
                if authors:
                    break

    if not authors and author_value:
        authors = _guess_authors([author_value]) or [{"literal": author_value}]

    # Strategy 7 (last resort): Extract from filename pattern (标题_作者.pdf)
    if not authors and filename:
        authors = _extract_author_from_filename(filename)

    # Deduplicate authors
    authors = _deduplicate_authors(authors)

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


def merge_bibliography(
    existing: dict[str, Any] | None, extracted: dict[str, Any] | None
) -> dict[str, Any] | None:
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


def _decrypt_pdf_if_needed(pdf_path: Path) -> Path | None:
    """Decrypt PDF if encrypted, returning path to decrypted temp file.

    Returns None if PDF is not encrypted or decryption fails.
    Caller is responsible for cleaning up the temp file.
    """
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(pdf_path))
        if not reader.is_encrypted:
            return None  # Not encrypted, no temp file needed

        # Try pikepdf for decryption (handles more algorithms than PyPDF2)
        import pikepdf
        import tempfile

        with pikepdf.open(str(pdf_path), password="") as pdf:
            # Create temp file in same directory (avoid cross-drive issues on Windows)
            temp_path = pdf_path.parent / f".tmp_decrypted_{pdf_path.stem}.pdf"
            pdf.save(str(temp_path))
            logger.debug(f"Decrypted PDF to temp file: {temp_path.name}")
            return temp_path

    except Exception as e:
        logger.debug(f"PDF decryption failed for {pdf_path.name}: {e}")
        return None


def _extract_with_pdf2bib(pdf_path: Path) -> dict[str, Any] | None:
    """Extract bibliography using pdf2bib (queries CrossRef/arXiv for metadata).

    Returns None if pdf2bib is not available or extraction fails.
    """
    if not PDF2BIB_AVAILABLE:
        return None

    # Try decrypting if needed (pdf2bib/PyPDF2 can't handle encrypted PDFs)
    temp_path = _decrypt_pdf_if_needed(pdf_path)
    work_path = temp_path if temp_path else pdf_path

    try:
        # pdf2bib.pdf2bib returns a dict with 'metadata' key containing the bibliographic info
        result = pdf2bib.pdf2bib(str(work_path))
        if not result or not result.get("metadata"):
            return None

        meta = result["metadata"]
        bibliography: dict[str, Any] = {}

        # Map pdf2bib fields to our format
        if meta.get("title"):
            bibliography["title"] = meta["title"]

        if meta.get("author"):
            # pdf2bib returns authors as a list of dicts with 'given' and 'family' keys
            authors = []
            for author in meta["author"]:
                if isinstance(author, dict):
                    given = author.get("given", "")
                    family = author.get("family", "")
                    author_entry: dict[str, Any] = {}
                    if family:
                        author_entry["family"] = family
                    if given:
                        author_entry["given"] = given
                    # Also set literal as full name for display
                    if given and family:
                        author_entry["literal"] = f"{given} {family}"
                    elif family:
                        author_entry["literal"] = family
                    elif given:
                        author_entry["literal"] = given
                    # Extract ORCID if available
                    if author.get("ORCID"):
                        author_entry["orcid"] = author["ORCID"]
                    if author_entry:
                        authors.append(author_entry)
                elif isinstance(author, str):
                    authors.append({"literal": author})
            if authors:
                bibliography["authors"] = authors

        if meta.get("year"):
            try:
                bibliography["year"] = int(meta["year"])
            except (ValueError, TypeError):
                pass
        elif meta.get("issued"):
            # Some sources provide 'issued' instead of 'year'
            issued = meta["issued"]
            if isinstance(issued, dict) and issued.get("date-parts"):
                date_parts = issued["date-parts"]
                if date_parts and date_parts[0]:
                    try:
                        bibliography["year"] = int(date_parts[0][0])
                    except (ValueError, TypeError, IndexError):
                        pass

        # Check both 'DOI' (CrossRef format) and 'doi' (pdf2bib format)
        doi_value = meta.get("DOI") or meta.get("doi")
        if doi_value:
            bibliography["doi"] = doi_value
            bibliography["doi_status"] = (
                "verified"  # pdf2bib verifies DOIs via CrossRef
            )

        # Check both 'journal' (pdf2bib format) and 'container-title' (raw CrossRef format)
        journal_name = meta.get("journal") or meta.get("container-title")
        if journal_name:
            # CrossRef returns container-title as a list (e.g., ["Journal Name", "J Name"])
            if isinstance(journal_name, list) and journal_name:
                bibliography["journal"] = journal_name[0]
            elif isinstance(journal_name, str):
                bibliography["journal"] = journal_name

        if meta.get("volume"):
            bibliography["volume"] = meta["volume"]

        if meta.get("issue"):
            bibliography["issue"] = meta["issue"]

        if meta.get("page"):
            bibliography["pages"] = meta["page"]

        if meta.get("publisher"):
            bibliography["publisher"] = meta["publisher"]

        if meta.get("url"):
            bibliography["url"] = meta["url"]

        if meta.get("month"):
            try:
                bibliography["month"] = int(meta["month"])
            except (ValueError, TypeError):
                pass

        # ISSN for journals
        issn = meta.get("ISSN") or meta.get("issn")
        if issn:
            if isinstance(issn, list) and issn:
                bibliography["issn"] = issn[0]
            elif isinstance(issn, str):
                bibliography["issn"] = issn

        # ISBN for books
        isbn = meta.get("ISBN") or meta.get("isbn")
        if isbn:
            if isinstance(isbn, list) and isbn:
                bibliography["isbn"] = isbn[0]
            elif isinstance(isbn, str):
                bibliography["isbn"] = isbn

        # Determine document type from pdf2bib type field
        if meta.get("type"):
            type_map = {
                "journal-article": "J",
                "article-journal": "J",
                "article": "J",
                "book": "M",
                "book-chapter": "M",
                "proceedings-article": "C",
                "paper-conference": "C",
                "thesis": "D",
                "dissertation": "D",
            }
            doc_type = type_map.get(meta["type"].lower())
            if doc_type:
                bibliography["doc_type"] = doc_type

        if bibliography:
            extraction_info: dict[str, Any] = {
                "source": "pdf2bib",
                "identifier": result.get("identifier"),
            }
            if result.get("identifier_type"):
                extraction_info["identifier_type"] = result["identifier_type"]
            bibliography["extraction"] = extraction_info
            # Detect language from title
            if bibliography.get("title"):
                bibliography["language"] = (
                    "zh" if _contains_cjk(bibliography["title"]) else "en"
                )

        return bibliography if bibliography else None

    except Exception as e:
        logger.debug(f"pdf2bib extraction failed for {pdf_path}: {e}")
        return None

    finally:
        # Clean up temp decrypted file
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass


def extract_bibliography_from_pdf(
    pdf_path: Path | str | None,
    text_blocks: list[str],
    title: str | None = None,
    filename: str | None = None,
) -> dict[str, Any] | None:
    """Extract bibliography from a PDF file.

    Uses a two-stage approach:
    1. Try pdf2bib first (queries CrossRef/arXiv for verified metadata)
    2. Fall back to heuristic extraction from text blocks

    Args:
        pdf_path: Path to the PDF file (needed for pdf2bib)
        text_blocks: Extracted text blocks from the PDF
        title: Optional title from PDF metadata
        filename: Original filename for fallback extraction

    Returns:
        Dictionary with bibliographic metadata, or None if extraction fails
    """
    pdf2bib_result = None

    # Try pdf2bib first if we have a valid PDF path
    if pdf_path is not None:
        path = Path(pdf_path) if isinstance(pdf_path, str) else pdf_path
        if path.exists() and path.suffix.lower() == ".pdf":
            pdf2bib_result = _extract_with_pdf2bib(path)
            if pdf2bib_result:
                logger.debug(f"pdf2bib extracted metadata for {path.name}")

    # Fall back to heuristic extraction
    heuristic_result = extract_pdf_bibliography(text_blocks, title, filename)

    # Merge results: pdf2bib takes priority, heuristics fill gaps
    if pdf2bib_result and heuristic_result:
        # pdf2bib result is more reliable, use it as base and fill gaps from heuristics
        merged = dict(pdf2bib_result)
        for key, value in heuristic_result.items():
            if key == "extraction":
                continue  # Keep pdf2bib's extraction source
            if key not in merged or merged.get(key) is None:
                merged[key] = value
        return merged
    elif pdf2bib_result:
        return pdf2bib_result
    else:
        return heuristic_result
