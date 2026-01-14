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

export interface TimelineStep {
  phase: string
  message: string
  startTime: number  // epoch ms
}

export interface ChatMessage {
  id: string
  role: "user" | "ai"
  content: string
  timestamp: number
  timeline?: TimelineStep[]
  sources?: EvidenceChunk[]
  keywords?: string[]
  isStreaming?: boolean
  completedAt?: number  // epoch ms when streaming completed
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

// Upload types
export type UploadPhase = "uploading" | "hashing" | "checking_duplicate" | "storing" | "extracting" | "indexing"
export type UploadStatus = "pending" | "uploading" | "processing" | "complete" | "error" | "duplicate"

export interface UploadProgress {
  phase: UploadPhase
  percent?: number
}

export interface UploadResult {
  success: boolean
  relPath: string
  sha256: string
  status: "processed" | "duplicate" | "replaced" | "error"
  message?: string
  manifestEntry?: ManifestEntry
  duplicatePath?: string
}

export interface UploadItem {
  id: string
  file: File
  status: UploadStatus
  progress: number
  error?: string
  duplicatePath?: string
  result?: UploadResult
}

export interface DuplicateCheck {
  isDuplicate: boolean
  existingPath?: string | null
  existingEntry?: ManifestEntry | null
}

export interface DeleteResult {
  success: boolean
  removedChunks: number
  message: string
}