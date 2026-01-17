from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF

from refminer.utils.text import normalize_text, normalize_text_with_mapping


@dataclass
class BoundingBox:
    """Bounding box for a span of text within a PDF page."""
    page: int              # 1-indexed page number
    x0: float              # Left coordinate
    y0: float              # Top coordinate
    x1: float              # Right coordinate
    y1: float              # Bottom coordinate
    char_start: int        # Character offset in chunk text (inclusive)
    char_end: int          # Character offset in chunk text (exclusive)


@dataclass
class PdfTextBlock:
    text: str
    page: int
    bbox: list[BoundingBox] | None = None


def extract_pdf_text(path: Path) -> tuple[list[PdfTextBlock], int]:
    """
    Extract text from PDF with bounding box information for each text span.

    Uses PyMuPDF's dict mode to extract detailed text structure including coordinates.
    Normalizes text and maps bounding boxes to normalized character positions.
    """
    doc = fitz.open(path)
    blocks: list[PdfTextBlock] = []

    for page_index in range(doc.page_count):
        page = doc.load_page(page_index)
        page_num = page_index + 1

        # Extract text structure with detailed position info
        text_dict = page.get_text("dict")

        # Build raw text and collect span bounding boxes
        raw_text_parts: list[str] = []
        span_boxes: list[tuple[int, int, tuple[float, float, float, float]]] = []  # (start, end, bbox)

        for block in text_dict.get("blocks", []):
            # Only process text blocks (type 0), skip image blocks (type 1)
            if block.get("type") != 0:
                continue

            for line in block.get("lines", []):
                line_start = len("".join(raw_text_parts))

                for span in line.get("spans", []):
                    span_text = span.get("text", "")
                    if not span_text:
                        continue

                    span_start = len("".join(raw_text_parts))
                    raw_text_parts.append(span_text)
                    span_end = len("".join(raw_text_parts))

                    # Extract bounding box (x0, y0, x1, y1)
                    bbox = span.get("bbox")
                    if bbox:
                        span_boxes.append((span_start, span_end, tuple(bbox)))

                # Add space between spans on same line
                if line.get("spans"):
                    raw_text_parts.append(" ")

                # Add newline after each line
                raw_text_parts.append("\n")

        raw_text = "".join(raw_text_parts)

        if not raw_text.strip():
            continue

        # Normalize text and get character mapping
        normalized_text, char_map = normalize_text_with_mapping(raw_text)

        if not normalized_text:
            continue

        # Transform bounding boxes to normalized positions
        bbox_list: list[BoundingBox] = []
        for raw_start, raw_end, (x0, y0, x1, y1) in span_boxes:
            # Map raw positions to normalized positions
            # Find the closest mapped position for start
            norm_start = char_map.get(raw_start)
            if norm_start is None:
                # Find nearest mapped position
                for pos in range(raw_start, -1, -1):
                    if pos in char_map:
                        norm_start = char_map[pos]
                        break
                if norm_start is None:
                    norm_start = 0

            # Find the closest mapped position for end
            norm_end = char_map.get(raw_end - 1)  # -1 because end is exclusive
            if norm_end is None:
                # Find nearest mapped position
                for pos in range(raw_end - 1, -1, -1):
                    if pos in char_map:
                        norm_end = char_map[pos] + 1  # +1 to make it exclusive
                        break
                if norm_end is None:
                    norm_end = len(normalized_text)
            else:
                norm_end += 1  # Make it exclusive

            # Skip if positions are invalid
            if norm_start >= norm_end or norm_start >= len(normalized_text):
                continue

            # Clamp to valid range
            norm_start = max(0, min(norm_start, len(normalized_text)))
            norm_end = max(norm_start, min(norm_end, len(normalized_text)))

            bbox_list.append(
                BoundingBox(
                    page=page_num,
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
                page=page_num,
                bbox=bbox_list if bbox_list else None,
            )
        )

    page_count = doc.page_count
    doc.close()
    return blocks, page_count


def render_page_image(path: Path, page: int, output_path: Path) -> None:
    doc = fitz.open(path)
    page_obj = doc.load_page(page - 1)
    pix = page_obj.get_pixmap()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pix.save(str(output_path))
    doc.close()
