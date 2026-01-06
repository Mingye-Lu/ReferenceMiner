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


def chunk_text(
    path: str,
    texts: Iterable[str],
    page_map: Iterable[int | None],
    section_map: Iterable[str | None],
    max_chars: int = 1200,
    overlap: int = 150,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    buffer: list[str] = []
    buffer_pages: list[int | None] = []
    buffer_sections: list[str | None] = []

    def flush() -> None:
        if not buffer:
            return
        text = "\n".join(buffer).strip()
        if not text:
            buffer.clear()
            buffer_pages.clear()
            buffer_sections.clear()
            return
        page = next((p for p in buffer_pages if p is not None), None)
        section = next((s for s in buffer_sections if s), None)
        chunk_id = f"{path}:{len(chunks) + 1}"
        chunks.append(Chunk(chunk_id=chunk_id, path=path, text=text, page=page, section=section))
        buffer.clear()
        buffer_pages.clear()
        buffer_sections.clear()

    for text, page, section in zip(texts, page_map, section_map):
        if len("\n".join(buffer)) + len(text) > max_chars:
            flush()
        buffer.append(text)
        buffer_pages.append(page)
        buffer_sections.append(section)
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
            overlapped.append(
                Chunk(
                    chunk_id=chunk.chunk_id,
                    path=chunk.path,
                    text=combined,
                    page=chunk.page,
                    section=chunk.section,
                )
            )
        return overlapped

    return chunks
