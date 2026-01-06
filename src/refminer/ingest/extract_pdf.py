from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF

from refminer.utils.text import normalize_text


@dataclass
class PdfTextBlock:
    text: str
    page: int


def extract_pdf_text(path: Path) -> tuple[list[PdfTextBlock], int]:
    doc = fitz.open(path)
    blocks: list[PdfTextBlock] = []
    for page_index in range(doc.page_count):
        page = doc.load_page(page_index)
        text = normalize_text(page.get_text("text"))
        if text:
            blocks.append(PdfTextBlock(text=text, page=page_index + 1))
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
