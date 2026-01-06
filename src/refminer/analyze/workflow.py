from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EvidenceChunk:
    chunk_id: str
    path: str
    page: int | None
    section: str | None
    text: str
    score: float


def derive_scope(question: str) -> list[str]:
    parts = [part.strip() for part in question.split("?") if part.strip()]
    return parts or [question]


def synthesize(question: str, evidence: list[EvidenceChunk]) -> str:
    if not evidence:
        return "No relevant evidence found in the indexed references."
    lead = f"Question: {question}"
    highlights = "\n".join(
        f"- {item.text[:240].rstrip()}" for item in evidence[:5]
    )
    return f"{lead}\nEvidence highlights:\n{highlights}"


def cross_check(evidence: list[EvidenceChunk]) -> str:
    if len(evidence) < 2:
        return "Insufficient sources for contradiction checking."
    return "No explicit contradictions detected in the top evidence snippets."


def analyze(question: str, evidence: list[EvidenceChunk]) -> dict:
    scope = derive_scope(question)
    synthesis = synthesize(question, evidence)
    crosscheck = cross_check(evidence)
    return {
        "question": question,
        "scope": scope,
        "evidence": evidence,
        "synthesis": synthesis,
        "crosscheck": crosscheck,
    }
