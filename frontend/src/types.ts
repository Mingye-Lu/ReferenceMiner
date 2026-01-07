export type FileType = "pdf" | "docx" | "image" | "table" | "text"

export interface ManifestEntry {
  relPath: string
  fileType: FileType
  title?: string | null
  abstract?: string | null
  pageCount?: number | null
  sizeBytes?: number
}

export interface EvidenceChunk {
  chunkId: string
  path: string
  page?: number | null
  section?: string | null
  text: string
  score: number
}

export interface AnswerBlock {
  heading: string
  body: string
  citations: string[]
}

export interface AskResponse {
  question: string
  scope: string[]
  keywords: string[]
  evidence: EvidenceChunk[]
  answer: AnswerBlock[]
  crosscheck: string
}

export interface IndexStatus {
  indexed: boolean
  lastIngest?: string | null
  totalFiles?: number
  totalChunks?: number
}
