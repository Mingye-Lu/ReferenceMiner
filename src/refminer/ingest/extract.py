from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import fitz

from refminer.ingest.extract_docx import DocxBlock, extract_docx_text
from refminer.ingest.extract_image import ImageMetadata, extract_image_metadata
from refminer.ingest.extract_pdf import PdfTextBlock, extract_pdf_text
from refminer.utils.text import detect_abstract


@dataclass
class ExtractedDocument:
    path: Path
    file_type: str
    text_blocks: list[str]
    page_map: list[int | None]
    section_map: list[str | None]
    abstract: str | None
    page_count: int | None
    image_metadata: ImageMetadata | None
    title: str | None
    bbox_map: list[list[dict] | None] | None = None


def _pdf_title(path: Path) -> str | None:
    doc = fitz.open(path)
    title = None
    if doc.metadata:
        title = doc.metadata.get("title") or None
    doc.close()
    if title:
        return title.strip() or None
    return None


def extract_document(path: Path, file_type: str) -> ExtractedDocument:
    if file_type == "pdf":
        blocks, page_count = extract_pdf_text(path)
        text_blocks = [block.text for block in blocks]
        page_map = [block.page for block in blocks]
        section_map: list[str | None] = []
        current_section: str | None = None
        for block in blocks:
            if block.section:
                current_section = block.section
            section_map.append(current_section)
        # Extract bbox data, converting BoundingBox objects to dicts
        bbox_map = [
            [asdict(bbox) for bbox in block.bbox] if block.bbox else None
            for block in blocks
        ]
        abstract = detect_abstract("\n".join(text_blocks).split("\n"))
        title = _pdf_title(path) or (
            text_blocks[0].split("\n")[0] if text_blocks else None
        )
        return ExtractedDocument(
            path=path,
            file_type=file_type,
            text_blocks=text_blocks,
            page_map=page_map,
            section_map=section_map,
            abstract=abstract,
            page_count=page_count,
            image_metadata=None,
            title=title,
            bbox_map=bbox_map,
        )
    if file_type == "docx":
        blocks = extract_docx_text(path)
        text_blocks = [block.text for block in blocks]
        page_map = [None for _ in blocks]
        section_map = [block.section for block in blocks]
        abstract = detect_abstract("\n".join(text_blocks).split("\n"))
        title = blocks[0].text if blocks else None
        return ExtractedDocument(
            path=path,
            file_type=file_type,
            text_blocks=text_blocks,
            page_map=page_map,
            section_map=section_map,
            abstract=abstract,
            page_count=None,
            image_metadata=None,
            title=title,
        )
    if file_type == "image":
        metadata = extract_image_metadata(path)
        return ExtractedDocument(
            path=path,
            file_type=file_type,
            text_blocks=[],
            page_map=[],
            section_map=[],
            abstract=None,
            page_count=None,
            image_metadata=metadata,
            title=path.stem,
        )
    return ExtractedDocument(
        path=path,
        file_type=file_type,
        text_blocks=[],
        page_map=[],
        section_map=[],
        abstract=None,
        page_count=None,
        image_metadata=None,
        title=path.stem,
    )


def summarize_abstract(text_blocks: Iterable[str]) -> str | None:
    return detect_abstract("\n".join(text_blocks).split("\n"))
