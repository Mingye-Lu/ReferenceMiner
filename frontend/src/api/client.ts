import type {
  AnswerBlock,
  AskResponse,
  BatchDeleteEventHandler,
  BatchDeleteResult,
  DeleteEventHandler,
  DeleteResult,
  DuplicateCheck,
  EvidenceChunk,
  IndexStatus,
  ManifestEntry,
  HighlightGroup,
  UploadProgress,
  UploadResult,
  Project,
  ProjectCreate,
  ChatMessage,
  Settings,
  UpdateCheck,
  ValidateResult,
  QueueJob,
  Bibliography,
  OcrConfig,
  OcrSettingsResponse,
} from "../types";
import { getFileName } from "../utils";

// When bundled, frontend is served from the same server - use relative URLs
// In development, VITE_API_URL can be set to point to the backend
const API_BASE = import.meta.env.VITE_API_URL ?? "";

const DEFAULT_PROVIDER_SETTINGS: Record<
  string,
  { baseUrl: string; model: string }
> = {
  deepseek: { baseUrl: "https://api.deepseek.com", model: "deepseek-chat" },
  openai: { baseUrl: "https://api.openai.com/v1", model: "gpt-4o-mini" },
  gemini: {
    baseUrl: "https://generativelanguage.googleapis.com/v1beta/openai",
    model: "gemini-1.5-flash",
  },
  anthropic: {
    baseUrl: "https://api.anthropic.com/v1",
    model: "claude-3-haiku-20240307",
  },
  custom: { baseUrl: "https://api.openai.com/v1", model: "gpt-4o-mini" },
};

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`API ${response.status}: ${detail || "Request failed"}`);
  }
  return response.json() as Promise<T>;
}

function mapBibliography(item: any): ManifestEntry["bibliography"] {
  if (!item) return null;
  return {
    docType: item.doc_type ?? item.docType ?? null,
    language: item.language ?? item.lang ?? null,
    title: item.title ?? null,
    subtitle: item.subtitle ?? null,
    authors: (item.authors ?? []).map((author: any) => ({
      family: author.family ?? null,
      given: author.given ?? null,
      literal: author.literal ?? author.name ?? null,
      sequence: author.sequence ?? null,
    })),
    organization: item.organization ?? null,
    year: item.year ?? null,
    date: item.date ?? null,
    journal: item.journal ?? null,
    volume: item.volume ?? null,
    issue: item.issue ?? null,
    pages: item.pages ?? null,
    publisher: item.publisher ?? null,
    place: item.place ?? null,
    conference: item.conference ?? null,
    institution: item.institution ?? null,
    reportNumber: item.report_number ?? item.reportNumber ?? null,
    standardNumber: item.standard_number ?? item.standardNumber ?? null,
    patentNumber: item.patent_number ?? item.patentNumber ?? null,
    url: item.url ?? null,
    accessed: item.accessed ?? null,
    doi: item.doi ?? null,
    doiStatus: item.doi_status ?? item.doiStatus ?? null,
    extraction: item.extraction ?? null,
    verification: item.verification ?? null,
  };
}

function serializeBibliography(input: ManifestEntry["bibliography"]): any {
  if (!input) return null;
  return {
    doc_type: input.docType ?? undefined,
    language: input.language ?? undefined,
    title: input.title ?? undefined,
    subtitle: input.subtitle ?? undefined,
    authors: (input.authors ?? []).map((author) => ({
      family: author.family ?? undefined,
      given: author.given ?? undefined,
      literal: author.literal ?? undefined,
      sequence: author.sequence ?? undefined,
    })),
    organization: input.organization ?? undefined,
    year: input.year ?? undefined,
    date: input.date ?? undefined,
    journal: input.journal ?? undefined,
    volume: input.volume ?? undefined,
    issue: input.issue ?? undefined,
    pages: input.pages ?? undefined,
    publisher: input.publisher ?? undefined,
    place: input.place ?? undefined,
    conference: input.conference ?? undefined,
    institution: input.institution ?? undefined,
    report_number: input.reportNumber ?? undefined,
    standard_number: input.standardNumber ?? undefined,
    patent_number: input.patentNumber ?? undefined,
    url: input.url ?? undefined,
    accessed: input.accessed ?? undefined,
    doi: input.doi ?? undefined,
    doi_status: input.doiStatus ?? undefined,
    extraction: input.extraction ?? undefined,
    verification: input.verification ?? undefined,
  };
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
    bibliography: mapBibliography(item.bibliography),
  };
}

function mapEvidence(item: any): EvidenceChunk {
  return {
    chunkId: item.chunk_id ?? item.chunkId ?? "",
    path: item.path ?? item.rel_path ?? "",
    page: item.page ?? item.page_number ?? null,
    section: item.section ?? null,
    text: item.text ?? "",
    score: item.score ?? 0,
    bbox: item.bbox ?? null,
  };
}

function mapAnswerBlock(item: any): AnswerBlock {
  return {
    heading: item.heading ?? "Answer",
    body: item.body ?? item.text ?? "",
    citations: item.citations ?? [],
  };
}

function mapQueueJob(item: any): QueueJob {
  const rawStatus = item.status ?? "pending";
  const status = rawStatus === "failed" ? "error" : rawStatus;
  return {
    id: item.id ?? "",
    type: item.type ?? "upload",
    scope: item.scope ?? "bank",
    projectId: item.project_id ?? item.projectId ?? null,
    name: item.name ?? null,
    relPath: item.rel_path ?? item.relPath ?? null,
    status,
    phase: item.phase ?? null,
    progress: item.progress ?? null,
    error: item.error ?? null,
    duplicatePath: item.duplicate_path ?? item.duplicatePath ?? null,
    createdAt: item.created_at ?? item.createdAt ?? Date.now(),
    updatedAt: item.updated_at ?? item.updatedAt ?? Date.now(),
  };
}

export async function fetchManifest(
  projectId: string,
): Promise<ManifestEntry[]> {
  const data = await fetchJson<any[]>(`/api/projects/${projectId}/manifest`);
  return data.map(mapManifestEntry);
}

export async function fetchBankManifest(): Promise<ManifestEntry[]> {
  const data = await fetchJson<any[]>(`/api/bank/manifest`);
  return data.map(mapManifestEntry);
}

export async function fetchProjectFiles(projectId: string): Promise<string[]> {
  const data = await fetchJson<any>(`/api/projects/${projectId}/files`);
  return data.selected_files ?? [];
}

export async function selectProjectFiles(
  projectId: string,
  relPaths: string[],
): Promise<string[]> {
  const data = await fetchJson<any>(`/api/projects/${projectId}/files/select`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rel_paths: relPaths }),
  });
  return data.selected_files ?? [];
}

export async function removeProjectFiles(
  projectId: string,
  relPaths: string[],
): Promise<string[]> {
  const data = await fetchJson<any>(`/api/projects/${projectId}/files/remove`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rel_paths: relPaths }),
  });
  return data.selected_files ?? [];
}

export async function fetchIndexStatus(
  projectId: string,
): Promise<IndexStatus> {
  const data = await fetchJson<any>(`/api/projects/${projectId}/status`);
  return {
    indexed: data.indexed ?? false,
    lastIngest: data.last_ingest ?? data.lastIngest ?? null,
    totalFiles: data.total_files ?? data.totalFiles ?? 0,
    totalChunks: data.total_chunks ?? data.totalChunks ?? 0,
  };
}

export async function askQuestion(
  projectId: string,
  question: string,
): Promise<AskResponse> {
  const data = await fetchJson<any>(`/api/projects/${projectId}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  return {
    question: data.question ?? question,
    scope: data.scope ?? [],
    evidence: (data.evidence ?? []).map(mapEvidence),
    answer: (data.answer ?? []).map(mapAnswerBlock),
    answerMarkdown: data.answer_markdown ?? "",
    crosscheck: data.crosscheck ?? "",
  };
}

export type StreamEventHandler = (event: string, payload: any) => void;

export async function streamAsk(
  projectId: string,
  question: string,
  onEvent: StreamEventHandler,
  context?: string[],
  useNotes?: boolean,
  notes?: EvidenceChunk[],
  history?: ChatMessage[],
): Promise<void> {
  const body = {
    question,
    context: context && context.length > 0 ? context : undefined,
    use_notes: useNotes,
    notes: notes && notes.length > 0 ? notes : undefined,
    history: history && history.length > 0 ? history : undefined,
  };

  const response = await fetch(
    `${API_BASE}/api/projects/${projectId}/ask/stream`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );

  if (!response.ok || !response.body) {
    const detail = await response.text();
    throw new Error(`API ${response.status}: ${detail || "Stream failed"}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const raw = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);

      let event = "message";
      let data = "";
      for (const line of raw.split("\n")) {
        if (line.startsWith("event:")) {
          event = line.replace("event:", "").trim();
        } else if (line.startsWith("data:")) {
          data += line.replace("data:", "").trim();
        }
      }

      if (data) {
        try {
          onEvent(event, JSON.parse(data));
        } catch {
          onEvent(event, data);
        }
      }
      boundary = buffer.indexOf("\n\n");
    }
  }
}
export async function streamSummarize(
  projectId: string,
  messages: ChatMessage[],
  onDelta: (delta: string) => void,
  onDone: (title: string) => void,
): Promise<void> {
  const response = await fetch(
    `${API_BASE}/api/projects/${projectId}/summarize`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages }),
    },
  );

  if (!response.ok || !response.body) {
    onDone("New Chat");
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const raw = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);

      let event = "message";
      let data = "";
      for (const line of raw.split("\n")) {
        if (line.startsWith("event:")) {
          event = line.replace("event:", "").trim();
        } else if (line.startsWith("data:")) {
          data += line.replace("data:", "").trim();
        }
      }

      if (data) {
        try {
          const payload = JSON.parse(data);
          if (event === "title_delta") {
            onDelta(payload.delta || "");
          } else if (event === "title_done") {
            onDone(payload.title || "New Chat");
          }
        } catch {
          // ignore parse errors
        }
      }
      boundary = buffer.indexOf("\n\n");
    }
  }
}

// =============================================================================
// Queue API
// =============================================================================

export async function fetchQueueJobs(params?: {
  scope?: string;
  projectId?: string;
  includeCompleted?: boolean;
  includeDismissed?: boolean;
  limit?: number;
}): Promise<QueueJob[]> {
  const search = new URLSearchParams();
  if (params?.scope) search.set("scope", params.scope);
  if (params?.projectId) search.set("project_id", params.projectId);
  if (params?.includeCompleted) search.set("include_completed", "true");
  if (params?.includeDismissed) search.set("include_dismissed", "true");
  if (params?.limit) search.set("limit", String(params.limit));
  const query = search.toString();
  const path = query ? `/api/queue/jobs?${query}` : "/api/queue/jobs";
  const data = await fetchJson<any[]>(path);
  return (data ?? []).map(mapQueueJob);
}

export async function dismissQueueJob(jobId: string): Promise<QueueJob> {
  const data = await fetchJson<any>(`/api/queue/jobs/${jobId}/dismiss`, {
    method: "POST",
  });
  return mapQueueJob(data);
}

export async function streamQueueJobs(
  params: { scope?: string; projectId?: string } | undefined,
  onJob: (job: QueueJob) => void,
  signal?: AbortSignal,
  onError?: (error: Error) => void,
): Promise<void> {
  const search = new URLSearchParams();
  if (params?.scope) search.set("scope", params.scope);
  if (params?.projectId) search.set("project_id", params.projectId);
  const query = search.toString();
  const url = query
    ? `${API_BASE}/api/queue/stream?${query}`
    : `${API_BASE}/api/queue/stream`;

  console.log("[queue-stream] connecting to", url);
  const response = await fetch(url, { signal });
  if (!response.ok || !response.body) {
    const detail = await response.text();
    const error = new Error(
      `API ${response.status}: ${detail || "Queue stream failed"}`,
    );
    onError?.(error);
    throw error;
  }
  console.log("[queue-stream] connected");

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        console.log("[queue-stream] stream ended");
        break;
      }
      buffer += decoder.decode(value, { stream: true });

      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const raw = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);

        let event = "message";
        let data = "";
        for (const line of raw.split("\n")) {
          if (line.startsWith("event:")) {
            event = line.replace("event:", "").replace(/\s+/g, " ").trim();
          } else if (line.startsWith("data:")) {
            data += line.replace("data:", "").replace(/\s+/g, " ").trim();
          }
        }

        if (event !== "job") {
          boundary = buffer.indexOf("\n\n");
          continue;
        }

        if (data) {
          try {
            const payload = JSON.parse(data);
            const mapped = mapQueueJob(payload);
            console.log(
              "[queue-stream] job event:",
              mapped.id.slice(0, 8),
              "status:",
              mapped.status,
              "phase:",
              mapped.phase,
            );
            onJob(mapped);
          } catch (e) {
            console.error("[queue-stream] parse error:", e);
          }
        }
        boundary = buffer.indexOf("\n\n");
      }
    }
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      console.log("[queue-stream] stream aborted");
    } else {
      console.error("[queue-stream] stream error:", error);
      onError?.(error instanceof Error ? error : new Error(String(error)));
    }
    throw error;
  }
}

// =============================================================================
// File Upload API
// =============================================================================

export type UploadEventHandler = {
  onProgress?: (progress: UploadProgress) => void;
  onDuplicate?: (sha256: string, existingPath: string) => void;
  onComplete?: (result: UploadResult) => void;
  onError?: (code: string, message: string) => void;
};

export async function uploadFileStream(
  projectId: string,
  file: File,
  handlers: UploadEventHandler,
  replaceExisting: boolean = false,
  bibliography?: Bibliography | null,
): Promise<UploadResult | null> {
  const formData = new FormData();
  formData.append("file", file, getFileName(file.name));
  formData.append("replace_existing", String(replaceExisting));
  if (bibliography) {
    formData.append(
      "bibliography",
      JSON.stringify(serializeBibliography(bibliography)),
    );
  }

  console.log("[upload] Starting upload for:", file.name);

  const response = await fetch(
    `${API_BASE}/api/projects/${projectId}/upload/stream`,
    {
      method: "POST",
      body: formData,
    },
  );

  console.log("[upload] Response status:", response.status);

  if (!response.ok || !response.body) {
    const detail = await response.text();
    console.error("[upload] Request failed:", detail);
    handlers.onError?.("UPLOAD_FAILED", detail || "Upload request failed");
    return null;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let result: UploadResult | null = null;

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      console.log("[upload] Stream done, remaining buffer:", buffer);
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    console.log("[upload] Received chunk, buffer length:", buffer.length);

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const raw = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);

      let event = "message";
      let data = "";
      for (const line of raw.split("\n")) {
        if (line.startsWith("event:")) {
          event = line.replace("event:", "").trim();
        } else if (line.startsWith("data:")) {
          data += line.replace("data:", "").trim();
        }
      }

      console.log("[upload] SSE event:", event, "data:", data.slice(0, 100));

      if (data) {
        try {
          const payload = JSON.parse(data);

          if (event === "progress") {
            console.log("[upload] Progress:", payload.phase, payload.percent);
            handlers.onProgress?.({
              phase: payload.phase,
              percent: payload.percent,
            });
          } else if (event === "duplicate") {
            console.log("[upload] Duplicate detected:", payload.existing_path);
            handlers.onDuplicate?.(payload.sha256, payload.existing_path);
            result = {
              success: false,
              relPath: "",
              sha256: payload.sha256,
              status: "duplicate",
              duplicatePath: payload.existing_path,
            };
          } else if (event === "complete") {
            console.log("[upload] Complete:", payload.rel_path);
            result = {
              success: true,
              relPath: payload.rel_path,
              sha256: payload.sha256,
              status: payload.status,
              manifestEntry: payload.manifest_entry
                ? mapManifestEntry(payload.manifest_entry)
                : undefined,
            };
            handlers.onComplete?.(result);
          } else if (event === "error") {
            console.error("[upload] Error:", payload.code, payload.message);
            handlers.onError?.(payload.code, payload.message);
            result = {
              success: false,
              relPath: "",
              sha256: "",
              status: "error",
              message: payload.message,
            };
          }
        } catch (e) {
          console.error("[upload] Parse error:", e);
        }
      }
      boundary = buffer.indexOf("\n\n");
    }
  }

  console.log("[upload] Final result:", result);
  return result;
}

// Upload file to global Reference Bank (not project-specific)
export async function uploadFileToBankStream(
  file: File,
  handlers: UploadEventHandler,
  replaceExisting: boolean = false,
  bibliography?: Bibliography | null,
): Promise<UploadResult | null> {
  const formData = new FormData();
  formData.append("file", file, getFileName(file.name));
  formData.append("replace_existing", String(replaceExisting));
  if (bibliography) {
    formData.append(
      "bibliography",
      JSON.stringify(serializeBibliography(bibliography)),
    );
  }

  console.log("[bank-upload] Starting upload for:", file.name);

  const response = await fetch(`${API_BASE}/api/bank/upload/stream`, {
    method: "POST",
    body: formData,
  });

  console.log("[bank-upload] Response status:", response.status);

  if (!response.ok || !response.body) {
    const detail = await response.text();
    console.error("[bank-upload] Request failed:", detail);
    handlers.onError?.("UPLOAD_FAILED", detail || "Upload request failed");
    return null;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let result: UploadResult | null = null;

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      console.log("[bank-upload] Stream done, remaining buffer:", buffer);
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    console.log("[bank-upload] Received chunk, buffer length:", buffer.length);

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const raw = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);

      let event = "message";
      let data = "";
      for (const line of raw.split("\n")) {
        if (line.startsWith("event:")) {
          event = line.replace("event:", "").trim();
        } else if (line.startsWith("data:")) {
          data += line.replace("data:", "").trim();
        }
      }

      console.log(
        "[bank-upload] SSE event:",
        event,
        "data:",
        data.slice(0, 100),
      );

      if (data) {
        try {
          const payload = JSON.parse(data);

          if (event === "progress") {
            console.log(
              "[bank-upload] Progress:",
              payload.phase,
              payload.percent,
            );
            handlers.onProgress?.({
              phase: payload.phase,
              percent: payload.percent,
            });
          } else if (event === "duplicate") {
            console.log(
              "[bank-upload] Duplicate detected:",
              payload.existing_path,
            );
            handlers.onDuplicate?.(payload.sha256, payload.existing_path);
            result = {
              success: false,
              relPath: "",
              sha256: payload.sha256,
              status: "duplicate",
              duplicatePath: payload.existing_path,
            };
          } else if (event === "complete") {
            console.log("[bank-upload] Complete:", payload.rel_path);
            result = {
              success: true,
              relPath: payload.rel_path,
              sha256: payload.sha256,
              status: payload.status,
              manifestEntry: payload.manifest_entry
                ? mapManifestEntry(payload.manifest_entry)
                : undefined,
            };
            handlers.onComplete?.(result);
          } else if (event === "error") {
            console.error(
              "[bank-upload] Error:",
              payload.code,
              payload.message,
            );
            handlers.onError?.(payload.code, payload.message);
            result = {
              success: false,
              relPath: "",
              sha256: "",
              status: "error",
              message: payload.message,
            };
          }
        } catch (e) {
          console.error("[bank-upload] Parse error:", e);
        }
      }
      boundary = buffer.indexOf("\n\n");
    }
  }

  console.log("[bank-upload] Final result:", result);
  return result;
}

export async function fetchFileStats(): Promise<
  Record<string, { usage_count: number; last_used: number }>
> {
  const data = await fetchJson<
    Record<string, { usage_count: number; last_used: number }>
  >("/api/bank/files/stats");
  return data;
}

export async function deleteFile(
  projectId: string,
  relPath: string,
): Promise<DeleteResult> {
  const fileName = getFileName(relPath);
  const response = await fetch(
    `${API_BASE}/api/projects/${projectId}/files/${encodeURIComponent(fileName)}`,
    {
      method: "DELETE",
    },
  );

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Delete failed: ${detail}`);
  }

  const data = await response.json();
  return {
    success: data.success ?? false,
    removedChunks: data.removed_chunks ?? 0,
    message: data.message ?? "",
  };
}

export async function batchDeleteFiles(
  projectId: string,
  relPaths: string[],
): Promise<BatchDeleteResult> {
  const fileNames = relPaths.map(getFileName);
  const response = await fetch(
    `${API_BASE}/api/projects/${projectId}/files/batch-delete`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rel_paths: fileNames }),
    },
  );

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Batch delete failed: ${detail}`);
  }

  const data = await response.json();
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
  };
}

export async function checkDuplicate(
  projectId: string,
  sha256: string,
): Promise<DuplicateCheck> {
  const data = await fetchJson<any>(
    `/api/projects/${projectId}/files/check-duplicate?sha256=${sha256}`,
  );
  return {
    isDuplicate: data.is_duplicate ?? false,
    existingPath: data.existing_path ?? null,
    existingEntry: data.existing_entry
      ? mapManifestEntry(data.existing_entry)
      : null,
  };
}

export function getFileUrl(_projectId: string, relPath: string): string {
  // Encode each segment to handle special characters while preserving directory structure
  const encodedPath = relPath
    .split("/")
    .map((segment) => encodeURIComponent(segment))
    .join("/");

  // In development, bypass Vite proxy for files to avoid timeouts/limits with large files
  if (import.meta.env.DEV) {
    return `http://localhost:8000/files/${encodedPath}`;
  }

  return `${API_BASE}/files/${encodedPath}`;
}

export async function fetchFileHighlights(
  relPath: string,
): Promise<HighlightGroup[]> {
  const data = await fetchJson<any[]>(
    `/api/files/${encodeURIComponent(relPath)}/highlights`,
  );
  return (data ?? []).map((item) => ({
    id: item.chunk_id ?? item.chunkId ?? "",
    boxes: (item.bbox ?? item.boxes ?? []).map((box: any) => ({
      page: box.page,
      x0: box.x0,
      y0: box.y0,
      x1: box.x1,
      y1: box.y1,
      charStart: box.char_start ?? box.charStart ?? 0,
      charEnd: box.char_end ?? box.charEnd ?? 0,
    })),
  }));
}

export async function fetchFileMetadata(
  relPath: string,
): Promise<ManifestEntry["bibliography"]> {
  const data = await fetchJson<any>(
    `/api/files/${encodeURIComponent(relPath)}/metadata`,
  );
  return mapBibliography(data.bibliography);
}

export async function updateFileMetadata(
  relPath: string,
  bibliography: ManifestEntry["bibliography"],
): Promise<ManifestEntry["bibliography"]> {
  const data = await fetchJson<any>(
    `/api/files/${encodeURIComponent(relPath)}/metadata`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        bibliography: serializeBibliography(bibliography),
      }),
    },
  );
  return mapBibliography(data.bibliography);
}

export async function extractFileMetadata(
  relPath: string,
  force: boolean = false,
): Promise<ManifestEntry["bibliography"]> {
  const url = `/api/files/${encodeURIComponent(relPath)}/metadata/extract${force ? "?force=true" : ""}`;
  const data = await fetchJson<any>(url, {
    method: "POST",
  });
  return mapBibliography(data.bibliography);
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
    selectedFiles: item.selected_files ?? item.selectedFiles ?? [],
  };
}

export async function fetchProjects(): Promise<Project[]> {
  const data = await fetchJson<any[]>("/api/projects");
  return data.map(mapProject);
}

export async function createProject(req: ProjectCreate): Promise<Project> {
  const data = await fetchJson<any>("/api/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return mapProject(data);
}


export async function deleteProject(projectId: string): Promise<void> {
  await fetchJson(`/api/projects/${projectId}`, { method: "DELETE" });
}

export async function activateProject(projectId: string): Promise<void> {
  await fetchJson(`/api/projects/${projectId}/activate`, { method: "POST" });
}

// =============================================================================
// Settings API
// =============================================================================

export async function getSettings(): Promise<Settings> {
  const data = await fetchJson<any>("/api/settings");
  const activeProvider = data.active_provider ?? "deepseek";
  const defaults =
    DEFAULT_PROVIDER_SETTINGS[activeProvider] ??
    DEFAULT_PROVIDER_SETTINGS.custom;
  const providerKeys: Record<
    string,
    { hasKey: boolean; maskedKey: string | null }
  > = {};
  const rawKeys = data.provider_keys ?? {};
  Object.keys(rawKeys).forEach((key) => {
    providerKeys[key] = {
      hasKey: rawKeys[key]?.has_key ?? false,
      maskedKey: rawKeys[key]?.masked_key ?? null,
    };
  });
  const providerSettings: Record<string, { baseUrl: string; model: string }> =
    {};
  const rawSettings = data.provider_settings ?? {};
  Object.keys(DEFAULT_PROVIDER_SETTINGS).forEach((provider) => {
    const entry = rawSettings[provider] ?? {};
    const fallback = DEFAULT_PROVIDER_SETTINGS[provider];
    providerSettings[provider] = {
      baseUrl: entry.base_url ?? entry.baseUrl ?? fallback.baseUrl,
      model: entry.model ?? fallback.model,
    };
  });
  return {
    activeProvider,
    providerKeys,
    providerSettings,
    baseUrl: data.base_url ?? defaults.baseUrl,
    model: data.model ?? defaults.model,
    citationCopyFormat: data.citation_copy_format ?? "apa",
  };
}

export async function saveCitationCopyFormat(
  format: string,
): Promise<{ success: boolean; citationCopyFormat: string }> {
  const data = await fetchJson<any>("/api/settings/citation-format", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ format }),
  });
  return {
    success: data.success ?? false,
    citationCopyFormat: data.citation_copy_format ?? format,
  };
}

export async function saveApiKey(
  apiKey: string,
  provider: string,
): Promise<{ success: boolean; maskedApiKey: string; provider: string }> {
  const data = await fetchJson<any>("/api/settings/api-key", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: apiKey, provider }),
  });
  return {
    success: data.success ?? false,
    maskedApiKey: data.masked_api_key ?? "",
    provider: data.provider ?? provider,
  };
}

export async function deleteApiKey(
  provider: string,
): Promise<{ success: boolean; hasApiKey: boolean; provider: string }> {
  const data = await fetchJson<any>(
    `/api/settings/api-key?provider=${encodeURIComponent(provider)}`,
    {
      method: "DELETE",
    },
  );
  return {
    success: data.success ?? false,
    hasApiKey: data.has_api_key ?? false,
    provider: data.provider ?? provider,
  };
}

export async function validateApiKey(
  apiKey?: string,
  baseUrl?: string,
  model?: string,
  provider?: string,
): Promise<ValidateResult> {
  const data = await fetchJson<any>("/api/settings/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      api_key: apiKey ?? "",
      base_url: baseUrl ?? "",
      model: model ?? "",
      provider: provider ?? "",
    }),
  });
  return {
    valid: data.valid ?? false,
    error: data.error,
    isAvailable: data.is_available,
    balanceInfos: (data.balance_infos ?? []).map((info: any) => ({
      currency: info.currency,
      totalBalance: info.total_balance,
      grantedBalance: info.granted_balance,
      toppedUpBalance: info.topped_up_balance,
    })),
  };
}

export async function saveLlmSettings(
  baseUrl: string,
  model: string,
  provider: string,
): Promise<{
  success: boolean;
  baseUrl: string;
  model: string;
  activeProvider: string;
}> {
  const data = await fetchJson<any>("/api/settings/llm", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ base_url: baseUrl, model, provider }),
  });
  return {
    success: data.success ?? false,
    baseUrl: data.base_url ?? baseUrl,
    model: data.model ?? model,
    activeProvider: data.active_provider ?? provider,
  };
}

export async function resetAllData(): Promise<{
  success: boolean;
  message: string;
  deletedFiles: string[];
}> {
  const data = await fetchJson<any>("/api/settings/reset", {
    method: "POST",
  });
  return {
    success: data.success ?? false,
    message: data.message ?? "",
    deletedFiles: data.deleted_files ?? [],
  };
}

export async function fetchVersion(): Promise<string> {
  const data = await fetchJson<{ version: string }>("/api/settings/version");
  return data.version ?? "unknown";
}

export async function fetchUpdateCheck(): Promise<UpdateCheck> {
  const data = await fetchJson<any>("/api/settings/update-check");
  return {
    repo: data.repo ?? "",
    current: {
      version: data.current?.version ?? "unknown",
    },
    latest: {
      version: data.latest?.version ?? null,
      url: data.latest?.url ?? null,
      source: data.latest?.source ?? null,
    },
    isUpdateAvailable: data.is_update_available ?? false,
    checkedAt: data.checked_at ?? undefined,
    error: data.error ?? null,
  };
}
export type ReprocessEventHandler = {
  onStart?: (totalFiles: number) => void;
  onFile?: (payload: {
    relPath: string;
    status: string;
    phase?: string;
    index?: number;
    total?: number;
  }) => void;
  onProgress?: (payload: { phase: string; percent?: number }) => void;
  onComplete?: (payload: { totalFiles: number; totalChunks: number }) => void;
  onError?: (code: string, message: string) => void;
};

export async function reprocessReferenceBankStream(
  handlers: ReprocessEventHandler,
): Promise<void> {
  const response = await fetch(`${API_BASE}/api/bank/reprocess/stream`, {
    method: "POST",
  });

  if (!response.ok || !response.body) {
    const detail = await response.text();
    handlers.onError?.(
      "REPROCESS_FAILED",
      detail || "Reprocess request failed",
    );
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const raw = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);

      let event = "message";
      let data = "";
      for (const line of raw.split("\n")) {
        if (line.startsWith("event:")) {
          event = line.replace("event:", "").trim();
        } else if (line.startsWith("data:")) {
          data += line.replace("data:", "").trim();
        }
      }

      if (data) {
        try {
          const payload = JSON.parse(data);
          if (event === "start") {
            handlers.onStart?.(payload.total_files ?? 0);
          } else if (event === "file") {
            handlers.onFile?.({
              relPath: payload.rel_path ?? "",
              status: payload.status ?? "processing",
              phase: payload.phase,
              index: payload.index,
              total: payload.total,
            });
          } else if (event === "progress") {
            handlers.onProgress?.({
              phase: payload.phase ?? "",
              percent: payload.percent,
            });
          } else if (event === "complete") {
            handlers.onComplete?.({
              totalFiles: payload.total_files ?? 0,
              totalChunks: payload.total_chunks ?? 0,
            });
          } else if (event === "error") {
            handlers.onError?.(
              payload.code ?? "REPROCESS_ERROR",
              payload.message ?? "Reprocess failed",
            );
          }
        } catch (e) {
          console.error("[reprocess] Parse error:", e);
        }
      }
      boundary = buffer.indexOf("\n\n");
    }
  }
}

export async function reprocessReferenceFileStream(
  relPath: string,
  handlers: ReprocessEventHandler,
): Promise<void> {
  const response = await fetch(
    `${API_BASE}/api/bank/files/${encodeURIComponent(relPath)}/reprocess/stream`,
    {
      method: "POST",
    },
  );

  if (!response.ok || !response.body) {
    const detail = await response.text();
    handlers.onError?.(
      "REPROCESS_FAILED",
      detail || "Reprocess request failed",
    );
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const raw = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);

      let event = "message";
      let data = "";
      for (const line of raw.split("\n")) {
        if (line.startsWith("event:")) {
          event = line.replace("event:", "").trim();
        } else if (line.startsWith("data:")) {
          data += line.replace("data:", "").trim();
        }
      }

      if (data) {
        try {
          const payload = JSON.parse(data);
          if (event === "file") {
            handlers.onFile?.({
              relPath: payload.rel_path ?? "",
              status: payload.status ?? "processing",
              phase: payload.phase,
            });
          } else if (event === "complete") {
            handlers.onComplete?.({
              totalFiles: 1,
              totalChunks: 0,
            });
          } else if (event === "error") {
            handlers.onError?.(
              payload.code ?? "REPROCESS_ERROR",
              payload.message ?? "Reprocess failed",
            );
          }
        } catch (e) {
          console.error("[reprocess-file] Parse error:", e);
        }
      }
      boundary = buffer.indexOf("\n\n");
    }
  }
}

export async function deleteFileStream(
  relPath: string,
  handlers: DeleteEventHandler,
): Promise<void> {
  const response = await fetch(
    `${API_BASE}/api/projects/default/files/${encodeURIComponent(relPath)}/delete/stream`,
    {
      method: "POST",
    },
  );

  if (!response.ok || !response.body) {
    const detail = await response.text();
    handlers.onError?.("DELETE_FAILED", detail || "Delete request failed");
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const raw = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);

      let event = "message";
      let data = "";
      for (const line of raw.split("\n")) {
        if (line.startsWith("event:")) {
          event = line.replace("event:", "").trim();
        } else if (line.startsWith("data:")) {
          data += line.replace("data:", "").trim();
        }
      }

      if (data) {
        try {
          const payload = JSON.parse(data);
          if (event === "file") {
            handlers.onFile?.({
              relPath: payload.rel_path ?? "",
              status: payload.status ?? "processing",
              phase: payload.phase,
            });
          } else if (event === "complete") {
            handlers.onComplete?.({
              relPath: payload.rel_path ?? "",
              removedChunks: payload.removed_chunks ?? 0,
            });
          } else if (event === "error") {
            handlers.onError?.(
              payload.code ?? "DELETE_ERROR",
              payload.message ?? "Delete failed",
            );
          }
        } catch (e) {
          console.error("[delete-file] Parse error:", e);
        }
      }
      boundary = buffer.indexOf("\n\n");
    }
  }
}

export async function batchDeleteFilesStream(
  relPaths: string[],
  handlers: BatchDeleteEventHandler,
): Promise<void> {
  const response = await fetch(
    `${API_BASE}/api/projects/default/files/batch-delete/stream`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rel_paths: relPaths }),
    },
  );

  if (!response.ok || !response.body) {
    const detail = await response.text();
    handlers.onError?.(
      "BATCH_DELETE_FAILED",
      detail || "Batch delete request failed",
    );
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const raw = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);

      let event = "message";
      let data = "";
      for (const line of raw.split("\n")) {
        if (line.startsWith("event:")) {
          event = line.replace("event:", "").trim();
        } else if (line.startsWith("data:")) {
          data += line.replace("data:", "").trim();
        }
      }

      if (data) {
        try {
          const payload = JSON.parse(data);
          if (event === "start") {
            handlers.onStart?.(payload.total_files ?? 0);
          } else if (event === "file") {
            handlers.onFile?.({
              relPath: payload.rel_path ?? "",
              status: payload.status ?? "processing",
              phase: payload.phase,
              index: payload.index,
              total: payload.total,
            });
          } else if (event === "complete") {
            handlers.onComplete?.({
              deletedCount: payload.deleted_count ?? 0,
              failedCount: payload.failed_count ?? 0,
              results: (payload.results ?? []).map((r: any) => ({
                relPath: r.rel_path,
                success: r.success,
                removedChunks: r.removed_chunks,
                error: r.error,
              })),
            });
          } else if (event === "error") {
            handlers.onError?.(
              payload.code ?? "BATCH_DELETE_ERROR",
              payload.message ?? "Batch delete failed",
            );
          }
        } catch (e) {
          console.error("[batch-delete] Parse error:", e);
        }
      }
      boundary = buffer.indexOf("\n\n");
    }
  }
}

export async function fetchModels(
  apiKey?: string,
  baseUrl?: string,
  provider?: string,
): Promise<string[]> {
  const data = await fetchJson<any>("/api/settings/models", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      api_key: apiKey ?? "",
      base_url: baseUrl ?? "",
      provider: provider ?? "",
    }),
  });
  return data.models ?? [];
}

// =============================================================================
// Chat Session API
// =============================================================================

import type { ChatSession } from "../types";

interface ChatSessionWithMessages extends ChatSession {
  messages: ChatMessage[];
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
  };
}

function mapChatSession(item: any): ChatSession {
  return {
    id: item.id,
    title: item.title,
    lastActive: item.lastActive,
    messageCount: item.messageCount ?? 0,
    preview: item.preview ?? "",
  };
}

function mapChatSessionWithMessages(item: any): ChatSessionWithMessages {
  return {
    ...mapChatSession(item),
    messages: (item.messages ?? []).map(mapChatMessage),
  };
}

export async function fetchChatSessions(
  projectId: string,
): Promise<ChatSession[]> {
  const data = await fetchJson<any[]>(`/api/projects/${projectId}/chats`);
  return data.map(mapChatSession);
}

export async function createChatSession(
  projectId: string,
  title: string = "New Chat",
): Promise<ChatSession> {
  const data = await fetchJson<any>(`/api/projects/${projectId}/chats`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  return mapChatSession(data);
}

export async function fetchChatSession(
  projectId: string,
  sessionId: string,
): Promise<ChatSessionWithMessages> {
  const data = await fetchJson<any>(
    `/api/projects/${projectId}/chats/${sessionId}`,
  );
  return mapChatSessionWithMessages(data);
}

export async function updateChatSession(
  projectId: string,
  sessionId: string,
  updates: { title?: string; messages?: ChatMessage[] },
): Promise<ChatSessionWithMessages> {
  const data = await fetchJson<any>(
    `/api/projects/${projectId}/chats/${sessionId}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updates),
    },
  );
  return mapChatSessionWithMessages(data);
}

export async function deleteChatSession(
  projectId: string,
  sessionId: string,
): Promise<void> {
  await fetchJson(`/api/projects/${projectId}/chats/${sessionId}`, {
    method: "DELETE",
  });
}

export async function addChatMessage(
  projectId: string,
  sessionId: string,
  message: ChatMessage,
): Promise<ChatSessionWithMessages> {
  const data = await fetchJson<any>(
    `/api/projects/${projectId}/chats/${sessionId}/messages`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    },
  );
  return mapChatSessionWithMessages(data);
}

export async function updateChatMessage(
  projectId: string,
  sessionId: string,
  messageId: string,
  updates: Partial<ChatMessage>,
): Promise<ChatSessionWithMessages> {
  const data = await fetchJson<any>(
    `/api/projects/${projectId}/chats/${sessionId}/messages`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message_id: messageId, updates }),
    },
  );
  return mapChatSessionWithMessages(data);
}

// =============================================================================
// Crawler API
// =============================================================================

import type {
  CrawlerAuthType,
  CrawlerConfig,
  CrawlerEngineAuthProfile,
  CrawlerSearchQuery,
  CrawlerSearchResult,
} from "../types";

function mapCrawlerAuthProfile(item: any): CrawlerEngineAuthProfile {
  return {
    authType: (item?.auth_type ?? "none") as CrawlerAuthType,
    hasSecret: item?.has_secret ?? false,
    maskedSecret: item?.masked_secret ?? null,
    headerNames: Array.isArray(item?.header_names) ? item.header_names : [],
    updatedAt:
      typeof item?.updated_at === "number" ? item.updated_at : null,
  };
}

export async function fetchCrawlerAuthConfig(): Promise<{
  engines: Record<string, CrawlerEngineAuthProfile>;
  authTypes: CrawlerAuthType[];
}> {
  const data = await fetchJson<any>("/api/settings/crawler-auth");
  const rawEngines = data?.engines ?? {};
  const engines: Record<string, CrawlerEngineAuthProfile> = {};
  Object.keys(rawEngines).forEach((engine) => {
    engines[engine] = mapCrawlerAuthProfile(rawEngines[engine]);
  });
  const authTypes = Array.isArray(data?.auth_types)
    ? (data.auth_types as CrawlerAuthType[])
    : ([
        "none",
        "cookie_header",
        "bearer",
        "api_key",
        "custom_headers",
      ] as CrawlerAuthType[]);
  return { engines, authTypes };
}

export async function saveCrawlerEngineAuth(
  engine: string,
  authType: CrawlerAuthType,
  secret?: string,
): Promise<{ success: boolean; engine: string; profile: CrawlerEngineAuthProfile }> {
  const payload: Record<string, any> = {
    engine,
    auth_type: authType,
  };
  if (typeof secret === "string") {
    payload.secret = secret;
  }

  const data = await fetchJson<any>("/api/settings/crawler-auth", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  return {
    success: data?.success ?? false,
    engine: data?.engine ?? engine,
    profile: mapCrawlerAuthProfile(data?.profile ?? {}),
  };
}

export async function deleteCrawlerEngineAuth(
  engine: string,
): Promise<{ success: boolean; engine: string }> {
  const data = await fetchJson<any>(
    `/api/settings/crawler-auth?engine=${encodeURIComponent(engine)}`,
    {
      method: "DELETE",
    },
  );
  return {
    success: data?.success ?? false,
    engine: data?.engine ?? engine,
  };
}

export async function fetchCrawlerEngines(): Promise<{
  engines: string[];
  enabled: string[];
}> {
  const data = await fetchJson<{
    engines: string[];
    enabled: string[];
  }>("/api/crawler/engines");
  return data;
}

export async function fetchCrawlerConfig(): Promise<CrawlerConfig> {
  const data = await fetchJson<CrawlerConfig>("/api/crawler/config");
  return data;
}

export async function updateCrawlerConfig(
  config: CrawlerConfig,
): Promise<CrawlerConfig> {
  const data = await fetchJson<CrawlerConfig>("/api/crawler/config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  return data;
}

export async function searchPapers(
  query: CrawlerSearchQuery,
): Promise<CrawlerSearchResult[]> {
  const data = await fetchJson<CrawlerSearchResult[]>("/api/crawler/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(query),
  });
  return data;
}

export async function downloadPapersQueueStream(
  results: CrawlerSearchResult[],
  overwrite: boolean = false,
): Promise<{ jobIds: string[]; status: string; count: number }> {
  const response = await fetch(
    `${API_BASE}/api/crawler/batch-download/stream`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ results, overwrite }),
    },
  );

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Download request failed");
  }

  const data = await response.json();
  return {
    jobIds: data.job_ids ?? [],
    status: data.status ?? "queued",
    count: data.count ?? 0,
  };
}

export async function testCrawlerEngine(
  engine: string,
): Promise<{ success: boolean; error?: string }> {
  try {
    const response = await fetch(
      `${API_BASE}/api/crawler/engines/${encodeURIComponent(engine)}/test`,
      {
        method: "POST",
      },
    );

    if (response.ok) {
      return { success: true };
    } else {
      const detail = await response.text();
      return { success: false, error: detail || "Connection failed" };
    }
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Unknown error",
    };
  }
}

export async function fetchCrawlerStats(): Promise<{
  totalSearches: number;
  totalDownloads: number;
  failedDownloads: number;
  perEngineStats: Record<
    string,
    { searches: number; downloads: number; failures: number }
  >;
  lastUpdated: number | null;
}> {
  const data = await fetchJson<{
    total_searches: number;
    total_downloads: number;
    failed_downloads: number;
    per_engine_stats: Record<
      string,
      { searches: number; downloads: number; failures: number }
    >;
    last_updated: number | null;
  }>("/api/crawler/stats");
  return {
    totalSearches: data.total_searches ?? 0,
    totalDownloads: data.total_downloads ?? 0,
    failedDownloads: data.failed_downloads ?? 0,
    perEngineStats: data.per_engine_stats ?? {},
    lastUpdated: data.last_updated ?? null,
  };
}

export interface FetchMetadataRequest {
  url: string;
  arxiv_id?: string;
  doi?: string;
}

export interface FetchMetadataResponse {
  title?: string;
  authors?: string[];
  year?: number;
  source: string;
  pdf_url?: string;
  is_academic: boolean;
}

export async function fetchMetadata(
  req: FetchMetadataRequest,
): Promise<FetchMetadataResponse> {
  const data = await fetchJson<FetchMetadataResponse>(
    "/api/crawler/fetch-metadata",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    },
  );
  return data;
}

// =============================================================================
// OCR API
// =============================================================================

export async function fetchOcrSettings(): Promise<OcrSettingsResponse> {
  return await fetchJson<OcrSettingsResponse>(`/api/settings/ocr?t=${Date.now()}`);
}

export async function saveOcrSettings(
  config: OcrConfig,
): Promise<{ success: boolean; config: OcrConfig }> {
  return await fetchJson<{ success: boolean; config: OcrConfig }>(
    "/api/settings/ocr",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    },
  );
}

export async function downloadOcrModel(
  model: string,
): Promise<{ success: boolean; message: string }> {
  return await fetchJson<{ success: boolean; message: string }>(
    "/api/settings/ocr/download",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model }),
    },
  );
}

export async function downloadOcrModelStatus(
  model: string,
): Promise<{ progress: number | null; state: string }> {
  return await fetchJson<{ progress: number | null; state: string }>(
    `/api/settings/ocr/download/status?model=${encodeURIComponent(model)}`,
  );
}

export async function deleteOcrModel(
  model: string,
): Promise<{ success: boolean; message: string }> {
  return await fetchJson<{ success: boolean; message: string }>(
    `/api/settings/ocr/models/${encodeURIComponent(model)}`,
    {
      method: "DELETE",
    },
  );
}

export async function pauseOcrDownload(
  model: string,
): Promise<{ success: boolean; message: string }> {
  return await fetchJson<{ success: boolean; message: string }>(
    "/api/settings/ocr/download/pause",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model }),
    },
  );
}

export async function resumeOcrDownload(
  model: string,
): Promise<{ success: boolean; message: string }> {
  return await fetchJson<{ success: boolean; message: string }>(
    "/api/settings/ocr/download/resume",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model }),
    },
  );
}

export async function cancelOcrDownload(
  model: string,
): Promise<{ success: boolean; message: string }> {
  return await fetchJson<{ success: boolean; message: string }>(
    "/api/settings/ocr/download/cancel",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model }),
    },
  );
}

