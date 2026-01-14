import type {
  AnswerBlock,
  AskResponse,
  DeleteResult,
  DuplicateCheck,
  EvidenceChunk,
  IndexStatus,
  ManifestEntry,
  UploadProgress,
  UploadResult,
} from "../types"

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
    evidence: (data.evidence ?? []).map(mapEvidence),
    answer: (data.answer ?? []).map(mapAnswerBlock),
    answerMarkdown: data.answer_markdown ?? "",
    crosscheck: data.crosscheck ?? "",
  }
}

export type StreamEventHandler = (event: string, payload: any) => void

export async function streamAsk(
  question: string,
  onEvent: StreamEventHandler,
  context?: string[],
  useNotes?: boolean,
  notes?: EvidenceChunk[]
): Promise<void> {
  const body = {
    question,
    context: context && context.length > 0 ? context : undefined,
    use_notes: useNotes,
    notes: notes && notes.length > 0 ? notes : undefined
  }

  const response = await fetch(`${API_BASE}/ask/stream`, {
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
  messages: any[],
  onDelta: (delta: string) => void,
  onDone: (title: string) => void
): Promise<void> {
  const response = await fetch(`${API_BASE}/summarize`, {
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
  file: File,
  handlers: UploadEventHandler,
  replaceExisting: boolean = false
): Promise<UploadResult | null> {
  const formData = new FormData()
  formData.append("file", file)
  formData.append("replace_existing", String(replaceExisting))

  console.log("[upload] Starting upload for:", file.name)

  const response = await fetch(`${API_BASE}/upload/stream`, {
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

export async function deleteFile(relPath: string): Promise<DeleteResult> {
  const response = await fetch(`${API_BASE}/files/${encodeURIComponent(relPath)}`, {
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

export async function checkDuplicate(sha256: string): Promise<DuplicateCheck> {
  const data = await fetchJson<any>(`/files/check-duplicate?sha256=${sha256}`)
  return {
    isDuplicate: data.is_duplicate ?? false,
    existingPath: data.existing_path ?? null,
    existingEntry: data.existing_entry ? mapManifestEntry(data.existing_entry) : null,
  }
}
