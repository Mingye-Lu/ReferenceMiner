# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ReferenceMiner is a local-first research assistant that provides evidence-grounded analysis over user-provided reference documents (PDFs, DOCX, images, text files, spreadsheets). All claims are traceable to specific files, pages, or sections. The system operates on a strict principle: if it's not in `references/`, it doesn't exist.

**Reference Bank Model**: All documents are stored in a single `references/` folder with one global index. Projects are lightweight metadata objects that select subsets of files from this bank. Files can belong to multiple projects.

## Common Commands

### Backend (Python)

```bash
# Install dependencies (from project root, with venv activated)
pip install -r requirements.txt

# Ingest documents from references/ folder
python referenceminer.py ingest

# Ingest without vector embeddings (faster, BM25-only)
python referenceminer.py ingest --no-vectors

# List indexed reference files
python referenceminer.py list

# Ask a question via CLI
python referenceminer.py ask "Your question here"

# Start the API server
python -m uvicorn refminer.server:app --reload --app-dir src --port 8000
```

### Frontend (Vue 3 + Vite)

```bash
cd frontend
npm install
npm run dev      # Development server at http://localhost:5173
npm run build    # Type-check and production build
```

### Environment Variables

Backend (`.env` in project root):
- `DEEPSEEK_API_KEY` - Required for LLM-powered answers (falls back to local synthesis if absent)
- `DEEPSEEK_BASE_URL` - Default: `https://api.deepseek.com`
- `DEEPSEEK_MODEL` - Default: `deepseek-chat`

Frontend (`frontend/.env`):
- `VITE_API_URL` - Backend URL, default: `http://localhost:8000`

## Architecture

### Data Flow Pipeline

1. **Ingest** (`src/refminer/ingest/`) - Scans `references/`, extracts text/metadata from PDFs/DOCX/images, builds manifest
2. **Index** (`src/refminer/index/`) - Chunks text, builds BM25 keyword index and optional FAISS vector index
3. **Retrieve** (`src/refminer/retrieve/`) - Hybrid search using reciprocal rank fusion of BM25 + vector results
4. **Analyze** (`src/refminer/analyze/workflow.py`) - Derives scope, extracts keywords (jieba), synthesizes evidence
5. **LLM** (`src/refminer/llm/deepseek.py`) - Generates structured answers with citations via DeepSeek API

### Backend Modules

- **`ingest/`** - Document extraction pipeline with format-specific extractors
- **`index/`** - BM25 + FAISS indexing with hybrid retrieval
- **`retrieve/`** - Search interface with project-scoped file filtering
- **`analyze/`** - Question decomposition and evidence synthesis
- **`llm/`** - DeepSeek API client with streaming support
- **`projects/`** - Project management (models.py, manager.py) for CRUD and file selection
- **`render/`** - Answer formatting for CLI output
- **`utils/`** - Path helpers, hashing, text processing

### Index Storage

All indexes are stored in `.index/`:
- `manifest.json` - File metadata (paths, types, titles, abstracts, sha256)
- `chunks.jsonl` - Text chunks with page/section info
- `bm25.pkl` - BM25 keyword index
- `vectors.faiss` - FAISS vector embeddings (optional)
- `registry.json` - Hash-to-path mapping for duplicate detection
- `projects.json` - Project metadata and file selections

### API Endpoints

**Project Management:**
- `GET /api/projects` - List all projects
- `POST /api/projects` - Create project
- `GET /api/projects/{project_id}` - Get project details
- `DELETE /api/projects/{project_id}` - Delete project
- `POST /api/projects/{project_id}/activate` - Mark as active

**Project Knowledge:**
- `GET /api/projects/{project_id}/manifest` - Files in project
- `GET /api/projects/{project_id}/files` - Selected files
- `POST /api/projects/{project_id}/files/select` - Add files to project
- `POST /api/projects/{project_id}/files/remove` - Remove files from project
- `GET /api/projects/{project_id}/status` - Index statistics
- `POST /api/projects/{project_id}/ask/stream` - Streaming Q&A (SSE)
- `POST /api/projects/{project_id}/summarize` - Generate chat title via LLM

**File Management:**
- `POST /api/projects/{project_id}/upload/stream` - Upload with SSE progress
- `GET /api/projects/{project_id}/files/check-duplicate` - Check if file exists
- `DELETE /api/projects/{project_id}/files/{rel_path}` - Delete file
- `POST /api/bank/upload/stream` - Upload to global bank
- `GET /api/bank/manifest` - Global file list

### Frontend Components

- `App.vue` - Router entry point
- `ProjectHub.vue` - Project creation and selection hub
- `Cockpit.vue` - Main 3-panel research interface (SidePanel | ChatWindow | RightDrawer)
- `ChatWindow.vue` - Message history and input
- `SidePanel.vue` - Reference file list and selection
- `RightDrawer.vue` - Evidence/citation details and notebook
- `MessageItem.vue` - Individual message rendering with markdown
- `FileUploader.vue` - File upload UI
- `FilePreviewModal.vue` - Document preview
- `ProjectCard.vue` - Project display card
- `ConfirmationModal.vue` / `AlertModal.vue` - Dialog modals

**Routing:** `/` (ProjectHub) and `/project/:id` (Cockpit)

## Key Patterns

- **EvidenceChunk** dataclass (in `analyze/workflow.py`) is the core data structure passed between retrieval and analysis
- All document extractors (`extract_pdf.py`, `extract_docx.py`, `extract_image.py`) return a consistent `ExtractedDocument` structure
- Citations use `[C#]` format in LLM responses, parsed back to source references
- The server auto-ingests on first request if indexes are missing
- **Project scoping**: Global index with per-project file filtering at query time
- **SSE streaming**: Both Q&A responses and file uploads use Server-Sent Events for responsive UI
- **Graceful degradation**: LLM is optional; falls back to local synthesis if API key missing
