from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from refminer.ingest.extract import extract_document
from refminer.ingest.manifest import ManifestEntry, detect_type, load_manifest, write_manifest
from refminer.ingest.registry import (
    HashRegistry,
    load_registry,
    register_file,
    save_registry,
    unregister_file,
)
from refminer.index.bm25 import BM25Index, build_bm25, save_bm25
from refminer.index.chunk import Chunk, chunk_text
from refminer.utils.hashing import sha256_file
from refminer.utils.paths import get_index_dir, get_references_dir


def ingest_single_file(
    file_path: Path,
    root: Path | None = None,
    build_vectors: bool = True,
) -> tuple[ManifestEntry, list[Chunk]]:
    """Process a single file: extract text, chunk, and return manifest entry + chunks."""
    references_dir = get_references_dir(root)
    rel_path = str(file_path.relative_to(references_dir))
    file_type = detect_type(file_path)

    if not file_type:
        raise ValueError(f"Unsupported file type: {file_path.suffix}")

    stat = file_path.stat()
    sha256 = sha256_file(file_path)

    entry = ManifestEntry(
        path=str(file_path),
        rel_path=rel_path,
        file_type=file_type,
        size_bytes=stat.st_size,
        modified_time=stat.st_mtime,
        sha256=sha256,
    )

    extracted = extract_document(file_path, file_type)
    entry.abstract = extracted.abstract
    entry.page_count = extracted.page_count
    entry.title = extracted.title

    chunks: list[Chunk] = []
    if extracted.text_blocks:
        chunks = chunk_text(
            path=rel_path,
            texts=extracted.text_blocks,
            page_map=extracted.page_map,
            section_map=extracted.section_map,
        )

    return entry, chunks


def append_to_manifest(entry: ManifestEntry, root: Path | None = None) -> None:
    """Add a manifest entry to the existing manifest."""
    index_dir = get_index_dir(root)
    manifest_path = index_dir / "manifest.json"

    if manifest_path.exists():
        manifest = load_manifest(root)
        # Remove any existing entry with same rel_path (for updates)
        manifest = [e for e in manifest if e.rel_path != entry.rel_path]
    else:
        manifest = []

    manifest.append(entry)
    write_manifest(manifest, root)


def remove_from_manifest(rel_path: str, root: Path | None = None) -> bool:
    """Remove a manifest entry by rel_path. Returns True if found and removed."""
    index_dir = get_index_dir(root)
    manifest_path = index_dir / "manifest.json"

    if not manifest_path.exists():
        return False

    manifest = load_manifest(root)
    original_len = len(manifest)
    manifest = [e for e in manifest if e.rel_path != rel_path]

    if len(manifest) < original_len:
        write_manifest(manifest, root)
        return True
    return False


def append_chunks(chunks: list[Chunk], root: Path | None = None) -> None:
    """Append chunks to chunks.jsonl."""
    index_dir = get_index_dir(root)
    index_dir.mkdir(parents=True, exist_ok=True)
    chunks_path = index_dir / "chunks.jsonl"

    with chunks_path.open("a", encoding="utf-8") as handle:
        for chunk in chunks:
            handle.write(json.dumps(asdict(chunk), ensure_ascii=True) + "\n")


def load_all_chunks(root: Path | None = None) -> list[tuple[str, str]]:
    """Load all chunks from chunks.jsonl as (chunk_id, text) tuples."""
    index_dir = get_index_dir(root)
    chunks_path = index_dir / "chunks.jsonl"

    if not chunks_path.exists():
        return []

    chunks = []
    with chunks_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            item = json.loads(line)
            chunks.append((item["chunk_id"], item["text"]))
    return chunks


def rebuild_bm25_from_chunks(root: Path | None = None) -> Optional[BM25Index]:
    """Rebuild BM25 index from existing chunks.jsonl."""
    chunks = load_all_chunks(root)
    if not chunks:
        return None

    bm25_index = build_bm25(chunks)
    save_bm25(bm25_index, get_index_dir(root) / "bm25.pkl")
    return bm25_index


def add_vectors_incremental(
    new_chunks: list[tuple[str, str]],
    root: Path | None = None,
) -> bool:
    """Add new vectors to existing FAISS index incrementally."""
    if not new_chunks:
        return False

    try:
        from refminer.index.vectors import _load_dependencies, load_vectors, save_vectors, VectorIndex
    except RuntimeError:
        return False

    index_dir = get_index_dir(root)
    vectors_path = index_dir / "vectors.faiss"

    try:
        faiss, SentenceTransformer = _load_dependencies()
    except RuntimeError:
        return False

    if not vectors_path.exists():
        # No existing index - build from scratch with just new chunks
        from refminer.index.vectors import build_vectors
        try:
            vector_index = build_vectors(new_chunks)
            save_vectors(vector_index, vectors_path)
            return True
        except RuntimeError:
            return False

    # Load existing index
    vector_index = load_vectors(vectors_path)

    # Encode new chunks
    model = SentenceTransformer(vector_index.model_name)
    texts = [text for _, text in new_chunks]
    new_embeddings = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
    new_embeddings = new_embeddings.astype("float32")

    # Add to FAISS index
    vector_index.faiss_index.add(new_embeddings)

    # Update metadata with new chunk IDs
    new_ids = [cid for cid, _ in new_chunks]
    all_ids = vector_index.chunk_ids + new_ids

    # Save updated index
    faiss.write_index(vector_index.faiss_index, str(vectors_path))
    import numpy as np
    meta_path = vectors_path.with_suffix(".meta.npz")
    np.savez(meta_path, chunk_ids=all_ids, model_name=vector_index.model_name)

    return True


def remove_file_from_index(rel_path: str, root: Path | None = None) -> int:
    """Remove all chunks for a file and rebuild indexes. Returns chunk count removed."""
    index_dir = get_index_dir(root)
    chunks_path = index_dir / "chunks.jsonl"

    # 1. Remove from manifest
    remove_from_manifest(rel_path, root)

    # 2. Filter chunks.jsonl
    removed = 0
    remaining_chunks: list[tuple[str, str]] = []

    if chunks_path.exists():
        temp_path = index_dir / "chunks.jsonl.tmp"
        with chunks_path.open("r", encoding="utf-8") as src, temp_path.open("w", encoding="utf-8") as dst:
            for line in src:
                item = json.loads(line)
                if item["path"] == rel_path:
                    removed += 1
                else:
                    dst.write(line)
                    remaining_chunks.append((item["chunk_id"], item["text"]))
        temp_path.replace(chunks_path)

    # 3. Rebuild BM25 (required - no incremental delete support)
    if remaining_chunks:
        bm25_index = build_bm25(remaining_chunks)
        save_bm25(bm25_index, index_dir / "bm25.pkl")
    else:
        # Remove empty index
        bm25_path = index_dir / "bm25.pkl"
        if bm25_path.exists():
            bm25_path.unlink()

    # 4. Rebuild FAISS (simpler than selective removal)
    vectors_path = index_dir / "vectors.faiss"
    if vectors_path.exists():
        if remaining_chunks:
            try:
                from refminer.index.vectors import build_vectors, save_vectors
                vector_index = build_vectors(remaining_chunks)
                save_vectors(vector_index, vectors_path)
            except RuntimeError:
                pass
        else:
            vectors_path.unlink()
            meta_path = vectors_path.with_suffix(".meta.npz")
            if meta_path.exists():
                meta_path.unlink()

    # 5. Update hash registry
    registry = load_registry(root)
    unregister_file(rel_path, registry)
    save_registry(registry, root)

    return removed


def full_ingest_single_file(
    file_path: Path,
    root: Path | None = None,
    build_vectors: bool = True,
) -> ManifestEntry:
    """Complete single-file ingest: process, update all indexes, update registry."""
    # 1. Process the file
    entry, chunks = ingest_single_file(file_path, root)

    # 2. Update manifest
    append_to_manifest(entry, root)

    # 3. Append chunks
    if chunks:
        append_chunks(chunks, root)

    # 4. Rebuild BM25 (required - no incremental support)
    rebuild_bm25_from_chunks(root)

    # 5. Add vectors incrementally
    if build_vectors and chunks:
        chunk_data = [(c.chunk_id, c.text) for c in chunks]
        add_vectors_incremental(chunk_data, root)

    # 6. Update registry
    registry = load_registry(root)
    register_file(entry.rel_path, entry.sha256, registry)
    save_registry(registry, root)

    return entry
