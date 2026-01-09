# ReferenceMiner

ReferenceMiner is a local-first research assistant designed to deliver deep, evidence-grounded analysis over a curated set of references you provide.

Instead of crawling the web (which introduces legal, ethical, and reproducibility issues), ReferenceMiner operates exclusively on a local `references/` folder containing PDFs, DOCX files, images, charts, and other research artifacts. Every claim it produces is traceable to a specific file, page, section, or figure.

Principle: If it is not in `references/`, it does not exist.

---

## Core Capabilities

ReferenceMiner behaves like a meticulous research assistant:

- Folder awareness
  - Knows exactly what files exist in `references/`, their types, structure, and metadata.
- Document understanding
  - Extracts titles, abstracts, sections, and full text from PDFs and DOCX files.
  - Tracks page numbers and section boundaries.
- Chart and figure interpretation
  - Uses surrounding text and captions by default (cheap and reliable).
  - Can fall back to vision-based analysis on demand.
- Hybrid retrieval
  - Combines keyword search (BM25) and semantic search (embeddings).
- Deep analytical responses
  - Breaks questions into sub-questions.
  - Synthesizes across multiple sources.
  - Identifies agreements, contradictions, and gaps.
  - Produces structured, citation-backed answers.
- Strict grounding
  - Every factual statement is backed by an explicit citation:

```
(paper1.pdf p.7, Fig.2)
(survey.docx 3.1)
```

---

## Non-Goals (By Design)

ReferenceMiner intentionally does not:
- Crawl the web
- Query external APIs for content
- Hallucinate missing sources
- Make uncited claims

This keeps the system legally safe, auditable, and suitable for academic or professional use.

---

## Project Structure

```
ReferenceMiner/
  references/
  src/
    refminer/
      analyze/
      ingest/
      index/
      render/
      retrieve/
      utils/
  .index/
    manifest.json
    chunks.jsonl
    bm25.pkl
    vectors.faiss
  frontend/
    src/
  requirements.txt
```

---

## Startup Guide

### 1) Python backend setup

Create and activate a virtual environment (optional but recommended), then install dependencies:

```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2) Configure DeepSeek (LLM)

Create a `.env` file in the project root (or export environment variables) with your DeepSeek credentials:

```
DEEPSEEK_API_KEY=your_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

If `DEEPSEEK_API_KEY` is not set, the backend will fall back to local synthesis.
### 3) Ingest references

Place your documents in `references/`, then build the manifest and indexes:

```
python referenceminer.py ingest
```

Tip: If you want to skip vector indexing, run:

```
python referenceminer.py ingest --no-vectors
```

### 4) Start the API server

Run the FastAPI backend on port 8000:

```
python -m uvicorn refminer.server:app --reload --app-dir src --port 8000
```

API endpoints:
- `GET /manifest`
- `GET /status`
- `POST /ask`

### 5) Start the Vue frontend

From the project root:

```
cd frontend
npm install
```

Create `frontend/.env` (or copy from `frontend/.env.example`) and set the API URL:

```
VITE_API_URL=http://localhost:8000
```

Run the dev server:

```
npm run dev
```

Open the UI at `http://localhost:5173`.

---

## How It Works (High Level)

1. Ingest
   - Scans `references/`, detects file types, extracts text and metadata, and builds a structured manifest.
2. Index
   - Content is chunked and indexed using BM25 and optional vector embeddings.
3. Retrieve
   - For a query, both indexes are queried and merged to identify relevant evidence.
4. Analyze
   - Decomposes the question, reads evidence, cross-checks sources, and identifies gaps.
5. Respond
   - Produces a structured answer with explicit citations and limitations.

---

## Usage (CLI)

```
python referenceminer.py list
python referenceminer.py ask "What evidence supports method X?"
```

---

## Example Queries

- "Summarize the consensus and disagreements across these papers."
- "Which figures support the claim that X improves Y?"
- "Compare the methodologies used in papers A, B, and C."
- "What assumptions are shared across all sources?"
- "What evidence contradicts hypothesis H?"

---

## Intended Use Cases

- Literature reviews
- Research validation
- Technical due diligence
- Academic writing support
- Internal knowledge audits

---

## Status

Early development. The current focus is robust ingestion, grounding, and retrieval. Multi-agent orchestration and advanced evaluation workflows may be added later.

---

> ReferenceMiner
> If it is not cited, it does not count.


