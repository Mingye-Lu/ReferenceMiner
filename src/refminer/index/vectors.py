from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np


@dataclass
class VectorIndex:
    embeddings: np.ndarray
    chunk_ids: list[str]
    model_name: str
    faiss_index: object


def _load_dependencies():
    try:
        import faiss  # type: ignore
        from sentence_transformers import SentenceTransformer  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "Vector search requires 'faiss-cpu' and 'sentence-transformers'."
        ) from exc
    return faiss, SentenceTransformer


def build_vectors(
    chunks: Iterable[tuple[str, str]],
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
) -> VectorIndex:
    faiss, SentenceTransformer = _load_dependencies()
    model = SentenceTransformer(model_name)
    chunk_ids: list[str] = []
    texts: list[str] = []
    for chunk_id, text in chunks:
        chunk_ids.append(chunk_id)
        texts.append(text)
    embeddings = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
    embeddings = np.asarray(embeddings, dtype="float32")
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    return VectorIndex(
        embeddings=embeddings,
        chunk_ids=chunk_ids,
        model_name=model_name,
        faiss_index=index,
    )


def save_vectors(index: VectorIndex, path: Path) -> None:
    faiss, _ = _load_dependencies()
    faiss.write_index(index.faiss_index, str(path))
    meta_path = path.with_suffix(".meta.npz")
    np.savez(meta_path, chunk_ids=index.chunk_ids, model_name=index.model_name)


def load_vectors(path: Path) -> VectorIndex:
    faiss, _ = _load_dependencies()
    index = faiss.read_index(str(path))
    meta = np.load(path.with_suffix(".meta.npz"), allow_pickle=True)
    chunk_ids = list(meta["chunk_ids"])
    model_name = str(meta["model_name"])
    return VectorIndex(
        embeddings=np.empty((0, 0)),
        chunk_ids=chunk_ids,
        model_name=model_name,
        faiss_index=index,
    )


def search(index: VectorIndex, query: str, k: int = 5) -> list[tuple[str, float]]:
    _, SentenceTransformer = _load_dependencies()
    model = SentenceTransformer(index.model_name)
    embedding = model.encode([query], normalize_embeddings=True)
    scores, neighbors = index.faiss_index.search(embedding.astype("float32"), k)
    results: list[tuple[str, float]] = []
    for score, idx in zip(scores[0], neighbors[0]):
        if idx < 0:
            continue
        results.append((index.chunk_ids[idx], float(score)))
    return results
