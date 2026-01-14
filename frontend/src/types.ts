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

export interface ChatMessage {
  id: string
  role: "user" | "ai"
  content: string
  timestamp: number
  timeline?: { phase: string; message: string; timestamp: string }[]
  sources?: EvidenceChunk[]
  keywords?: string[]
  isStreaming?: boolean
}

export interface ChatSession {
  id: string
  title: string
  lastActive: number
  messageCount: number
  preview: string
}

export interface IndexStatus {
  indexed: boolean
  lastIngest?: string | null
  totalFiles?: number
  totalChunks?: number
}

export interface AskResponse {
  question: string
  scope: string[]
  evidence: EvidenceChunk[]
  answer: AnswerBlock[]
  answerMarkdown: string
  crosscheck: string
}