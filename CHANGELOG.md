# Changelog

All notable changes to this project will be documented in this file.

## 1.0.0

- Local-first research assistant that only uses the `references/` bank with strict, citable answers.
- Ingestion pipeline for PDFs, DOCX, text, images, and tables with manifesting, hashing, and reprocessing.
- Hybrid retrieval (BM25 + vector embeddings + reciprocal rank fusion) with project-scoped filtering.
- Evidence-grounded analysis flow with citation mapping to chunks/pages.
- FastAPI backend with SSE streaming for uploads, reprocessing, and Q&A responses.
- Projects and chat sessions with CRUD APIs and persisted history.
- PDF highlights and bounding boxes for evidence display in the UI.
- Settings and LLM provider management (DeepSeek/OpenAI/Gemini/Anthropic/custom), including key validation and model discovery.
- Vue 3 frontend with ProjectHub + Cockpit layout, file browser, PDF viewer, chat, and modal system.
- Electron desktop build pipeline and offline installer flow.
- CLI for ingest/list/ask and full REST API documentation.
