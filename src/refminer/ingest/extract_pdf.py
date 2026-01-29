from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF
import re

from refminer.utils.text import normalize_text_with_mapping


@dataclass
class BoundingBox:
    """Bounding box for a span of text within a PDF page."""

    page: int  # 1-indexed page number
    x0: float  # Left coordinate
    y0: float  # Top coordinate
    x1: float  # Right coordinate
    y1: float  # Bottom coordinate
    char_start: int  # Character offset in chunk text (inclusive)
    char_end: int  # Character offset in chunk text (exclusive)


@dataclass
class PdfTextBlock:
    text: str
    page: int
    bbox: list[BoundingBox] | None = None
    section: str | None = None


def extract_pdf_text(path: Path) -> tuple[list[PdfTextBlock], int]:
    """
    Extract text from PDF with bounding box information for each text span.

    Uses PyMuPDF's dict mode to extract detailed text structure including coordinates.
    Normalizes text and maps bounding boxes to normalized character positions.
    """

    def _median(values: list[float]) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        mid = len(ordered) // 2
        if len(ordered) % 2 == 0:
            return (ordered[mid - 1] + ordered[mid]) / 2.0
        return ordered[mid]

    def _map_span(
        raw_start: int, raw_end: int, char_map: dict[int, int], text_len: int
    ) -> tuple[int, int] | None:
        norm_start = char_map.get(raw_start)
        if norm_start is None:
            for pos in range(raw_start, -1, -1):
                if pos in char_map:
                    norm_start = char_map[pos]
                    break
            if norm_start is None:
                norm_start = 0

        norm_end = char_map.get(raw_end - 1)
        if norm_end is None:
            for pos in range(raw_end - 1, -1, -1):
                if pos in char_map:
                    norm_end = char_map[pos] + 1
                    break
            if norm_end is None:
                norm_end = text_len
        else:
            norm_end += 1

        if norm_start >= norm_end or norm_start >= text_len:
            return None

        norm_start = max(0, min(norm_start, text_len))
        norm_end = max(norm_start, min(norm_end, text_len))
        return norm_start, norm_end

    def _kmeans_1d(
        values: list[float], iterations: int = 6
    ) -> tuple[float, float] | None:
        if len(values) < 6:
            return None
        sorted_vals = sorted(values)
        c1 = sorted_vals[len(sorted_vals) // 4]
        c2 = sorted_vals[(3 * len(sorted_vals)) // 4]
        if c1 == c2:
            return None
        for _ in range(iterations):
            group1 = []
            group2 = []
            for val in sorted_vals:
                if abs(val - c1) <= abs(val - c2):
                    group1.append(val)
                else:
                    group2.append(val)
            if not group1 or not group2:
                return None
            c1 = sum(group1) / len(group1)
            c2 = sum(group2) / len(group2)
        return (min(c1, c2), max(c1, c2))

    heading_number_re = re.compile(r"^\s*(\d+(?:\.\d+)*)(?:\.)?\s+\S+")
    heading_markdown_re = re.compile(r"^\s*(#{1,6})\s+\S+")

    def _detect_heading_text(
        para_lines: list[dict],
        normalized_text: str,
        median_font_size: float,
    ) -> str | None:
        if not normalized_text:
            return None
        merged = " ".join(
            line.strip() for line in normalized_text.splitlines() if line.strip()
        )
        if not merged:
            return None
        if len(merged) > 140:
            return None
        if len(para_lines) > 3:
            return None

        font_sizes = [line.get("font_size") or 0.0 for line in para_lines]
        max_size = max(font_sizes) if font_sizes else 0.0
        size_boost = median_font_size and max_size >= (median_font_size * 1.15)

        if heading_markdown_re.match(merged):
            return heading_markdown_re.sub("", merged).strip()
        if heading_number_re.match(merged):
            return merged
        if merged.isupper() and len(merged) <= 80:
            return merged

        words = re.findall(r"[A-Za-z][A-Za-z-]*", merged)
        if words:
            caps = sum(1 for w in words if w[0].isupper())
            title_case = (caps / len(words)) >= 0.6
        else:
            title_case = False

        if size_boost and title_case and not merged.endswith("."):
            return merged
        return None

    doc = fitz.open(path)
    blocks: list[PdfTextBlock] = []
    pages: list[dict] = []

    for page_index in range(doc.page_count):
        page = doc.load_page(page_index)
        page_num = page_index + 1
        text_dict = page.get_text("dict")
        page_rect = page.rect
        page_height = float(page_rect.height) if page_rect.height else 1.0
        page_width = float(page_rect.width) if page_rect.width else 1.0

        lines: list[dict] = []
        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                spans = [s for s in line.get("spans", []) if s.get("text")]
                if not spans:
                    continue

                line_text_parts: list[str] = []
                line_spans: list[dict] = []
                line_len = 0
                sizes: list[float] = []
                for idx, span in enumerate(spans):
                    span_text = span.get("text", "")
                    if not span_text:
                        continue
                    span_start = line_len
                    line_text_parts.append(span_text)
                    line_len += len(span_text)
                    span_end = line_len
                    bbox = span.get("bbox")
                    if bbox:
                        line_spans.append(
                            {
                                "bbox": tuple(bbox),
                                "char_start": span_start,
                                "char_end": span_end,
                                "size": (
                                    float(span.get("size"))
                                    if isinstance(span.get("size"), (int, float))
                                    else 0.0
                                ),
                            }
                        )
                    size = span.get("size")
                    if isinstance(size, (int, float)):
                        sizes.append(float(size))
                    if idx < len(spans) - 1:
                        line_text_parts.append(" ")
                        line_len += 1

                line_text = "".join(line_text_parts).strip()
                if not line_text:
                    continue
                bbox = line.get("bbox")
                if not bbox:
                    continue

                median_size = _median(sizes) if sizes else 0.0
                size_cutoff = median_size * 0.7 if median_size else 0.0
                anchor_spans = [s for s in line_spans if s["size"] >= size_cutoff]
                anchor_x = min(
                    (s["bbox"][0] for s in anchor_spans), default=float(bbox[0])
                )

                lines.append(
                    {
                        "text": line_text,
                        "bbox": tuple(bbox),
                        "x0": float(bbox[0]),
                        "y0": float(bbox[1]),
                        "x1": float(bbox[2]),
                        "y1": float(bbox[3]),
                        "anchor_x": float(anchor_x),
                        "spans": line_spans,
                        "font_size": median_size,
                    }
                )

        pages.append(
            {
                "page_num": page_num,
                "height": page_height,
                "width": page_width,
                "lines": lines,
            }
        )

    page_count = doc.page_count
    doc.close()

    if not pages:
        return blocks, page_count

    def _normalize_header_text(text: str) -> str:
        cleaned = text.lower().strip()
        cleaned = re.sub(r"\d+", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned

    band_size = 20
    header_counts: dict[tuple[int, str], int] = {}
    footer_counts: dict[tuple[int, str], int] = {}
    for page in pages:
        height = page["height"]
        header_keys: set[tuple[int, str]] = set()
        footer_keys: set[tuple[int, str]] = set()
        for line in page["lines"]:
            y0_norm = line["y0"] / height
            y1_norm = line["y1"] / height
            band = int(y0_norm * band_size)
            text_key = _normalize_header_text(line["text"])
            if not text_key:
                continue
            if y0_norm < 0.08:
                header_keys.add((band, text_key))
            if y1_norm > 0.92:
                footer_keys.add((band, text_key))
        for key in header_keys:
            header_counts[key] = header_counts.get(key, 0) + 1
        for key in footer_keys:
            footer_counts[key] = footer_counts.get(key, 0) + 1

    page_threshold = max(3, int(len(pages) * 0.6))
    header_keys = {
        key for key, count in header_counts.items() if count >= page_threshold
    }
    footer_keys = {
        key for key, count in footer_counts.items() if count >= page_threshold
    }

    for page in pages:
        height = page["height"]
        width = page["width"]
        filtered_lines: list[dict] = []
        for line in page["lines"]:
            y0_norm = line["y0"] / height
            y1_norm = line["y1"] / height
            band = int(y0_norm * band_size)
            text_key = _normalize_header_text(line["text"])
            if y0_norm < 0.08 and (band, text_key) in header_keys:
                continue
            if y1_norm > 0.92 and (band, text_key) in footer_keys:
                continue
            if line["font_size"] and line["font_size"] < 6.0:
                continue
            filtered_lines.append(line)

        if not filtered_lines:
            continue

        line_heights = [
            line["y1"] - line["y0"]
            for line in filtered_lines
            if line["y1"] > line["y0"]
        ]
        median_line_height = _median(line_heights)
        median_font_size = _median(
            [line["font_size"] for line in filtered_lines if line["font_size"] > 0]
        )
        height_cutoff = median_line_height * 0.7 if median_line_height else 0.0
        font_cutoff = median_font_size * 0.7 if median_font_size else 0.0

        full_width_lines: list[dict] = []
        column_candidates: list[dict] = []
        for line in filtered_lines:
            line_width = line["x1"] - line["x0"]
            if line_width >= (0.85 * width):
                full_width_lines.append(line)
            else:
                line_height = line["y1"] - line["y0"]
                if (height_cutoff and line_height < height_cutoff) or (
                    font_cutoff and line["font_size"] < font_cutoff
                ):
                    continue
                column_candidates.append(line)

        x0s = sorted(line["anchor_x"] for line in column_candidates)
        x_mids = sorted(line["anchor_x"] for line in column_candidates)
        split_x = None
        if len(x0s) >= 10:
            gaps = []
            for idx in range(1, len(x0s)):
                gaps.append((x0s[idx] - x0s[idx - 1], idx))
            max_gap, max_gap_idx = max(gaps, key=lambda item: item[0])
            if max_gap > (0.18 * width):
                split_x = (x0s[max_gap_idx - 1] + x0s[max_gap_idx]) / 2.0
        if split_x is None:
            centers = _kmeans_1d(x0s)
            if centers:
                c1, c2 = centers
                if (c2 - c1) > (0.22 * width):
                    split_x = (c1 + c2) / 2.0
        if split_x is None and len(x_mids) >= 10:
            gaps = []
            for idx in range(1, len(x_mids)):
                gaps.append((x_mids[idx] - x_mids[idx - 1], idx))
            max_gap, max_gap_idx = max(gaps, key=lambda item: item[0])
            if max_gap > (0.22 * width):
                split_x = (x_mids[max_gap_idx - 1] + x_mids[max_gap_idx]) / 2.0

        columns: list[list[dict]] = []
        if split_x is None or not column_candidates:
            columns.append(sorted(filtered_lines, key=lambda l: l["y0"]))
        else:
            left = [line for line in column_candidates if line["anchor_x"] <= split_x]
            right = [line for line in column_candidates if line["anchor_x"] > split_x]
            if len(left) < 3 or len(right) < 3:
                columns.append(sorted(filtered_lines, key=lambda l: l["y0"]))
            else:
                if full_width_lines:
                    columns.append(sorted(full_width_lines, key=lambda l: l["y0"]))
                columns.append(sorted(left, key=lambda l: l["y0"]))
                columns.append(sorted(right, key=lambda l: l["y0"]))

        for column_lines in columns:
            heights = [line["y1"] - line["y0"] for line in column_lines]
            gaps = []
            for idx in range(1, len(column_lines)):
                gap = column_lines[idx]["y0"] - column_lines[idx - 1]["y1"]
                if gap > 0:
                    gaps.append(gap)
            median_height = _median(heights)
            median_gap = _median(gaps) if gaps else median_height
            gap_threshold = max(median_gap * 1.5, median_height * 1.2)
            indent_threshold = width * 0.05

            paragraphs: list[list[dict]] = []
            current: list[dict] = []
            for idx, line in enumerate(column_lines):
                if not current:
                    current.append(line)
                    continue
                prev = current[-1]
                gap = line["y0"] - prev["y1"]
                indent_change = abs(line["x0"] - prev["x0"]) > indent_threshold
                prev_text = prev["text"].rstrip()
                prev_end = prev_text[-1:] if prev_text else ""
                starts_new = (
                    line["text"].lstrip()[:1].isupper() if line["text"] else False
                )
                paragraph_break = False
                if gap > gap_threshold:
                    paragraph_break = True
                elif indent_change and gap > (median_gap * 0.5):
                    paragraph_break = True
                elif (
                    prev_end in (".", "!", "?", ":")
                    and gap > (median_gap * 1.1)
                    and starts_new
                ):
                    paragraph_break = True

                if paragraph_break:
                    paragraphs.append(current)
                    current = [line]
                else:
                    current.append(line)
            if current:
                paragraphs.append(current)

            for para_lines in paragraphs:
                raw_parts: list[str] = []
                span_entries: list[
                    tuple[int, int, tuple[float, float, float, float]]
                ] = []
                raw_len = 0
                for line in para_lines:
                    line_text = line["text"]
                    for span in line["spans"]:
                        raw_start = raw_len + span["char_start"]
                        raw_end = raw_len + span["char_end"]
                        span_entries.append((raw_start, raw_end, span["bbox"]))
                    raw_parts.append(line_text)
                    raw_len += len(line_text)
                    raw_parts.append("\n")
                    raw_len += 1

                raw_text = "".join(raw_parts)
                if not raw_text.strip():
                    continue

                normalized_text, char_map = normalize_text_with_mapping(raw_text)
                if not normalized_text:
                    continue

                section = _detect_heading_text(
                    para_lines, normalized_text, median_font_size
                )

                bbox_list: list[BoundingBox] = []
                for raw_start, raw_end, (x0, y0, x1, y1) in span_entries:
                    mapped = _map_span(
                        raw_start, raw_end, char_map, len(normalized_text)
                    )
                    if not mapped:
                        continue
                    norm_start, norm_end = mapped
                    bbox_list.append(
                        BoundingBox(
                            page=page["page_num"],
                            x0=float(x0),
                            y0=float(y0),
                            x1=float(x1),
                            y1=float(y1),
                            char_start=norm_start,
                            char_end=norm_end,
                        )
                    )

                blocks.append(
                    PdfTextBlock(
                        text=normalized_text,
                        page=page["page_num"],
                        bbox=bbox_list if bbox_list else None,
                        section=section,
                    )
                )

    return blocks, page_count


def render_page_image(path: Path, page: int, output_path: Path) -> None:
    doc = fitz.open(path)
    page_obj = doc.load_page(page - 1)
    pix = page_obj.get_pixmap()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pix.save(str(output_path))
    doc.close()
