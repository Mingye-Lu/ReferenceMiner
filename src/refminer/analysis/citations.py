"""
Reference parsing logic for extracting citations from document text.
Enhanced to properly identify reference sections and parse individual items.
"""

import re
from typing import List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class CitationItem:
    """Represents a parsed citation/reference item."""

    raw_text: str
    ref_number: Optional[int] = None  # Original reference number [1], [2], etc.
    title: Optional[str] = None
    authors: Optional[List[str]] = None
    year: Optional[int] = None
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    url: Optional[str] = None
    source_type: str = "unknown"  # "arxiv", "doi", "url", "text"
    availability: str = (
        "unavailable"  # "downloadable", "link_only", "searchable", "unavailable"
    )
    needs_metadata_fetch: bool = False  # True if has link but missing author/year


class ReferenceParser:
    """Parses text to extract reference list items from academic documents."""

    # Regex patterns for identifiers
    DOI_PATTERN = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
    # Match arxiv:XXXX.XXXXX or arXiv:XXXX.XXXXX or just XXXX.XXXXX in arxiv context
    ARXIV_PATTERN = re.compile(
        r"(?:arxiv[:\s]*)(\d{4}\.\d{4,5}(?:v\d+)?)", re.IGNORECASE
    )
    # Also match standalone arXiv IDs that might appear without prefix
    ARXIV_STANDALONE = re.compile(r"\b(\d{4}\.\d{4,5}(?:v\d+)?)\b")
    URL_PATTERN = re.compile(
        r"https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[^\s,\]]*", re.IGNORECASE
    )

    # Reference section header patterns
    REF_SECTION_HEADERS = [
        r"^\s*REFERENCES\s*$",
        r"^\s*References\s*$",
        r"^\s*BIBLIOGRAPHY\s*$",
        r"^\s*Bibliography\s*$",
        r"^\s*Literature\s+Cited\s*$",
        r"^\s*Works\s+Cited\s*$",
    ]

    # Patterns that usually indicate the reference section ended.
    REF_SECTION_TERMINATORS = [
        r"^\s*(?:[A-Z]\.\s+)?Appendix\b",
        r"^\s*[A-Z]\.\s+.*\bAppendix\b",
        r"^\s*Supplementary\s+(?:Material|Information)\b",
        r"^\s*Acknowledg(?:e)?ments?\b",
    ]

    # Reference number patterns (to detect the numbering format)
    REF_NUMBER_PATTERNS = [
        (r"^\[(\d+)\]", "bracket"),  # [1], [2], ...
        (r"^(\d+)\.\s", "dot"),  # 1. 2. ...
        (r"^\((\d+)\)", "paren"),  # (1), (2), ...
    ]

    # Title extraction patterns — covers straight, curly, guillemet quotes
    QUOTED_TITLE = re.compile(r'["“”«»‘’‚„]([^"“”«»‘’‚„]{10,})["“”«»‘’‚„]')
    # IEEE-style: comma followed by space and a quoted title
    IEEE_COMMA_TITLE = re.compile(r',\s*["“”«‘]([^"“”»’]{10,})["“”»’]')
    ITALIC_MARKER = re.compile(r"\*([^*]+)\*|_([^_]+)_")

    # Patterns to filter out (not actual references)
    NOISE_PATTERNS = [
        re.compile(r"^\[Online\]", re.IGNORECASE),
        re.compile(r"^\[Accessed", re.IGNORECASE),
        re.compile(r"^Available:", re.IGNORECASE),
    ]

    # Pattern to detect [Online] tag anywhere in text
    ONLINE_TAG_PATTERN = re.compile(r"\[[^\]]*online[^\]]*\]", re.IGNORECASE)

    # Pattern to clean [Online] and similar from text
    BRACKET_NOISE_PATTERN = re.compile(
        r"\s*\[[^\]]*(?:online|accessed|available)[^\]]*\]\s*\.?", re.IGNORECASE
    )

    def extract_references(self, text: str) -> List[CitationItem]:
        """
        Extracts references from the provided text.
        Starts from the bottom to find the reference section.
        """
        # Find reference section
        ref_section, section_start = self._find_reference_section(text)
        if not ref_section:
            # Fallback: try last 20% of document for short docs
            if len(text) < 10000:
                ref_section = text[-int(len(text) * 0.3) :]
            else:
                ref_section = text[-int(len(text) * 0.15) :]

        # Detect numbering format
        number_format = self._detect_number_format(ref_section)

        # Split into items
        items = self._split_references(ref_section, number_format)

        parsed_items = []
        for i, (ref_num, raw) in enumerate(items):
            parsed = self._parse_item(raw, ref_num if ref_num else i + 1)
            if parsed:
                parsed_items.append(parsed)

        # Sort by ref_number
        parsed_items.sort(key=lambda x: x.ref_number or 9999)

        return parsed_items

    def _find_reference_section(self, text: str) -> Tuple[Optional[str], int]:
        """
        Locates the reference section by searching from the end of document.
        Returns (section_text, start_position).
        """
        lines = text.split("\n")

        # Search from bottom for reference header
        for header_pattern in self.REF_SECTION_HEADERS:
            pattern = re.compile(header_pattern, re.MULTILINE)
            matches = list(pattern.finditer(text))
            if matches:
                # Take the last occurrence (avoid TOC references)
                last_match = matches[-1]
                section = text[last_match.end() :]
                section = self._truncate_reference_section(section)
                return section, last_match.end()

        return None, -1

    def _truncate_reference_section(self, section_text: str) -> str:
        """Cuts off likely non-reference content (appendix, acknowledgements)."""
        lines = section_text.split("\n")
        if len(lines) < 12:
            return section_text

        for i, raw_line in enumerate(lines):
            if i < 8:
                continue
            line = raw_line.strip()
            if not line:
                continue
            if self._is_reference_terminator_line(line):
                return "\n".join(lines[:i])

        return section_text

    def _is_reference_terminator_line(self, line: str) -> bool:
        for pattern in self.REF_SECTION_TERMINATORS:
            if re.match(pattern, line, re.IGNORECASE):
                return True

        # Catch common heading variants like "Overview of the Appendix" while
        # avoiding long body lines that merely mention the word.
        if len(line) <= 120 and re.search(r"\bappendix\b", line, re.IGNORECASE):
            return True
        return False

    def _detect_number_format(self, text: str) -> Optional[str]:
        """Detects which numbering format is used in the reference section.
        Only matches patterns at the START of a line.
        Filters out year-like numbers (1900-2099)."""
        lines = text.split("\n")
        format_counts = {"bracket": 0, "dot": 0, "paren": 0}

        for line in lines[:50]:  # Check first 50 lines
            line = line.strip()
            # Only match at line start (already stripped)
            for pattern, fmt in self.REF_NUMBER_PATTERNS:
                match = re.match(pattern, line)
                if match:
                    # Extract the number and filter out year-like values
                    num = int(match.group(1))
                    if 1900 <= num <= 2099:
                        # This looks like a year, skip it
                        continue
                    format_counts[fmt] += 1
                    break

        # Return the most common format
        best_format: Optional[str] = None
        best_count = 0
        for fmt, count in format_counts.items():
            if count > best_count:
                best_format = fmt
                best_count = count

        if best_count > 0:
            return best_format
        return None

    def _split_references(
        self, text: str, number_format: Optional[str]
    ) -> List[Tuple[Optional[int], str]]:
        """
        Splits the reference section into individual citation strings.
        Returns list of (ref_number, raw_text) tuples.
        Reference numbers must be at true line start (after newline or start of text).
        Strictly uses detected format - will NOT match other formats.
        Filters out year-like numbers (1900-2099) being used as ref numbers.
        """
        lines = text.split("\n")
        refs: List[Tuple[Optional[int], str]] = []
        current_ref: List[str] = []
        current_num: Optional[int] = None
        seen_numbers: set[int] = set()

        # If no format detected, try bracket as default (most common)
        if not number_format:
            number_format = "bracket"

        # Strictly use ONLY the detected format pattern
        if number_format == "bracket":
            start_pattern = re.compile(r"^\s*\[(\d+)\]\s*(.*)$")
        elif number_format == "dot":
            start_pattern = re.compile(r"^\s*(\d+)\.\s+(.*)$")
        elif number_format == "paren":
            start_pattern = re.compile(r"^\s*\((\d+)\)\s*(.*)$")
        else:
            start_pattern = re.compile(r"^\s*\[(\d+)\]\s*(.*)$")  # Fallback to bracket

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            if self._is_reference_terminator_line(stripped):
                break

            # Skip noise patterns like [Online]
            if any(p.match(stripped) for p in self.NOISE_PATTERNS):
                continue

            # Match using the strictly detected format
            line_start_match = start_pattern.match(line)

            if line_start_match:
                groups = line_start_match.groups()
                ref_num_str = groups[0]
                ref_num = int(ref_num_str) if ref_num_str else None

                if ref_num and current_num is not None:
                    # Reference lists are usually strictly increasing.
                    # A restart at a small number after many references
                    # typically indicates we entered appendix/body citations.
                    if ref_num <= current_num:
                        if len(refs) >= 8 and ref_num <= 5:
                            break
                        continue
                    if ref_num in seen_numbers:
                        if len(refs) >= 8:
                            break
                        continue

                # Filter out year-like numbers (1900-2099) being used as ref numbers
                # These are likely [2021], [2022] etc being misidentified
                if ref_num and 1900 <= ref_num <= 2099:
                    # This looks like a year, treat as continuation
                    if current_ref is not None:
                        current_ref.append(stripped)
                    continue

                # Save previous reference
                if current_ref:
                    refs.append((current_num, " ".join(current_ref)))

                current_num = ref_num
                if ref_num:
                    seen_numbers.add(ref_num)
                rest = groups[1] if len(groups) > 1 else ""
                current_ref = [rest.strip()] if rest and rest.strip() else []
            else:
                # Continuation line
                if current_ref is not None:
                    current_ref.append(stripped)

        # Don't forget the last reference
        if current_ref:
            refs.append((current_num, " ".join(current_ref)))

        # Filter out entries without valid ref numbers or with ref_number 0
        valid_refs: List[Tuple[int, str]] = []
        for num, raw_text in refs:
            if isinstance(num, int) and num > 0:
                valid_refs.append((num, raw_text))

        # Keep first occurrence for each reference number.
        deduped: List[Tuple[Optional[int], str]] = []
        seen: set[int] = set()
        for num, raw_text in valid_refs:
            if num in seen:
                continue
            seen.add(num)
            deduped.append((num, raw_text))

        return deduped

    def _parse_item(self, text: str, ref_number: int) -> Optional[CitationItem]:
        """Parses a single reference text string into structured data."""
        if len(text) < 10:  # Too short
            return None

        # Check for [Online] tag before cleaning
        has_online_tag = bool(self.ONLINE_TAG_PATTERN.search(text))

        # Clean text of [Online], [Accessed], etc. before parsing
        cleaned_text = self.BRACKET_NOISE_PATTERN.sub("", text).strip()
        # Also remove "Available:" prefix
        cleaned_text = re.sub(r"^Available:\s*", "", cleaned_text, flags=re.IGNORECASE)

        if re.fullmatch(r"(?:\[\d+\]\s*){2,}", cleaned_text):
            return None
        if not re.search(r"[A-Za-z]{3,}", cleaned_text):
            return None

        # Extract identifiers from cleaned text
        doi_match = self.DOI_PATTERN.search(cleaned_text)
        arxiv_match = self.ARXIV_PATTERN.search(cleaned_text)
        url_match = self.URL_PATTERN.search(cleaned_text)

        doi = doi_match.group(0) if doi_match else None
        arxiv_id = arxiv_match.group(1) if arxiv_match else None
        url = url_match.group(0) if url_match else None

        # If no explicit arxiv pattern, check for standalone ID near "arxiv" mention
        if not arxiv_id and "arxiv" in cleaned_text.lower():
            standalone = self.ARXIV_STANDALONE.search(cleaned_text)
            if standalone:
                arxiv_id = standalone.group(1)

        # Extract year early so we can trim trailing OCR noise safely.
        year = self._extract_year(cleaned_text)
        cleaned_text = self._trim_reference_noise(
            cleaned_text, doi=doi, arxiv_id=arxiv_id, year=year
        )

        # Re-extract year after trimming and then parse structured fields.
        year = self._extract_year(cleaned_text)
        title = self._extract_title(cleaned_text)
        authors = self._extract_authors(cleaned_text, title)

        # Check if missing metadata but has identifiers
        has_identifier = bool(doi or arxiv_id or url)
        # Always fetch if identifier exists to ensure quality (fixes issues where parsed metadata is poor)
        needs_fetch = has_identifier

        # Determine source type and availability with new logic
        source_type, availability, title = self._classify_availability(
            doi, arxiv_id, url, title, authors, year, has_online_tag
        )

        return CitationItem(
            raw_text=cleaned_text,
            ref_number=ref_number,
            title=title,
            authors=authors,
            year=year,
            doi=doi,
            arxiv_id=arxiv_id,
            url=url,
            source_type=source_type,
            availability=availability,
            needs_metadata_fetch=needs_fetch,
        )

    def _trim_reference_noise(
        self,
        text: str,
        doi: Optional[str],
        arxiv_id: Optional[str],
        year: Optional[int],
    ) -> str:
        """Trim common OCR spillover that appears after the true reference body."""
        trimmed = text.strip()

        appendix_markers = [
            "overview of the appendix",
            "this appendix is organized",
            "supplementary material",
            "acknowledgments",
            "acknowledgements",
        ]
        lowered = trimmed.lower()
        for marker in appendix_markers:
            idx = lowered.find(marker)
            if idx > 0:
                trimmed = trimmed[:idx].strip()
                lowered = trimmed.lower()

        if arxiv_id:
            arxiv_tail = re.search(
                r"arxiv[:\s]*\d{4}\.\d{4,5}(?:v\d+)?(?:\s*,\s*)?(?:19\d{2}|20[0-2]\d)?(?:\s*\.\s*\d+(?:\s*,\s*\d+)*)?",
                trimmed,
                flags=re.IGNORECASE,
            )
            if arxiv_tail:
                trimmed = trimmed[: arxiv_tail.end()].strip()

        if doi:
            doi_tail = self.DOI_PATTERN.search(trimmed)
            if doi_tail and doi_tail.end() < len(trimmed):
                tail = trimmed[doi_tail.end() :]
                if "appendix" in tail.lower() or "supplement" in tail.lower():
                    trimmed = trimmed[: doi_tail.end()].strip()

        if year:
            year_matches = list(re.finditer(rf"\b{year}\b", trimmed))
            if year_matches:
                end = year_matches[-1].end()
                tail = trimmed[end:]
                keep = re.match(r"^[\s\]\)\.,;:-]*(?:\d+(?:\s*,\s*\d+)*)?", tail)
                kept_tail = keep.group(0) if keep else ""
                extra = tail[len(kept_tail) :].strip()
                if len(extra) >= 15 and re.search(r"[A-Za-z]", extra):
                    trimmed = (trimmed[:end] + kept_tail).strip()

        return trimmed

    def _extract_title(self, text: str) -> Optional[str]:
        """Extracts the title from a reference string."""
        title = None

        # 1. Try quoted title (most reliable for IEEE / APA styles)
        quoted = self.QUOTED_TITLE.search(text)
        if quoted:
            title = quoted.group(1).strip()
        else:
            # 1b. Try IEEE comma-quote pattern: , "Title,"
            ieee = self.IEEE_COMMA_TITLE.search(text)
            if ieee:
                title = ieee.group(1).strip()

        # 2. Try italic markers (*Title* or _Title_)
        if not title:
            italic = self.ITALIC_MARKER.search(text)
            if italic:
                title = (italic.group(1) or italic.group(2)).strip()

        # 3. Heuristic: skip author initials, find first long sentence segment
        if not title:
            # Split by sentence-ending periods (skip single-letter initials)
            # Pattern: period followed by space, where preceding char is NOT
            # a single uppercase letter (author initial like "R." or "D.")
            parts = re.split(r"(?<![A-Z])\.\s+", text)

            for part in parts:
                part = part.strip()
                if len(part) < 15:
                    continue
                # Skip parts that look like author lists
                if re.match(r"^[A-Z]\.\s", part):
                    continue
                if self._looks_like_venue(part):
                    continue
                # Skip parts that are mostly short comma-separated tokens (author names)
                tokens = part.split(", ")
                avg_token_len = sum(len(t) for t in tokens) / max(len(tokens), 1)
                if len(tokens) > 3 and avg_token_len < 12:
                    continue
                title = part
                break

        # 4. Fallback: first 120 chars
        if not title:
            title = text[:120].strip() + "..." if len(text) > 120 else text.strip()

        # Clean up trailing punctuation (keep ? and !)
        if title:
            title = re.sub(r"[,.:;]+$", "", title).strip()

        return title

    def _looks_like_venue(self, text: str) -> bool:
        """Check if text looks like a journal/conference name."""
        venue_indicators = [
            "journal",
            "proceedings",
            "conference",
            "trans.",
            "transactions",
            "IEEE",
            "ACM",
            "ICML",
            "NeurIPS",
            "CVPR",
            "ICLR",
            "AAAI",
            "vol.",
            "volume",
            "pp.",
            "pages",
        ]
        text_lower = text.lower()
        return any(ind.lower() in text_lower for ind in venue_indicators)

    def _extract_authors(self, text: str, title: Optional[str]) -> Optional[List[str]]:
        """Extracts author names from a reference string."""
        # If we have a title, authors are usually before it
        if title and title in text:
            idx = text.find(title)
            author_part = text[:idx].strip()
        else:
            # Take first part before a period
            parts = text.split(". ", 1)
            author_part = parts[0] if parts else ""

        # Clean up numbering prefix
        author_part = re.sub(r"^\[?\d+\]?\s*\.?\s*", "", author_part)

        if not author_part or len(author_part) < 3:
            return None

        # Split by common author separators
        # Pattern: "LastName, FirstName" or "F. LastName" separated by , and or &
        author_candidates = re.split(
            r"\s*(?:,\s*(?:and\s+)?|&|\sand\s)\s*", author_part
        )

        authors = []
        for candidate in author_candidates:
            candidate = candidate.strip()
            # Filter out non-author text
            if candidate and len(candidate) > 1 and len(candidate) < 50:
                # Should contain letters
                if re.search(r"[A-Za-z]", candidate):
                    authors.append(candidate)

        return authors[:10] if authors else None  # Limit to 10 authors

    def _extract_year(self, text: str) -> Optional[int]:
        """Extracts publication year from reference text."""
        # Common patterns: (2020), 2020, in 2020
        year_patterns = [
            r"\((\d{4})\)",  # (2020)
            r"\b(19\d{2}|20[0-2]\d)\b",  # 1900-2029
        ]

        for pattern in year_patterns:
            match = re.search(pattern, text)
            if match:
                year = int(match.group(1))
                if 1900 <= year <= 2030:
                    return year

        return None

    def _classify_availability(
        self,
        doi: Optional[str],
        arxiv_id: Optional[str],
        url: Optional[str],
        title: Optional[str],
        authors: Optional[List[str]],
        year: Optional[int],
        has_online_tag: bool,
    ) -> Tuple[str, str, Optional[str]]:
        """
        Classifies the citation's source type and availability.
        Returns (source_type, availability, possibly_modified_title).

        Availability tiers (highest to lowest):
        arXiv / DOI -> downloadable
        PDF URL     -> downloadable
        URL         -> link_only
        Good title  -> searchable
        Fallback    -> unavailable
        """
        # arXiv: highest priority, always downloadable
        if arxiv_id:
            return "arxiv", "downloadable", title

        # DOI: can often resolve to PDF
        if doi:
            return "doi", "downloadable", title

        # Direct URL (especially PDF URLs)
        if url:
            if url.lower().endswith(".pdf"):
                return "url", "downloadable", title

            # URL without PDF extension
            if not title or len(title) < 15:
                domain_title = self._extract_domain_title(url)
                return "url", "link_only", domain_title

            return "url", "link_only", title

        # Has a usable title: mark as searchable regardless of author metadata
        if title and len(title) > 20:
            return "text", "searchable", title

        # Nothing useful
        return "text", "unavailable", title

    def _extract_domain_title(self, url: str) -> str:
        """Extract a readable domain name from URL to use as title."""
        try:
            # Remove protocol
            domain = re.sub(r"^https?://", "", url)
            # Get just the domain part
            domain = domain.split("/")[0]
            # Remove www.
            domain = re.sub(r"^www\.", "", domain)
            return domain
        except Exception:
            return url
