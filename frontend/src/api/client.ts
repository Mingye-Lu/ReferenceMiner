import type { AnswerBlock, AskResponse, EvidenceChunk, ManifestEntry, IndexStatus } from "../types"

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000"

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init)
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`API ${response.status}: ${detail || "Request failed"}`)
  }
  return response.json() as Promise<T>
}

function mapManifestEntry(item: any): ManifestEntry {
  return {
    relPath: item.rel_path ?? item.relPath ?? item.path ?? "",
    fileType: item.file_type ?? item.fileType ?? "text",
    title: item.title ?? null,
    abstract: item.abstract ?? null,
    pageCount: item.page_count ?? item.pageCount ?? null,
    sizeBytes: item.size_bytes ?? item.sizeBytes,
  }
}

function mapEvidence(item: any): EvidenceChunk {
  return {
    chunkId: item.chunk_id ?? item.chunkId ?? "",
    path: item.path ?? item.rel_path ?? "",
    page: item.page ?? item.page_number ?? null,
    section: item.section ?? null,
    text: item.text ?? "",
    score: item.score ?? 0,
  }
}

function mapAnswerBlock(item: any): AnswerBlock {
  return {
    heading: item.heading ?? "Answer",
    body: item.body ?? item.text ?? "",
    citations: item.citations ?? [],
  }
}

export async function fetchManifest(): Promise<ManifestEntry[]> {
  const data = await fetchJson<any[]>("/manifest")
  return data.map(mapManifestEntry)
}

export async function fetchIndexStatus(): Promise<IndexStatus> {
  const data = await fetchJson<any>("/status")
  return {
    indexed: data.indexed ?? false,
    lastIngest: data.last_ingest ?? data.lastIngest ?? null,
    totalFiles: data.total_files ?? data.totalFiles ?? 0,
    totalChunks: data.total_chunks ?? data.totalChunks ?? 0,
  }
}

export async function askQuestion(question: string): Promise<AskResponse> {
  const data = await fetchJson<any>("/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  })
  return {
    question: data.question ?? question,
    scope: data.scope ?? [],
    keywords: data.keywords ?? [],
    evidence: (data.evidence ?? []).map(mapEvidence),
    answer: (data.answer ?? []).map(mapAnswerBlock),
    crosscheck: data.crosscheck ?? "",
  }
}
