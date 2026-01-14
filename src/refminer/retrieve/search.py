from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from refminer.analyze.workflow import EvidenceChunk
from refminer.index.bm25 import load_bm25, search as bm25_search
from refminer.index.vectors import load_vectors, search as vector_search
from refminer.retrieve.hybrid import reciprocal_rank_fusion
from refminer.utils.paths import get_index_dir


def load_chunks(index_dir: Path) -> dict[str, dict]:
    chunks_path = index_dir / "chunks.jsonl"
    chunks: dict[str, dict] = {}
    with chunks_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            item = json.loads(line)
            chunks[item["chunk_id"]] = item
    return chunks


def retrieve(
    query: str, root: Optional[Path] = None, k: int = 5, filter_files: Optional[list[str]] = None
) -> list[EvidenceChunk]:
    index_dir = get_index_dir(root)
    chunks = load_chunks(index_dir)
    bm25_index = load_bm25(index_dir / "bm25.pkl")
    
    # Retrieve more candidates if filtering is active to ensure we have enough results
    search_k = k * 5 if filter_files else k
    bm25_hits = bm25_search(bm25_index, query, k=search_k)

    rankings = [bm25_hits]
    vector_hits: list[tuple[str, float]] = []
    vectors_path = index_dir / "vectors.faiss"
    if vectors_path.exists():
        try:
            vector_index = load_vectors(vectors_path)
            vector_hits = vector_search(vector_index, query, k=search_k)
            if vector_hits:
                rankings.append(vector_hits)
        except RuntimeError:
            pass

    fused = reciprocal_rank_fusion(rankings)
    evidence: list[EvidenceChunk] = []
    
    for chunk_id, score in fused:
        if len(evidence) >= k:
            break
            
        item = chunks.get(chunk_id)
        if not item:
            continue
            
        # Apply strict filtering
        if filter_files and item["path"] not in filter_files:
            continue
            
        evidence.append(
            EvidenceChunk(
                chunk_id=chunk_id,
                path=item["path"],
                page=item.get("page"),
                section=item.get("section"),
                text=item["text"],
                score=score,
            )
        )
    return evidence
