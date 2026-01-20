export type FileType = "pdf" | "docx" | "image" | "table" | "text"

export interface ManifestEntry {
  relPath: string
  fileType: FileType
  title?: string | null
  abstract?: string | null
  pageCount?: number | null
  sizeBytes?: number
  sha256?: string
}

export interface BoundingBox {
  page: number
  x0: number
  y0: number
  x1: number
  y1: number
  charStart: number
  charEnd: number
}

export interface EvidenceChunk {
  chunkId: string
  path: string
  page?: number | null
  section?: string | null
  text: string
  score: number
  bbox?: BoundingBox[] | null
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
  details?: string
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

export interface BatchDeleteFileResult {
  relPath: string
  success: boolean
  removedChunks?: number
  error?: string
}

export interface BatchDeleteResult {
  success: boolean
  deletedCount: number
  failedCount: number
  totalChunksRemoved: number
  results: BatchDeleteFileResult[]
}

// Project types
export interface Project {
  id: string
  name: string
  rootPath: string
  createdAt: number
  lastActive: number
  fileCount: number
  noteCount: number
  description?: string
  icon?: string
  selectedFiles?: string[]
}

export interface ProjectCreate {
  name: string
  description?: string
}

// Settings types
export interface Settings {
  activeProvider: string
  providerKeys: Record<string, { hasKey: boolean; maskedKey: string | null }>
  providerSettings: Record<string, { baseUrl: string; model: string }>
  baseUrl: string
  model: string
}

export interface BalanceInfo {
  currency: string
  totalBalance: string
  grantedBalance: string
  toppedUpBalance: string
}

export interface ValidateResult {
  valid: boolean
  error?: string
  isAvailable?: boolean
  balanceInfos?: BalanceInfo[]
}
