from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass
class Chunk:
    chunk_id: str
    path: str
    text: str
    page: int | None
    section: str | None
    bbox: list[dict] | None = None


def chunk_text(
    path: str,
    texts: Iterable[str],
    page_map: Iterable[int | None],
    section_map: Iterable[str | None],
    bbox_map: Iterable[list[dict] | None] | None = None,
    max_chars: int = 1200,
    overlap: int = 150,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    buffer: list[str] = []
    buffer_pages: list[int | None] = []
    buffer_sections: list[str | None] = []
    buffer_bboxes: list[list[dict] | None] = []

    def flush() -> None:
        if not buffer:
            return
        text = "\n".join(buffer).strip()
        if not text:
            buffer.clear()
            buffer_pages.clear()
            buffer_sections.clear()
            buffer_bboxes.clear()
            return
        page = next((p for p in buffer_pages if p is not None), None)
        section = next((s for s in buffer_sections if s), None)

        # Merge bounding boxes from all buffered blocks
        merged_bbox: list[dict] = []
        char_offset = 0
        for i, block_text in enumerate(buffer):
            block_bboxes = buffer_bboxes[i] if i < len(buffer_bboxes) else None
            if block_bboxes:
                # Adjust character offsets for this block
                for bbox in block_bboxes:
                    adjusted_bbox = bbox.copy()
                    adjusted_bbox["char_start"] = bbox["char_start"] + char_offset
                    adjusted_bbox["char_end"] = bbox["char_end"] + char_offset
                    merged_bbox.append(adjusted_bbox)
            # Account for newline between blocks
            char_offset += len(block_text) + (1 if i < len(buffer) - 1 else 0)

        chunk_id = f"{path}:{len(chunks) + 1}"
        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                path=path,
                text=text,
                page=page,
                section=section,
                bbox=merged_bbox if merged_bbox else None,
            )
        )
        buffer.clear()
        buffer_pages.clear()
        buffer_sections.clear()
        buffer_bboxes.clear()

    # Convert bbox_map to list if provided, otherwise use empty list
    bbox_list = list(bbox_map) if bbox_map is not None else []

    for i, (text, page, section) in enumerate(zip(texts, page_map, section_map)):
        if len("\n".join(buffer)) + len(text) > max_chars:
            flush()
        buffer.append(text)
        buffer_pages.append(page)
        buffer_sections.append(section)
        # Get bbox for this text block, or None if not available
        bbox = bbox_list[i] if i < len(bbox_list) else None
        buffer_bboxes.append(bbox)
        if len("\n".join(buffer)) >= max_chars:
            flush()
    flush()

    if overlap > 0 and chunks:
        overlapped: list[Chunk] = []
        for index, chunk in enumerate(chunks):
            if index == 0:
                overlapped.append(chunk)
                continue
            prev = chunks[index - 1]
            overlap_text = prev.text[-overlap:]
            combined = overlap_text + "\n" + chunk.text

            # Adjust bounding boxes for overlapped chunk
            overlap_bbox: list[dict] = []

            # Add bbox from previous chunk's overlap region
            if prev.bbox:
                for bbox in prev.bbox:
                    # Check if this bbox is in the overlap region
                    if bbox["char_end"] > len(prev.text) - overlap:
                        adjusted_bbox = bbox.copy()
                        # Adjust to position in overlapped chunk (starts at 0)
                        offset = len(prev.text) - overlap
                        adjusted_bbox["char_start"] = max(
                            0, bbox["char_start"] - offset
                        )
                        adjusted_bbox["char_end"] = bbox["char_end"] - offset
                        overlap_bbox.append(adjusted_bbox)

            # Add bbox from current chunk, shifted by overlap length + newline
            if chunk.bbox:
                shift = len(overlap_text) + 1  # +1 for newline
                for bbox in chunk.bbox:
                    adjusted_bbox = bbox.copy()
                    adjusted_bbox["char_start"] = bbox["char_start"] + shift
                    adjusted_bbox["char_end"] = bbox["char_end"] + shift
                    overlap_bbox.append(adjusted_bbox)

            overlapped.append(
                Chunk(
                    chunk_id=chunk.chunk_id,
                    path=chunk.path,
                    text=combined,
                    page=chunk.page,
                    section=chunk.section,
                    bbox=overlap_bbox if overlap_bbox else None,
                )
            )
        return overlapped

    return chunks
