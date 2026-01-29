from __future__ import annotations

from typing import Iterable

from refminer.analyze.workflow import EvidenceChunk


def format_citation(chunk: EvidenceChunk) -> str:
    if chunk.page:
        return f"{chunk.path} p.{chunk.page}"
    return chunk.path


def render_answer(analysis: dict) -> str:
    evidence: Iterable[EvidenceChunk] = analysis.get("evidence", [])
    citations = "\n".join(f"- {format_citation(item)}" for item in evidence)
    return "\n".join(
        [
            analysis.get("synthesis", ""),
            "",
            "Citations:",
            citations or "- None",
            "",
            f"Cross-check: {analysis.get('crosscheck', '')}",
        ]
    ).strip()
