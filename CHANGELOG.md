# Changelog

All notable changes to this project will be documented in this file.

## 1.2.0

### Added
- Zoom hotkey functionality for PDF viewer
- Confirm extract metadata modal with user confirmation
- Global queue component with projectile eject animation
- Copy with in-text citation feature
- GB/T 7714-2015 citation format support
- Works cited modal for managing citations

### Changed
- Reorganized file metadata modal for better UX
- Unified styles across reference bank and selector modal
- Adjusted bankfile selector modal and component layouts
- Improved metadata extraction accuracy
- Various UI style improvements and polish

### Fixed
- Build issues for Electron packaging (missing dependencies)
- Layout overflow issue of preview-container
- DOCX reload bug with LRU cache implementation
- Queue state consistency across page refreshes
- Various layout fixes and responsiveness issues

## 1.1.0

### Added
- Automatic update support via electron-updater for seamless app updates.
- Heuristic PDF metadata extraction for improved document indexing.
- Bibliography modal with enhanced citation display.
- Common citation rules for standardized reference formatting.
- Enhanced markdown rendering:
  - Syntax highlighting for code blocks with language detection.
  - Copy button for code blocks.
  - Mermaid diagram support (flowcharts, sequence diagrams, etc.).
  - External link detection with visual indicator and secure attributes.
  - Image rendering with lazy loading and captions.
  - Responsive table styling with horizontal scroll.

### Fixed
- Various bug fixes and stability improvements.

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
