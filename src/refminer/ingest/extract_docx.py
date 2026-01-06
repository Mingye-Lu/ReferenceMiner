from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from docx import Document

from refminer.utils.text import normalize_text


@dataclass
class DocxBlock:
    text: str
    section: str


def extract_docx_text(path: Path) -> list[DocxBlock]:
    doc = Document(path)
    blocks: list[DocxBlock] = []
    current_section = "Body"
    for paragraph in doc.paragraphs:
        text = normalize_text(paragraph.text)
        if not text:
            continue
        style = paragraph.style.name if paragraph.style else ""
        if style.lower().startswith("heading"):
            current_section = text
            continue
        blocks.append(DocxBlock(text=text, section=current_section))
    return blocks
