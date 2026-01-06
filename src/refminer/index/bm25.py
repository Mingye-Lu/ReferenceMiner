from __future__ import annotations

import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from rank_bm25 import BM25Okapi


@dataclass
class BM25Index:
    bm25: BM25Okapi
    chunk_ids: list[str]


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in text.split() if token]


def build_bm25(chunks: Iterable[tuple[str, str]]) -> BM25Index:
    texts = []
    chunk_ids = []
    for chunk_id, text in chunks:
        texts.append(tokenize(text))
        chunk_ids.append(chunk_id)
    bm25 = BM25Okapi(texts)
    return BM25Index(bm25=bm25, chunk_ids=chunk_ids)


def save_bm25(index: BM25Index, path: Path) -> None:
    with path.open("wb") as handle:
        pickle.dump(index, handle)


def load_bm25(path: Path) -> BM25Index:
    with path.open("rb") as handle:
        return pickle.load(handle)


def search(index: BM25Index, query: str, k: int = 5) -> list[tuple[str, float]]:
    tokens = tokenize(query)
    scores = index.bm25.get_scores(tokens)
    ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)[:k]
    return [(index.chunk_ids[i], float(score)) for i, score in ranked]
