"""Reprocess streaming logic for re-indexing files."""
from __future__ import annotations

import asyncio
from dataclasses import asdict
from pathlib import Path
from typing import AsyncIterator

from refminer.ingest.incremental import full_ingest_single_file, remove_file_from_index
from refminer.ingest.manifest import build_manifest, write_manifest
from refminer.ingest.extract import extract_document
from refminer.ingest.bibliography import extract_bibliography_from_pdf, merge_bibliography
from refminer.ingest.registry import HashRegistry, register_file, save_registry
from refminer.index.bm25 import build_bm25, save_bm25
from refminer.index.chunk import chunk_text
from refminer.index.vectors import build_vectors, save_vectors
from refminer.server.globals import get_bank_paths
from refminer.server.utils import (
    sse,
    resolve_rel_path,
    clear_bank_indexes,
    write_chunks_file,
    load_manifest_entries,
    update_manifest_entry,
)


async def stream_reprocess() -> AsyncIterator[str]:
    """Stream full reprocess of the reference bank."""
    try:
        ref_dir, idx_dir = get_bank_paths()
        idx_dir.mkdir(parents=True, exist_ok=True)
        existing_entries = await asyncio.to_thread(load_manifest_entries)
        existing_map = {entry.rel_path: entry.bibliography for entry in existing_entries if entry.bibliography}

        yield sse("progress", {"phase": "resetting", "percent": 5})
        await asyncio.sleep(0)
        await asyncio.to_thread(clear_bank_indexes, idx_dir)

        yield sse("progress", {"phase": "scanning", "percent": 10})
        await asyncio.sleep(0)
        manifest_entries = await asyncio.to_thread(build_manifest, references_dir=ref_dir)
        total_files = len(manifest_entries)
        yield sse("start", {"total_files": total_files})
        await asyncio.sleep(0)

        chunks_payload: list[dict] = []
        for index, entry in enumerate(manifest_entries, start=1):
            preserved_bibliography = existing_map.get(entry.rel_path)
            if preserved_bibliography:
                entry.bibliography = preserved_bibliography
            yield sse("file", {
                "rel_path": entry.rel_path,
                "status": "processing",
                "phase": "extracting",
                "index": index,
                "total": total_files,
            })
            await asyncio.sleep(0)

            path = Path(entry.path)
            extracted = await asyncio.to_thread(extract_document, path, entry.file_type)
            entry.abstract = extracted.abstract
            entry.page_count = extracted.page_count
            entry.title = extracted.title
            if entry.file_type == "pdf":
                extracted_bib = await asyncio.to_thread(extract_bibliography_from_pdf, path, extracted.text_blocks, entry.title, path.name)
                entry.bibliography = merge_bibliography(entry.bibliography, extracted_bib)
            if extracted.text_blocks:
                chunks = await asyncio.to_thread(
                    chunk_text,
                    entry.rel_path,
                    extracted.text_blocks,
                    extracted.page_map,
                    extracted.section_map,
                    extracted.bbox_map,
                )
                for chunk in chunks:
                    chunks_payload.append(asdict(chunk))

            yield sse("file", {
                "rel_path": entry.rel_path,
                "status": "complete",
                "index": index,
                "total": total_files,
            })
            await asyncio.sleep(0)

        await asyncio.to_thread(write_manifest, manifest_entries, index_dir=idx_dir)

        yield sse("progress", {"phase": "indexing", "percent": 80})
        await asyncio.sleep(0)
        if chunks_payload:
            chunks_path = idx_dir / "chunks.jsonl"
            await asyncio.to_thread(write_chunks_file, chunks_path, chunks_payload)

            bm25_index = await asyncio.to_thread(
                build_bm25,
                [(item["chunk_id"], item["text"]) for item in chunks_payload],
            )
            await asyncio.to_thread(save_bm25, bm25_index, idx_dir / "bm25.pkl")

            vectors_path = idx_dir / "vectors.faiss"
            try:
                vector_index = await asyncio.to_thread(
                    build_vectors,
                    [(item["chunk_id"], item["text"]) for item in chunks_payload],
                )
                await asyncio.to_thread(save_vectors, vector_index, vectors_path)
            except RuntimeError:
                pass

        registry = HashRegistry()
        for entry in manifest_entries:
            register_file(entry.rel_path, entry.sha256, registry)
        await asyncio.to_thread(save_registry, registry, index_dir=idx_dir, references_dir=ref_dir)

        yield sse("complete", {
            "total_files": total_files,
            "total_chunks": len(chunks_payload),
        })
    except Exception as e:
        yield sse("error", {"code": "REPROCESS_ERROR", "message": str(e)})


async def stream_reprocess_file(rel_path: str) -> AsyncIterator[str]:
    """Stream reprocess for a single file."""
    try:
        ref_dir, idx_dir = get_bank_paths()
        resolved_path = resolve_rel_path(rel_path)
        file_path = ref_dir / resolved_path
        if not file_path.exists():
            yield sse("error", {"code": "NOT_FOUND", "message": f"File not found: {resolved_path}"})
            return
        existing_entries = await asyncio.to_thread(load_manifest_entries)
        existing_entry = next((e for e in existing_entries if e.rel_path == resolved_path), None)

        yield sse("file", {
            "rel_path": resolved_path,
            "status": "processing",
            "phase": "extracting",
        })
        await asyncio.sleep(0)

        await asyncio.to_thread(remove_file_from_index, resolved_path, index_dir=idx_dir, references_dir=ref_dir)
        entry = await asyncio.to_thread(
            full_ingest_single_file,
            file_path,
            references_dir=ref_dir,
            index_dir=idx_dir,
            build_vectors=True,
        )
        if existing_entry and existing_entry.bibliography is not None:
            await asyncio.to_thread(
                update_manifest_entry,
                resolved_path,
                lambda e: setattr(e, "bibliography", existing_entry.bibliography),
            )
            entry.bibliography = existing_entry.bibliography
        manifest_entry = {
            "rel_path": entry.rel_path,
            "file_type": entry.file_type,
            "title": entry.title,
            "abstract": entry.abstract,
            "page_count": entry.page_count,
            "size_bytes": entry.size_bytes,
            "bibliography": entry.bibliography,
        }

        yield sse("complete", {"manifest_entry": manifest_entry})
    except Exception as e:
        yield sse("error", {"code": "REPROCESS_FILE_ERROR", "message": str(e)})
