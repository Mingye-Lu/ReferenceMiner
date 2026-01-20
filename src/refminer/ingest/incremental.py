from __future__ import annotations

import json
import time
from contextlib import contextmanager
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


@contextmanager
def _file_lock(lock_path: Path, timeout: float = 30.0):
    """Cross-platform file lock using a lock file.

    Prevents concurrent writes to chunks.jsonl which can cause corruption.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    start = time.time()

    while True:
        try:
            # Try to create lock file exclusively
            fd = lock_path.open("x")
            fd.write(str(time.time()))
            fd.close()
            break
        except FileExistsError:
            # Lock exists - check if it's stale (older than timeout)
            try:
                mtime = lock_path.stat().st_mtime
                if time.time() - mtime > timeout:
                    # Stale lock, remove it
                    lock_path.unlink(missing_ok=True)
                    continue
            except FileNotFoundError:
                # Lock was released, try again
                continue

            if time.time() - start > timeout:
                raise TimeoutError(f"Could not acquire lock on {lock_path}")
            time.sleep(0.1)

    try:
        yield
    finally:
        lock_path.unlink(missing_ok=True)


def ingest_single_file(
    file_path: Path,
    root: Path | None = None,
    references_dir: Path | None = None,
    build_vectors: bool = True,
) -> tuple[ManifestEntry, list[Chunk]]:
    """Process a single file: extract text, chunk, and return manifest entry + chunks."""
    ref_dir = references_dir or get_references_dir(root)
    rel_path = str(file_path.relative_to(ref_dir))
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
            bbox_map=extracted.bbox_map,
        )

    return entry, chunks


def append_to_manifest(entry: ManifestEntry, root: Path | None = None, index_dir: Path | None = None) -> None:
    """Add a manifest entry to the existing manifest."""
    idx_dir = index_dir or get_index_dir(root)
    manifest_path = idx_dir / "manifest.json"
    
    if manifest_path.exists():
        manifest = load_manifest(root, index_dir=idx_dir)
        # Remove any existing entry with same rel_path (for updates)
        manifest = [e for e in manifest if e.rel_path != entry.rel_path]
    else:
        manifest = []

    manifest.append(entry)
    write_manifest(manifest, root, index_dir=idx_dir)


def remove_from_manifest(rel_path: str, root: Path | None = None, index_dir: Path | None = None) -> bool:
    """Remove a manifest entry by rel_path. Returns True if found and removed."""
    idx_dir = index_dir or get_index_dir(root)
    manifest_path = idx_dir / "manifest.json"

    if not manifest_path.exists():
        return False

    manifest = load_manifest(root, index_dir=idx_dir)
    original_len = len(manifest)
    manifest = [e for e in manifest if e.rel_path != rel_path]

    if len(manifest) < original_len:
        write_manifest(manifest, root, index_dir=idx_dir)
        return True
    return False


def append_chunks(chunks: list[Chunk], root: Path | None = None, index_dir: Path | None = None) -> None:
    """Append chunks to chunks.jsonl with file locking to prevent corruption."""
    idx_dir = index_dir or get_index_dir(root)
    idx_dir.mkdir(parents=True, exist_ok=True)
    chunks_path = idx_dir / "chunks.jsonl"
    lock_path = idx_dir / "chunks.jsonl.lock"

    # Serialize all chunks first (outside the lock) to minimize lock time
    lines = [json.dumps(asdict(chunk), ensure_ascii=True) + "\n" for chunk in chunks]
    data = "".join(lines)

    # Acquire lock and write atomically
    with _file_lock(lock_path):
        with chunks_path.open("a", encoding="utf-8") as handle:
            handle.write(data)
            handle.flush()


def load_all_chunks(root: Path | None = None, index_dir: Path | None = None) -> list[tuple[str, str]]:
    """Load all chunks from chunks.jsonl as (chunk_id, text) tuples."""
    idx_dir = index_dir or get_index_dir(root)
    chunks_path = idx_dir / "chunks.jsonl"

    if not chunks_path.exists():
        return []

    chunks = []
    with chunks_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                item = json.loads(line)
                chunks.append((item["chunk_id"], item["text"]))
            except json.JSONDecodeError:
                # Skip corrupted lines
                continue
    return chunks


def rebuild_bm25_from_chunks(root: Path | None = None, index_dir: Path | None = None) -> Optional[BM25Index]:
    """Rebuild BM25 index from existing chunks.jsonl."""
    idx_dir = index_dir or get_index_dir(root)
    chunks = load_all_chunks(root, index_dir=idx_dir)
    if not chunks:
        return None

    bm25_index = build_bm25(chunks)
    save_bm25(bm25_index, idx_dir / "bm25.pkl")
    return bm25_index


def add_vectors_incremental(
    new_chunks: list[tuple[str, str]],
    root: Path | None = None,
    index_dir: Path | None = None,
) -> bool:
    """Add new vectors to existing FAISS index incrementally."""
    if not new_chunks:
        return False

    try:
        from refminer.index.vectors import _load_dependencies, load_vectors, save_vectors, VectorIndex
    except RuntimeError:
        return False

    idx_dir = index_dir or get_index_dir(root)
    vectors_path = idx_dir / "vectors.faiss"

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


def remove_file_from_index(rel_path: str, root: Path | None = None, index_dir: Path | None = None, references_dir: Path | None = None) -> int:
    """Remove all chunks for a file and rebuild indexes. Returns chunk count removed."""
    idx_dir = index_dir or get_index_dir(root)
    chunks_path = idx_dir / "chunks.jsonl"
    lock_path = idx_dir / "chunks.jsonl.lock"

    # 1. Remove from manifest
    remove_from_manifest(rel_path, root, index_dir=idx_dir)

    # 2. Filter chunks.jsonl (with lock to prevent concurrent access)
    removed = 0
    remaining_chunks: list[tuple[str, str]] = []

    if chunks_path.exists():
        with _file_lock(lock_path):
            temp_path = idx_dir / "chunks.jsonl.tmp"
            with chunks_path.open("r", encoding="utf-8") as src, temp_path.open("w", encoding="utf-8") as dst:
                for line in src:
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        # Skip corrupted lines
                        continue
                    if item["path"] == rel_path:
                        removed += 1
                    else:
                        # Re-serialize to ensure clean output
                        dst.write(json.dumps(item, ensure_ascii=True) + "\n")
                        remaining_chunks.append((item["chunk_id"], item["text"]))
            temp_path.replace(chunks_path)

    # 3. Rebuild BM25 (required - no incremental delete support)
    if remaining_chunks:
        bm25_index = build_bm25(remaining_chunks)
        save_bm25(bm25_index, idx_dir / "bm25.pkl")
    else:
        # Remove empty index
        bm25_path = idx_dir / "bm25.pkl"
        if bm25_path.exists():
            bm25_path.unlink()

    # 4. Remove FAISS index (rebuilding is too expensive; BM25 will handle search)
    #    User can rebuild vectors later with `python referenceminer.py ingest` if needed
    vectors_path = idx_dir / "vectors.faiss"
    if vectors_path.exists():
        vectors_path.unlink()
        meta_path = vectors_path.with_suffix(".meta.npz")
        if meta_path.exists():
            meta_path.unlink()

    # 5. Update hash registry
    registry = load_registry(root, index_dir=idx_dir, references_dir=references_dir)
    unregister_file(rel_path, registry)
    save_registry(registry, root, index_dir=idx_dir, references_dir=references_dir)

    return removed


def full_ingest_single_file(
    file_path: Path,
    root: Path | None = None,
    references_dir: Path | None = None,
    index_dir: Path | None = None,
    build_vectors: bool = True,
) -> ManifestEntry:
    """Complete single-file ingest: process, update all indexes, update registry."""
    # 1. Process the file
    entry, chunks = ingest_single_file(file_path, root, references_dir=references_dir)

    # 2. Update manifest
    append_to_manifest(entry, root, index_dir=index_dir)

    # 3. Append chunks
    if chunks:
        append_chunks(chunks, root, index_dir=index_dir)

    # 4. Rebuild BM25 (required - no incremental support)
    rebuild_bm25_from_chunks(root, index_dir=index_dir)

    # 5. Add vectors incrementally
    if build_vectors and chunks:
        chunk_data = [(c.chunk_id, c.text) for c in chunks]
        add_vectors_incremental(chunk_data, root, index_dir=index_dir)

    # 6. Update registry
    registry = load_registry(root, index_dir=index_dir, references_dir=references_dir)
    register_file(entry.rel_path, entry.sha256, registry)
    save_registry(registry, root, index_dir=index_dir, references_dir=references_dir)

    return entry
