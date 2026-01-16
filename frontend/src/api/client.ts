import type {
  AnswerBlock,
  AskResponse,
  BatchDeleteResult,
  DeleteResult,
  DuplicateCheck,
  EvidenceChunk,
  IndexStatus,
  ManifestEntry,
  UploadProgress,
  UploadResult,
  Project,
  ProjectCreate,
  ChatMessage,
  Settings,
  ValidateResult
} from "../types"
import { getFileName } from "../utils"

// When bundled, frontend is served from the same server - use relative URLs
// In development, VITE_API_URL can be set to point to the backend
const API_BASE = import.meta.env.VITE_API_URL ?? ""

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
    sha256: item.sha256 ?? undefined,
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

export async function fetchManifest(projectId: string): Promise<ManifestEntry[]> {
  const data = await fetchJson<any[]>(`/api/projects/${projectId}/manifest`)
  return data.map(mapManifestEntry)
}

export async function fetchBankManifest(): Promise<ManifestEntry[]> {
  const data = await fetchJson<any[]>(`/api/bank/manifest`)
  return data.map(mapManifestEntry)
}

export async function fetchProjectFiles(projectId: string): Promise<string[]> {
  const data = await fetchJson<any>(`/api/projects/${projectId}/files`)
  return data.selected_files ?? []
}

export async function selectProjectFiles(projectId: string, relPaths: string[]): Promise<string[]> {
  const data = await fetchJson<any>(`/api/projects/${projectId}/files/select`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rel_paths: relPaths }),
  })
  return data.selected_files ?? []
}

export async function removeProjectFiles(projectId: string, relPaths: string[]): Promise<string[]> {
  const data = await fetchJson<any>(`/api/projects/${projectId}/files/remove`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rel_paths: relPaths }),
  })
  return data.selected_files ?? []
}

export async function fetchIndexStatus(projectId: string): Promise<IndexStatus> {
  const data = await fetchJson<any>(`/api/projects/${projectId}/status`)
  return {
    indexed: data.indexed ?? false,
    lastIngest: data.last_ingest ?? data.lastIngest ?? null,
    totalFiles: data.total_files ?? data.totalFiles ?? 0,
    totalChunks: data.total_chunks ?? data.totalChunks ?? 0,
  }
}

export async function askQuestion(projectId: string, question: string): Promise<AskResponse> {
  const data = await fetchJson<any>(`/api/projects/${projectId}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  })
  return {
    question: data.question ?? question,
    scope: data.scope ?? [],
    evidence: (data.evidence ?? []).map(mapEvidence),
    answer: (data.answer ?? []).map(mapAnswerBlock),
    answerMarkdown: data.answer_markdown ?? "",
    crosscheck: data.crosscheck ?? "",
  }
}

export type StreamEventHandler = (event: string, payload: any) => void

export async function streamAsk(
  projectId: string,
  question: string,
  onEvent: StreamEventHandler,
  context?: string[],
  useNotes?: boolean,
  notes?: EvidenceChunk[],
  history?: ChatMessage[]
): Promise<void> {
  const body = {
    question,
    context: context && context.length > 0 ? context : undefined,
    use_notes: useNotes,
    notes: notes && notes.length > 0 ? notes : undefined,
    history: history && history.length > 0 ? history : undefined
  }

  const response = await fetch(`${API_BASE}/api/projects/${projectId}/ask/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })

  if (!response.ok || !response.body) {
    const detail = await response.text()
    throw new Error(`API ${response.status}: ${detail || "Stream failed"}`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder("utf-8")
  let buffer = ""

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let boundary = buffer.indexOf("\n\n")
    while (boundary !== -1) {
      const raw = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)

      let event = "message"
      let data = ""
      for (const line of raw.split("\n")) {
        if (line.startsWith("event:")) {
          event = line.replace("event:", "").trim()
        } else if (line.startsWith("data:")) {
          data += line.replace("data:", "").trim()
        }
      }

      if (data) {
        try {
          onEvent(event, JSON.parse(data))
        } catch {
          onEvent(event, data)
        }
      }
      boundary = buffer.indexOf("\n\n")
    }
  }
}
export async function streamSummarize(
  projectId: string,
  messages: ChatMessage[],
  onDelta: (delta: string) => void,
  onDone: (title: string) => void
): Promise<void> {
  const response = await fetch(`${API_BASE}/api/projects/${projectId}/summarize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages }),
  })

  if (!response.ok || !response.body) {
    onDone("New Chat")
    return
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder("utf-8")
  let buffer = ""

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let boundary = buffer.indexOf("\n\n")
    while (boundary !== -1) {
      const raw = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)

      let event = "message"
      let data = ""
      for (const line of raw.split("\n")) {
        if (line.startsWith("event:")) {
          event = line.replace("event:", "").trim()
        } else if (line.startsWith("data:")) {
          data += line.replace("data:", "").trim()
        }
      }

      if (data) {
        try {
          const payload = JSON.parse(data)
          if (event === "title_delta") {
            onDelta(payload.delta || "")
          } else if (event === "title_done") {
            onDone(payload.title || "New Chat")
          }
        } catch {
          // ignore parse errors
        }
      }
      boundary = buffer.indexOf("\n\n")
    }
  }
}

// =============================================================================
// File Upload API
// =============================================================================

export type UploadEventHandler = {
  onProgress?: (progress: UploadProgress) => void
  onDuplicate?: (sha256: string, existingPath: string) => void
  onComplete?: (result: UploadResult) => void
  onError?: (code: string, message: string) => void
}

export async function uploadFileStream(
  projectId: string,
  file: File,
  handlers: UploadEventHandler,
  replaceExisting: boolean = false
): Promise<UploadResult | null> {
  const formData = new FormData()
  formData.append("file", file, getFileName(file.name))
  formData.append("replace_existing", String(replaceExisting))

  console.log("[upload] Starting upload for:", file.name)

  const response = await fetch(`${API_BASE}/api/projects/${projectId}/upload/stream`, {
    method: "POST",
    body: formData,
  })

  console.log("[upload] Response status:", response.status)

  if (!response.ok || !response.body) {
    const detail = await response.text()
    console.error("[upload] Request failed:", detail)
    handlers.onError?.("UPLOAD_FAILED", detail || "Upload request failed")
    return null
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder("utf-8")
  let buffer = ""
  let result: UploadResult | null = null

  while (true) {
    const { value, done } = await reader.read()
    if (done) {
      console.log("[upload] Stream done, remaining buffer:", buffer)
      break
    }
    buffer += decoder.decode(value, { stream: true })
    console.log("[upload] Received chunk, buffer length:", buffer.length)

    let boundary = buffer.indexOf("\n\n")
    while (boundary !== -1) {
      const raw = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)

      let event = "message"
      let data = ""
      for (const line of raw.split("\n")) {
        if (line.startsWith("event:")) {
          event = line.replace("event:", "").trim()
        } else if (line.startsWith("data:")) {
          data += line.replace("data:", "").trim()
        }
      }

      console.log("[upload] SSE event:", event, "data:", data.slice(0, 100))

      if (data) {
        try {
          const payload = JSON.parse(data)

          if (event === "progress") {
            console.log("[upload] Progress:", payload.phase, payload.percent)
            handlers.onProgress?.({
              phase: payload.phase,
              percent: payload.percent,
            })
          } else if (event === "duplicate") {
            console.log("[upload] Duplicate detected:", payload.existing_path)
            handlers.onDuplicate?.(payload.sha256, payload.existing_path)
            result = {
              success: false,
              relPath: "",
              sha256: payload.sha256,
              status: "duplicate",
              duplicatePath: payload.existing_path,
            }
          } else if (event === "complete") {
            console.log("[upload] Complete:", payload.rel_path)
            result = {
              success: true,
              relPath: payload.rel_path,
              sha256: payload.sha256,
              status: payload.status,
              manifestEntry: payload.manifest_entry ? mapManifestEntry(payload.manifest_entry) : undefined,
            }
            handlers.onComplete?.(result)
          } else if (event === "error") {
            console.error("[upload] Error:", payload.code, payload.message)
            handlers.onError?.(payload.code, payload.message)
            result = {
              success: false,
              relPath: "",
              sha256: "",
              status: "error",
              message: payload.message,
            }
          }
        } catch (e) {
          console.error("[upload] Parse error:", e)
        }
      }
      boundary = buffer.indexOf("\n\n")
    }
  }

  console.log("[upload] Final result:", result)
  return result
}

// Upload file to global Reference Bank (not project-specific)
export async function uploadFileToBankStream(
  file: File,
  handlers: UploadEventHandler,
  replaceExisting: boolean = false
): Promise<UploadResult | null> {
  const formData = new FormData()
  formData.append("file", file, getFileName(file.name))
  formData.append("replace_existing", String(replaceExisting))

  console.log("[bank-upload] Starting upload for:", file.name)

  const response = await fetch(`${API_BASE}/api/bank/upload/stream`, {
    method: "POST",
    body: formData,
  })

  console.log("[bank-upload] Response status:", response.status)

  if (!response.ok || !response.body) {
    const detail = await response.text()
    console.error("[bank-upload] Request failed:", detail)
    handlers.onError?.("UPLOAD_FAILED", detail || "Upload request failed")
    return null
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder("utf-8")
  let buffer = ""
  let result: UploadResult | null = null

  while (true) {
    const { value, done } = await reader.read()
    if (done) {
      console.log("[bank-upload] Stream done, remaining buffer:", buffer)
      break
    }
    buffer += decoder.decode(value, { stream: true })
    console.log("[bank-upload] Received chunk, buffer length:", buffer.length)

    let boundary = buffer.indexOf("\n\n")
    while (boundary !== -1) {
      const raw = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)

      let event = "message"
      let data = ""
      for (const line of raw.split("\n")) {
        if (line.startsWith("event:")) {
          event = line.replace("event:", "").trim()
        } else if (line.startsWith("data:")) {
          data += line.replace("data:", "").trim()
        }
      }

      console.log("[bank-upload] SSE event:", event, "data:", data.slice(0, 100))

      if (data) {
        try {
          const payload = JSON.parse(data)

          if (event === "progress") {
            console.log("[bank-upload] Progress:", payload.phase, payload.percent)
            handlers.onProgress?.({
              phase: payload.phase,
              percent: payload.percent,
            })
          } else if (event === "duplicate") {
            console.log("[bank-upload] Duplicate detected:", payload.existing_path)
            handlers.onDuplicate?.(payload.sha256, payload.existing_path)
            result = {
              success: false,
              relPath: "",
              sha256: payload.sha256,
              status: "duplicate",
              duplicatePath: payload.existing_path,
            }
          } else if (event === "complete") {
            console.log("[bank-upload] Complete:", payload.rel_path)
            result = {
              success: true,
              relPath: payload.rel_path,
              sha256: payload.sha256,
              status: payload.status,
              manifestEntry: payload.manifest_entry ? mapManifestEntry(payload.manifest_entry) : undefined,
            }
            handlers.onComplete?.(result)
          } else if (event === "error") {
            console.error("[bank-upload] Error:", payload.code, payload.message)
            handlers.onError?.(payload.code, payload.message)
            result = {
              success: false,
              relPath: "",
              sha256: "",
              status: "error",
              message: payload.message,
            }
          }
        } catch (e) {
          console.error("[bank-upload] Parse error:", e)
        }
      }
      boundary = buffer.indexOf("\n\n")
    }
  }

  console.log("[bank-upload] Final result:", result)
  return result
}

export async function fetchFileStats(): Promise<Record<string, { usage_count: number; last_used: number }>> {
  const data = await fetchJson<Record<string, { usage_count: number; last_used: number }>>("/api/bank/files/stats")
  return data
}


export async function deleteFile(projectId: string, relPath: string): Promise<DeleteResult> {
  const fileName = getFileName(relPath)
  const response = await fetch(`${API_BASE}/api/projects/${projectId}/files/${encodeURIComponent(fileName)}`, {
    method: "DELETE",
  })

  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`Delete failed: ${detail}`)
  }

  const data = await response.json()
  return {
    success: data.success ?? false,
    removedChunks: data.removed_chunks ?? 0,
    message: data.message ?? "",
  }
}

export async function batchDeleteFiles(projectId: string, relPaths: string[]): Promise<BatchDeleteResult> {
  const fileNames = relPaths.map(getFileName)
  const response = await fetch(`${API_BASE}/api/projects/${projectId}/files/batch-delete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rel_paths: fileNames }),
  })

  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`Batch delete failed: ${detail}`)
  }

  const data = await response.json()
  return {
    success: data.success ?? false,
    deletedCount: data.deleted_count ?? 0,
    failedCount: data.failed_count ?? 0,
    totalChunksRemoved: data.total_chunks_removed ?? 0,
    results: (data.results ?? []).map((r: any) => ({
      relPath: r.rel_path,
      success: r.success,
      removedChunks: r.removed_chunks,
      error: r.error,
    })),
  }
}

export async function checkDuplicate(projectId: string, sha256: string): Promise<DuplicateCheck> {
  const data = await fetchJson<any>(`/api/projects/${projectId}/files/check-duplicate?sha256=${sha256}`)
  return {
    isDuplicate: data.is_duplicate ?? false,
    existingPath: data.existing_path ?? null,
    existingEntry: data.existing_entry ? mapManifestEntry(data.existing_entry) : null,
  }
}

export function getFileUrl(_projectId: string, relPath: string): string {
  return `${API_BASE}/files/${encodeURIComponent(relPath)}`
}

// =============================================================================
// Project API
// =============================================================================

function mapProject(item: any): Project {
  return {
    id: item.id,
    name: item.name,
    rootPath: item.root_path ?? item.rootPath,
    createdAt: item.created_at ?? item.createdAt,
    lastActive: item.last_active ?? item.lastActive,
    fileCount: item.file_count ?? item.fileCount ?? 0,
    noteCount: item.note_count ?? item.noteCount ?? 0,
    description: item.description,
    icon: item.icon,
    selectedFiles: item.selected_files ?? item.selectedFiles ?? []
  }
}

export async function fetchProjects(): Promise<Project[]> {
  const data = await fetchJson<any[]>("/api/projects")
  return data.map(mapProject)
}

export async function createProject(req: ProjectCreate): Promise<Project> {
  const data = await fetchJson<any>("/api/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  })
  return mapProject(data)
}

export async function deleteProject(projectId: string): Promise<void> {
  await fetchJson(`/api/projects/${projectId}`, { method: "DELETE" })
}

export async function activateProject(projectId: string): Promise<void> {
  await fetchJson(`/api/projects/${projectId}/activate`, { method: "POST" })
}

// =============================================================================
// Settings API
// =============================================================================

export async function getSettings(): Promise<Settings> {
  const data = await fetchJson<any>("/api/settings")
  return {
    hasApiKey: data.has_api_key ?? false,
    maskedApiKey: data.masked_api_key ?? null,
    baseUrl: data.base_url ?? "https://api.deepseek.com",
    model: data.model ?? "deepseek-chat",
  }
}

export async function saveApiKey(apiKey: string): Promise<{ success: boolean; maskedApiKey: string }> {
  const data = await fetchJson<any>("/api/settings/api-key", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: apiKey }),
  })
  return {
    success: data.success ?? false,
    maskedApiKey: data.masked_api_key ?? "",
  }
}

export async function deleteApiKey(): Promise<{ success: boolean; hasApiKey: boolean }> {
  const data = await fetchJson<any>("/api/settings/api-key", {
    method: "DELETE",
  })
  return {
    success: data.success ?? false,
    hasApiKey: data.has_api_key ?? false,
  }
}

export async function validateApiKey(): Promise<ValidateResult> {
  const data = await fetchJson<any>("/api/settings/validate", {
    method: "POST",
  })
  return {
    valid: data.valid ?? false,
    error: data.error,
  }
}

// =============================================================================
// Chat Session API
// =============================================================================

import type { ChatSession } from "../types"

interface ChatSessionWithMessages extends ChatSession {
  messages: ChatMessage[]
}

function mapChatMessage(item: any): ChatMessage {
  return {
    id: item.id,
    role: item.role,
    content: item.content,
    timestamp: item.timestamp,
    timeline: item.timeline ?? [],
    sources: (item.sources ?? []).map(mapEvidence),
    keywords: item.keywords ?? [],
    isStreaming: item.isStreaming ?? false,
    completedAt: item.completedAt,
  }
}

function mapChatSession(item: any): ChatSession {
  return {
    id: item.id,
    title: item.title,
    lastActive: item.lastActive,
    messageCount: item.messageCount ?? 0,
    preview: item.preview ?? "",
  }
}

function mapChatSessionWithMessages(item: any): ChatSessionWithMessages {
  return {
    ...mapChatSession(item),
    messages: (item.messages ?? []).map(mapChatMessage),
  }
}

export async function fetchChatSessions(projectId: string): Promise<ChatSession[]> {
  const data = await fetchJson<any[]>(`/api/projects/${projectId}/chats`)
  return data.map(mapChatSession)
}

export async function createChatSession(projectId: string, title: string = "New Chat"): Promise<ChatSession> {
  const data = await fetchJson<any>(`/api/projects/${projectId}/chats`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  })
  return mapChatSession(data)
}

export async function fetchChatSession(projectId: string, sessionId: string): Promise<ChatSessionWithMessages> {
  const data = await fetchJson<any>(`/api/projects/${projectId}/chats/${sessionId}`)
  return mapChatSessionWithMessages(data)
}

export async function updateChatSession(
  projectId: string,
  sessionId: string,
  updates: { title?: string; messages?: ChatMessage[] }
): Promise<ChatSessionWithMessages> {
  const data = await fetchJson<any>(`/api/projects/${projectId}/chats/${sessionId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  })
  return mapChatSessionWithMessages(data)
}

export async function deleteChatSession(projectId: string, sessionId: string): Promise<void> {
  await fetchJson(`/api/projects/${projectId}/chats/${sessionId}`, { method: "DELETE" })
}

export async function addChatMessage(
  projectId: string,
  sessionId: string,
  message: ChatMessage
): Promise<ChatSessionWithMessages> {
  const data = await fetchJson<any>(`/api/projects/${projectId}/chats/${sessionId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  })
  return mapChatSessionWithMessages(data)
}

export async function updateChatMessage(
  projectId: string,
  sessionId: string,
  messageId: string,
  updates: Partial<ChatMessage>
): Promise<ChatSessionWithMessages> {
  const data = await fetchJson<any>(`/api/projects/${projectId}/chats/${sessionId}/messages`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message_id: messageId, updates }),
  })
  return mapChatSessionWithMessages(data)
}
