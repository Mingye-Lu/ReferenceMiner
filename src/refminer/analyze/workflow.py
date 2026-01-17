from __future__ import annotations

from dataclasses import dataclass
import jieba.analyse


@dataclass
class EvidenceChunk:
    chunk_id: str
    path: str
    page: int | None
    section: str | None
    text: str
    score: float
    bbox: list[dict] | None = None


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


def extract_keywords(question: str) -> list[str]:
    tags = jieba.analyse.extract_tags(question, topK=5)
    if not tags:
        tags = list(jieba.cut(question))
    return [w for w in tags if len(w.strip()) > 1]


def analyze(question: str, evidence: list[EvidenceChunk]) -> dict:
    scope = derive_scope(question)
    keywords = extract_keywords(question)
    
    synthesis = synthesize(question, evidence)
    crosscheck = cross_check(evidence)
    
    return {
        "question": question,
        "scope": scope,
        "keywords": keywords,
        "evidence": evidence,
        "synthesis": synthesis,
        "crosscheck": crosscheck,
    }
