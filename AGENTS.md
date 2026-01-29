# AGENTS.md

This file provides guidance for agentic coding assistants working in the ReferenceMiner repository.

## Build, Lint, and Test Commands

### Backend (Python)

**IMPORTANT**: All Python commands must use `uv run` prefix. This project uses `uv` for dependency management.

```bash
# Install dependencies
uv sync

# Run all tests
uv runud python -m unittest discover tests

# Run a single test file
uv run python -m unittest tests.test_metadata_extraction

# Run a specific test method
uv run python -m unittest tests.test_metadata_extraction.TestMetadataExtraction.test_extract_pdf_bibliography_basic

# Ingest documents
uv run python referenceminer.py ingest

# Start server (for manual testing only - do not run in automated commands)
uv run python -m uvicorn refminer.server:app --reload --app-dir src --port 8000

# Type checking (if mypy is added)
uv run python -m mypy src/refminer
```

### Frontend (Vue 3 + TypeScript)

```bash
cd frontend

# Install dependencies
npm install

# Development server
npm run dev

# Type check and production build
npm run build

# Type check only
npx vue-tsc --noEmit

# Preview production build
npm run preview
```

## Code Style Guidelines

### Python

**Imports:**
- Always start with `from __future__ import annotations` at the top of every file
- Group imports: standard library, third-party, local modules
- Use absolute imports for local modules: `from refminer.module import function`
- Avoid wildcard imports (`from module import *`)

**Type Hints:**
- Use type hints for all function signatures and class attributes
- Use `| None` for optional types (Python 3.10+ syntax)
- Use `TYPE` type variable for forward references with `if TYPE_CHECKING:`
- Use `dataclass` for data structures with `@dataclass` decorator

**Naming Conventions:**
- Functions/variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private members: `_leading_underscore`
- Module-level constants: `UPPER_CASE` (e.g., `DOI_RE`, `YEAR_RE`)

**Error Handling:**
- Use `try/except` with specific exception types
- Log errors using `logging` module: `logger.error("message", exc_info=True)`
- Return `None` or raise appropriate exceptions for error conditions
- Use `Optional[T]` return types for functions that may fail gracefully

**Logging:**
- Use module-level logger: `logger = logging.getLogger(__name__)`
- Log at appropriate levels: `debug`, `info`, `warning`, `error`, `critical`
- Include context in log messages, not just exception details

**Code Structure:**
- Keep functions focused and under 50 lines when possible
- Use docstrings for functions with non-trivial logic
- Prefer dataclasses over dictionaries for structured data
- Use `Path` from pathlib for file operations

**Critical Safety Rule:**
- NEVER delete or move reference files from `references/` folder
- Only delete metadata/index files: `chunks.jsonl`, `bm25.pkl`, `vectors.faiss`, `manifest.json`
- This is a fundamental safety principle for user's research materials

### Vue 3 + TypeScript

**Component Structure:**
- Use `<script setup lang="ts">` syntax for all components
- Use `defineProps<>` and `defineEmits<>` for type-safe props and emits
- Keep component files focused; extract complex logic to composables

**Imports:**
- Group imports: Vue, external libraries, local modules
- Use type-only imports when possible: `import type { Interface } from './types'`

**Type Safety:**
- Use TypeScript interfaces for all props and emits
- Use `withDefaults()` for default prop values
- Avoid `any`; use `unknown` or proper types
- Use `ref<>` and `reactive<>` with explicit types

**Naming Conventions:**
- Components: `PascalCase.vue` (e.g., `BaseModal.vue`, `ChatWindow.vue`)
- Functions/variables: `camelCase`
- Constants: `UPPER_SNAKE_CASE`
- Composables: `useCamelCase` (e.g., `useQueue`, `usePdfSettings`)

**Error Handling:**
- Use try/catch for async operations
- Provide user-friendly error messages
- Use error boundaries for component-level error handling

**Modal Pattern:**
- Always use `BaseModal.vue` as the base for modals
- Use `v-model` for visibility control (never `v-if` on modal component)
- Keep modals mounted to allow transitions to work properly
- Sizes: `small`, `medium`, `large`, `xlarge`, `fullscreen`

**Styling:**
- Use scoped styles in single-file components
- Use CSS variables for theming: `var(--color-white)`, `var(--text-primary)`
- Follow existing design tokens in the codebase
- Avoid inline styles; prefer CSS classes

**API Calls:**
- Use the centralized `client.ts` for all API calls
- Use type assertions for responses: `as Promise<Type>`
- Handle errors with try/catch and show user feedback

## Testing

**Python Tests:**
- Use `unittest` framework
- Place tests in `tests/` directory
- Name test files: `test_<module_name>.py`
- Name test classes: `Test<ClassName>`
- Name test methods: `test_<function_name>_<scenario>`

**Test Isolation:**
- Each test should be independent
- Use `setUp()` and `tearDown()` for test fixtures
- Mock external dependencies (API calls, file I/O)

## Architecture Patterns

**Backend:**
- FastAPI with modular route handlers in `src/refminer/server/routes/`
- Use Pydantic models for request/response validation
- SSE streaming for long-running operations (Q&A, file upload)
- Global state managed in `src/refminer/server/globals.py`

**Frontend:**
- Vue Router for navigation
- Composition API for reusable logic
- Centralized API client in `frontend/src/api/client.ts`
- Type definitions in `frontend/src/types.ts`

**Data Flow:**
- Ingest → Index → Retrieve → Analyze → LLM
- EvidenceChunk is the core data structure
- Citations use `[C#]` format in LLM responses
