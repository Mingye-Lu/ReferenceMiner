from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from refminer.ingest.extract import extract_document
from refminer.ingest.manifest import build_manifest, write_manifest
from refminer.index.bm25 import build_bm25, save_bm25
from refminer.index.chunk import chunk_text
from refminer.index.vectors import build_vectors, save_vectors
from refminer.utils.paths import get_index_dir


def ingest_all(
    root: Path | None = None, 
    references_dir: Path | None = None,
    index_dir: Path | None = None,
    build_vectors_index: bool = True
) -> dict:
    manifest_entries = build_manifest(root, references_dir=references_dir)
    manifest_path = write_manifest(manifest_entries, root, index_dir=index_dir)
    
    idx_dir = index_dir or get_index_dir(root)
    ref_dir = references_dir or get_references_dir(root)

    if not manifest_entries:
        return {
            "manifest": str(manifest_path),
            "chunks": None,
            "bm25": None,
            "vectors": None,
        }

    chunks_payload: list[dict] = []

    for entry in manifest_entries:
        path = Path(entry.path)
        extracted = extract_document(path, entry.file_type)
        entry.abstract = extracted.abstract
        entry.page_count = extracted.page_count
        entry.title = extracted.title
        if extracted.text_blocks:
            chunks = chunk_text(
                path=entry.rel_path,
                texts=extracted.text_blocks,
                page_map=extracted.page_map,
                section_map=extracted.section_map,
            )
            for chunk in chunks:
                chunks_payload.append(asdict(chunk))

    idx_dir.mkdir(parents=True, exist_ok=True)
    
    chunks_path = idx_dir / "chunks.jsonl"
    with chunks_path.open("w", encoding="utf-8") as handle:
        for item in chunks_payload:
            handle.write(json.dumps(item, ensure_ascii=True) + "\n")

    bm25_index = build_bm25([(item["chunk_id"], item["text"]) for item in chunks_payload])
    save_bm25(bm25_index, idx_dir / "bm25.pkl")

    vectors_path = idx_dir / "vectors.faiss"
    vectors_built = False
    if build_vectors_index and chunks_payload:
        try:
            vector_index = build_vectors([(item["chunk_id"], item["text"]) for item in chunks_payload])
            save_vectors(vector_index, vectors_path)
            vectors_built = True
        except RuntimeError:
            vectors_built = False

    return {
        "manifest": str(manifest_path),
        "chunks": str(chunks_path),
        "bm25": str(idx_dir / "bm25.pkl"),
        "vectors": str(vectors_path) if vectors_built else None,
    }
