# ReferenceMiner API Endpoints

This document provides a comprehensive reference for all API endpoints in ReferenceMiner.

## Table of Contents

- [Authentication & Middleware](#authentication--middleware)
- [Project Management](#project-management)
- [Settings & Configuration](#settings--configuration)
- [Chat Sessions](#chat-sessions)
- [File Management](#file-management)
- [File Upload & Deletion](#file-upload--deletion)
- [Knowledge & Analysis](#knowledge--analysis)
- [Data Structures](#data-structures)
- [Error Handling](#error-handling)

---

## Authentication & Middleware

### CORS Configuration

- **Dev mode:** Allows `http://localhost:5173` and `http://127.0.0.1:5173`
- **Bundled mode:** Allows all origins (`*`)
- CORS headers enabled for credentials and all methods

### Static File Serving

| Path                | Description                                                        |
| ------------------- | ------------------------------------------------------------------ |
| `/files`            | Static mount to serve reference files from `references/` directory |
| `/assets`           | Frontend assets (when available)                                   |
| `/`                 | SPA root (serves `index.html`)                                     |
| `/{full_path:path}` | SPA fallback routing                                               |

---

## Project Management

### List Projects

```
GET /api/projects
```

**Response:** `List[Project]`

---

### Create Project

```
POST /api/projects
```

**Request Body:**

```json
{
  "name": "string",
  "description": "string (optional)"
}
```

**Response:** `Project` object

---

### Get Project

```
GET /api/projects/{project_id}
```

**Response:** `Project` object

**Status Codes:** `200`, `404` (Project not found)

---

### Delete Project

```
DELETE /api/projects/{project_id}
```

**Response:**

```json
{ "success": true }
```

---

### Activate Project

```
POST /api/projects/{project_id}/activate
```

Updates the `last_active` timestamp.

**Response:**

```json
{ "success": true }
```

---

## Settings & Configuration

### Get Settings

```
GET /api/settings
```

**Response:**

```json
{
  "active_provider": "deepseek|openai|gemini|anthropic|custom",
  "provider_keys": {
    "[provider_name]": {
      "has_key": true,
      "masked_key": "sk-****1234"
    }
  },
  "provider_settings": {
    "[provider_name]": {
      "base_url": "https://api.deepseek.com",
      "model": "deepseek-chat"
    }
  },
  "has_api_key": true,
  "masked_api_key": "sk-****1234",
  "base_url": "https://api.deepseek.com",
  "model": "deepseek-chat",
  "citation_copy_format": "apa"
}
```

---

### Get Version

```
GET /api/settings/version
```

**Response:**

```json
{
  "version": "1.0.0"
}
```

---

### Check for Updates

```
GET /api/settings/update-check
```

Checks GitHub for a newer version.

**Response:**

```json
{
  "repo": "owner/repo",
  "current": { "version": "1.0.0" },
  "latest": {
    "version": "1.1.0",
    "url": "https://github.com/...",
    "source": "release"
  },
  "is_update_available": true,
  "checked_at": 1234567890000,
  "error": null
}
```

---

### Save API Key

```
POST /api/settings/api-key
```

**Request Body:**

```json
{
  "api_key": "string",
  "provider": "deepseek|openai|gemini|anthropic|custom (optional)"
}
```

**Response:**

```json
{
  "success": true,
  "has_api_key": true,
  "masked_api_key": "sk-****1234",
  "provider": "deepseek"
}
```

**Status Codes:** `200`, `400` (Empty key or unsupported provider)

---

### Delete API Key

```
DELETE /api/settings/api-key
```

**Query Parameters:** `provider` (optional, defaults to active provider)

**Response:**

```json
{
  "success": true,
  "has_api_key": false,
  "provider": "deepseek"
}
```

---

### Validate API Key

```
POST /api/settings/validate
```

**Request Body:**

```json
{
  "api_key": "string (optional)",
  "base_url": "string (optional)",
  "model": "string (optional)",
  "provider": "string (optional)"
}
```

**Response:**

```json
{
  "valid": true,
  "error": "string (present if validation failed)"
}
```

---

### Fetch Available Models

```
POST /api/settings/models
```

**Request Body:**

```json
{
  "api_key": "string (optional)",
  "base_url": "string (optional)",
  "provider": "string (optional)"
}
```

**Response:**

```json
{
  "models": ["model_id_1", "model_id_2"],
  "provider": "deepseek"
}
```

**Status Codes:** `200`, `400` (No API key or fetch failed)

---

### Save LLM Configuration

```
POST /api/settings/llm
```

**Request Body:**

```json
{
  "base_url": "string",
  "model": "string",
  "provider": "string (optional)"
}
```

**Response:**

```json
{
  "success": true,
  "base_url": "https://api.deepseek.com",
  "model": "deepseek-chat",
  "active_provider": "deepseek"
}
```

**Status Codes:** `200`, `400` (Invalid URL, empty model, or unsupported provider)

---

### Reset All Data

```
POST /api/settings/reset
```

Clears all indexes, manifest, and chat sessions. **Preserves reference files.**

**Response:**

```json
{
  "success": true,
  "message": "All metadata, indexes, and chat sessions cleared. Reference files preserved."
}
```

---

### Save Citation Format

```
POST /api/settings/citation-format
```

Save the preferred citation format for copying AI responses.

**Request Body:**

```json
{
  "format": "apa|mla|chicago|gbt7714|numeric"
}
```

**Response:**

```json
{
  "success": true,
  "citation_copy_format": "apa"
}
```

---

## Chat Sessions

### List Chat Sessions

```
GET /api/projects/{project_id}/chats
```

**Response:** `List[ChatSession]` (without messages)

---

### Create Chat Session

```
POST /api/projects/{project_id}/chats
```

**Request Body:**

```json
{
  "title": "New Chat"
}
```

**Response:** `ChatSession` object

---

### Get Chat Session

```
GET /api/projects/{project_id}/chats/{session_id}
```

**Response:** `ChatSession` object with full `messages` array

**Status Codes:** `200`, `404`

---

### Update Chat Session

```
PUT /api/projects/{project_id}/chats/{session_id}
```

**Request Body:**

```json
{
  "title": "string (optional)",
  "messages": "list (optional)"
}
```

**Response:** `ChatSession` object

---

### Delete Chat Session

```
DELETE /api/projects/{project_id}/chats/{session_id}
```

**Response:**

```json
{ "success": true }
```

---

### Add Message to Chat

```
POST /api/projects/{project_id}/chats/{session_id}/messages
```

**Request Body:**

```json
{
  "message": {
    "id": "string",
    "role": "user|ai",
    "content": "string",
    "timestamp": 1234567890000,
    "timeline": [],
    "sources": [],
    "keywords": []
  }
}
```

**Response:** `ChatSession` object

---

### Update Message in Chat

```
PATCH /api/projects/{project_id}/chats/{session_id}/messages
```

**Request Body:**

```json
{
  "message_id": "string",
  "updates": {
    "content": "updated content"
  }
}
```

**Response:** `ChatSession` object

---

## File Management

### Get Project Manifest

```
GET /api/projects/{project_id}/manifest
```

Returns file manifest filtered by project's selected files.

**Response:** `List[ManifestEntry]`

---

### Get Bank Manifest

```
GET /api/bank/manifest
```

Returns all files in global reference bank.

**Response:** `List[ManifestEntry]`

---

### Get Bank File Statistics

```
GET /api/bank/files/stats
```

**Response:**

```json
{
  "file_path.pdf": {
    "usage_count": 5,
    "last_used": 1234567890.0
  }
}
```

---

### Reprocess Reference Bank (Streaming)

```
POST /api/bank/reprocess/stream
```

Rebuilds all indexes from scratch by re-extracting and re-indexing all files in the `references/` folder.

**Response:** `text/event-stream` (SSE)

**Events:**

```
event: progress
data: {"phase": "resetting|scanning|indexing", "percent": 10}

event: start
data: {"total_files": 25}

event: file
data: {"rel_path": "paper.pdf", "status": "processing|complete", "phase": "extracting", "index": 1, "total": 25}

event: complete
data: {"total_files": 25, "total_chunks": 500}

event: error
data: {"code": "REPROCESS_ERROR", "message": "..."}
```

---

### Reprocess Single File (Streaming)

```
POST /api/bank/files/{rel_path}/reprocess/stream
```

Re-extracts and re-indexes a single file.

**Response:** `text/event-stream` (SSE)

**Events:**

```
event: file
data: {"rel_path": "paper.pdf", "status": "processing", "phase": "extracting"}

event: complete
data: {"manifest_entry": {...}}

event: error
data: {"code": "NOT_FOUND|REPROCESS_FILE_ERROR", "message": "..."}
```

---

### Get Project Selected Files

```
GET /api/projects/{project_id}/files
```

**Response:**

```json
{ "selected_files": ["file1.pdf", "file2.docx"] }
```

---

### Add Files to Project

```
POST /api/projects/{project_id}/files/select
```

**Request Body:**

```json
{
  "rel_paths": ["file1.pdf", "file2.docx"]
}
```

**Response:**

```json
{ "selected_files": ["file1.pdf", "file2.docx"] }
```

---

### Remove Files from Project

```
POST /api/projects/{project_id}/files/remove
```

**Request Body:**

```json
{
  "rel_paths": ["file1.pdf"]
}
```

**Response:**

```json
{ "selected_files": ["file2.docx"] }
```

---

## File Upload & Deletion

### Upload File to Project (Streaming)

```
POST /api/projects/{project_id}/upload/stream
```

**Content-Type:** `multipart/form-data`

**Form Data:**

- `file` - File to upload (max 100MB)
- `replace_existing` - Boolean, replace if duplicate found

**Response:** `text/event-stream` (SSE)

**Events:**

```
event: progress
data: {"phase": "uploading|hashing|checking_duplicate|storing|extracting|indexing", "percent": 50}

event: duplicate
data: {"sha256": "abc123", "existing_path": "existing.pdf"}

event: complete
data: {"rel_path": "new.pdf", "sha256": "abc123", "status": "processed", "manifest_entry": {...}}

event: error
data: {"code": "UNSUPPORTED_TYPE|FILE_TOO_LARGE|EXTRACTION_ERROR|UPLOAD_ERROR", "message": "..."}
```

---

### Upload File to Bank (Streaming)

```
POST /api/bank/upload/stream
```

Same as project upload but adds file to global bank without project selection.

---

### Check Duplicate

```
GET /api/projects/{project_id}/files/check-duplicate?sha256=abc123
```

**Response:**

```json
{
  "is_duplicate": true,
  "existing_path": "existing.pdf",
  "existing_entry": {...}
}
```

---

### Delete File (Streaming)

```
POST /api/projects/{project_id}/files/{rel_path:path}/delete/stream
```

Supports subdirectories (e.g., `subdir/file.pdf`).

**Response:** `text/event-stream` (SSE)

**Events:**

```
event: progress
data: {"phase": "deleting", "percent": 50}

event: complete
data: {"success": true, "removed_chunks": 42, "rel_path": "file.pdf"}

event: error
data: {"code": "NOT_FOUND", "message": "..."}
```

---

### Batch Delete Files

```
POST /api/projects/{project_id}/files/batch-delete
```

**Request Body:**

```json
{
  "rel_paths": ["file1.pdf", "file2.pdf"]
}
```

**Response:**

```json
{
  "success": true,
  "deleted_count": 2,
  "failed_count": 0,
  "total_chunks_removed": 84,
  "results": [
    { "rel_path": "file1.pdf", "success": true, "removed_chunks": 42 },
    { "rel_path": "file2.pdf", "success": true, "removed_chunks": 42 }
  ]
}
```

---

### Get File Highlights

```
GET /api/files/{rel_path}/highlights
```

Returns bounding boxes for all chunks in a file (PDF only). Used for rendering text highlights in the PDF viewer.

**Response:**

```json
{
  "chunk_id_1": [{ "page": 1, "x0": 72, "y0": 100, "x1": 540, "y1": 120 }],
  "chunk_id_2": [
    { "page": 1, "x0": 72, "y0": 130, "x1": 540, "y1": 150 },
    { "page": 2, "x0": 72, "y0": 50, "x1": 540, "y1": 70 }
  ]
}
```

---

## Knowledge & Analysis

### Get Index Status

```
GET /api/projects/{project_id}/status
```

**Response:**

```json
{
  "indexed": true,
  "total_files": 10,
  "total_chunks": 500
}
```

---

### Ask Question (Non-Streaming)

```
POST /api/projects/{project_id}/ask
```

**Request Body:**

```json
{
  "question": "What is the main thesis?",
  "context": ["specific_file.pdf"],
  "use_notes": false,
  "notes": [],
  "history": [
    { "role": "user", "content": "Previous question" },
    { "role": "assistant", "content": "Previous answer" }
  ]
}
```

**Response:**

```json
{
  "question": "What is the main thesis?",
  "scope": ["file1.pdf", "file2.pdf"],
  "evidence": [
    {
      "chunk_id": "abc123",
      "path": "file1.pdf",
      "page": 5,
      "section": "Introduction",
      "text": "The main thesis is...",
      "score": 0.95
    }
  ],
  "answer": [
    {
      "heading": "Main Thesis",
      "body": "The document argues that...",
      "citations": ["[C1]", "[C2]"]
    }
  ],
  "answer_markdown": "## Main Thesis\n\nThe document argues...",
  "crosscheck": "Evidence supports the claims."
}
```

**Status Codes:** `200`, `400` (Indexes not found)

---

### Ask Question (Streaming)

```
POST /api/projects/{project_id}/ask/stream
```

**Request Body:** Same as non-streaming `/ask`

**Response:** `text/event-stream` (SSE)

**Events:**

```
event: step
data: {"step": "research|analyze|answer|done", "title": "Searching documents...", "timestamp": 1234567890.0}

event: evidence
data: [{"chunk_id": "abc123", "path": "file.pdf", "text": "...", "score": 0.95}]

event: answer_delta
data: {"delta": "The document "}

event: error
data: {"code": "LACK_INGEST|CONTENT_FILTERED|LLM_ERROR", "message": "..."}

event: done
data: {}
```

---

### Generate Chat Title (Streaming)

```
POST /api/projects/{project_id}/summarize
```

**Request Body:**

```json
{
  "messages": [
    { "role": "user", "content": "What is machine learning?" },
    { "role": "assistant", "content": "Machine learning is..." }
  ]
}
```

**Response:** `text/event-stream` (SSE)

**Events:**

```
event: title_delta
data: {"delta": "M"}

event: title_done
data: {"title": "Machine Learning Overview"}
```

---

## Queue Management

### List Queue Jobs

```
GET /api/queue/jobs
```

**Query Parameters:**

- `scope` (optional) - Filter by scope
- `project_id` (optional) - Filter by project
- `include_completed` (optional, default: false) - Include completed jobs
- `limit` (optional, default: 200) - Max results

**Response:** `List[QueueJob]`

---

### Get Queue Job

```
GET /api/queue/jobs/{job_id}
```

**Response:** `QueueJob` object

**Status Codes:** `200`, `404`

---

### Create Queue Job

```
POST /api/queue/jobs
```

**Request Body:**

```json
{
  "type": "upload|reprocess|delete",
  "scope": "project|bank",
  "project_id": "string (optional)",
  "name": "string",
  "rel_path": "string (optional)",
  "status": "pending|running|complete|failed (optional)",
  "phase": "string (optional)",
  "progress": 0.0
}
```

**Response:** `QueueJob` object

---

### Stream Queue Jobs

```
GET /api/queue/stream
```

**Query Parameters:**

- `scope` (optional) - Filter by scope
- `project_id` (optional) - Filter by project

**Response:** `text/event-stream` (SSE)

**Events:**

```
event: job
data: {"id": "...", "type": "upload", "status": "running", "progress": 50, ...}

event: ready
data: {"ok": true}
```

---

## Data Structures

### Project

```typescript
interface Project {
  id: string;
  name: string;
  description?: string;
  root_path: string;
  created_at: number; // epoch timestamp (seconds)
  last_active: number; // epoch timestamp (seconds)
  file_count: number;
  note_count: number;
  selected_files: string[];
}
```

### ManifestEntry

```typescript
interface ManifestEntry {
  path: string;
  rel_path: string;
  file_type: "pdf" | "docx" | "text" | "image" | "table";
  size_bytes: number;
  modified_time: number; // epoch timestamp
  sha256: string;
  title?: string;
  abstract?: string;
  page_count?: number;
}
```

### ChatSession

```typescript
interface ChatSession {
  id: string;
  title: string;
  lastActive: number; // epoch ms
  messageCount: number;
  preview: string;
  messages: ChatMessage[];
}
```

### ChatMessage

```typescript
interface ChatMessage {
  id: string;
  role: "user" | "ai";
  content: string;
  timestamp: number; // epoch ms
  timeline?: TimelineEntry[];
  sources?: EvidenceChunk[];
  keywords?: string[];
  isStreaming?: boolean;
  completedAt?: number; // epoch ms
}
```

### EvidenceChunk

```typescript
interface EvidenceChunk {
  chunk_id: string;
  path: string;
  page?: number;
  section?: string;
  text: string;
  score: number;
  bbox?: BoundingBox[];
}
```

### TimelineEntry

```typescript
interface TimelineEntry {
  phase: string;
  message: string;
  startTime: number; // epoch ms
}
```

### QueueJob

```typescript
interface QueueJob {
  id: string;
  type: "upload" | "reprocess" | "delete";
  scope: "project" | "bank";
  project_id?: string;
  name: string;
  rel_path?: string;
  status: "pending" | "running" | "complete" | "failed";
  phase?: string;
  progress: number; // 0.0 to 1.0
  created_at: number; // epoch ms
  updated_at: number; // epoch ms
  error?: string;
}
```

---

## Supported File Types

| Extension               | Type              | Code    |
| ----------------------- | ----------------- | ------- |
| `.pdf`                  | PDF Document      | `pdf`   |
| `.docx`                 | Word Document     | `docx`  |
| `.txt`, `.md`           | Text File         | `text`  |
| `.png`, `.jpg`, `.jpeg` | Image             | `image` |
| `.csv`, `.xlsx`         | Table/Spreadsheet | `table` |

---

## Error Handling

### HTTP Status Codes

| Code  | Description                                                           |
| ----- | --------------------------------------------------------------------- |
| `200` | Success                                                               |
| `400` | Bad Request - Invalid parameters, empty API key, unsupported provider |
| `404` | Not Found - Project, chat, or file not found                          |
| `409` | Conflict - Multiple files with same name (ambiguous path)             |
| `500` | Internal Server Error - Server processing failures                    |

### Streaming Error Codes

| Code               | Description                            |
| ------------------ | -------------------------------------- |
| `LACK_INGEST`      | No indexed documents available         |
| `CONTENT_FILTERED` | Content was filtered by safety systems |
| `LLM_ERROR`        | LLM API request failed                 |
| `UNSUPPORTED_TYPE` | File type not supported for upload     |
| `FILE_TOO_LARGE`   | File exceeds 100MB limit               |
| `EXTRACTION_ERROR` | Failed to extract content from file    |
| `UPLOAD_ERROR`     | General upload failure                 |

---

## SSE Format

All streaming endpoints use standard Server-Sent Events format:

```
event: [event_name]
data: {"json": "payload"}

```

Each event is separated by a blank line. Parse `data` as JSON.
