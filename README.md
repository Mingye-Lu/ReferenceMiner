# ReferenceMiner

**ReferenceMiner** is a local-first research assistant agent designed to perform **deep, evidence-grounded analysis** over a curated set of references you provide.

Instead of crawling the web (which introduces legal, ethical, and reproducibility issues), ReferenceMiner operates **exclusively on a local `references/` folder** containing PDFs, DOCX files, images, charts, and other research artifacts. Every claim it produces is traceable to a specific file, page, section, or figure.

> **Principle:** If it鈥檚 not in `references/`, it doesn鈥檛 exist.

---

## Core Capabilities

ReferenceMiner is built to behave like a meticulous research assistant:

- 馃搨 **Folder Awareness**  
  Knows exactly what files exist in `references/`, their types, structure, and metadata.

- 馃搫 **Document Understanding**  
  - Extracts titles, abstracts, sections, and full text from PDFs and DOCX files  
  - Detects and indexes figures, tables, and captions  
  - Tracks page numbers and section boundaries

- 馃搳 **Chart & Figure Interpretation**  
  - Uses surrounding text and captions by default (cheap & reliable)  
  - Falls back to vision-based analysis *on demand* for graphs and diagrams  
  - Associates insights with exact figures/pages

- 馃攳 **Hybrid Retrieval**  
  Combines keyword search (BM25) and semantic search (embeddings) for robust evidence discovery.

- 馃 **Deep Analytical Responses**  
  - Breaks questions into sub-questions  
  - Synthesizes across multiple sources  
  - Identifies agreements, contradictions, and gaps  
  - Produces structured, citation-backed answers

- 馃搶 **Strict Grounding**  
  Every factual statement is backed by an explicit citation:
```

(paper1.pdf p.7, Fig.2)
(survey.docx 搂3.1)

```

---

## Non-Goals (By Design)

ReferenceMiner intentionally does **not**:
- Crawl the web
- Query external APIs for content
- Hallucinate missing sources
- Make uncited claims

This keeps the system legally safe, auditable, and suitable for academic or professional use.

---

## Project Structure

```
// yet to be replenished after implementation
```

---

## How It Works (High Level)

1. **Ingest**  
   ReferenceMiner scans `references/`, detects file types, extracts text/figures, and builds a structured manifest.

2. **Index**  
   Content is chunked and indexed using:
   - BM25 (exact / keyword matching)
   - Vector embeddings (semantic matching)

3. **Retrieve**  
   For a query, both indexes are queried and merged to identify the most relevant evidence.

4. **Analyze**  
   The agent:
   - Decomposes the question
   - Reads relevant text and figures
   - Cross-checks sources
   - Identifies consensus and disagreement

5. **Respond**  
   Produces a structured answer with explicit citations and limitations.

---

## Usage (Planned Interfaces)

### CLI (minimal, recommended first)
```bash
referenceminer ingest
referenceminer list
referenceminer ask "What evidence supports method X?"
```

### API (optional)

A lightweight FastAPI service can expose:

* `/manifest`
* `/query`
* `/document/{id}`
* `/figure/{id}`

---

## Design Philosophy

* **Minimal construction, maximal output**
* Expensive operations are cached
* Vision analysis is on-demand, not upfront
* Text-first whenever possible
* Transparency over cleverness

ReferenceMiner is not a chatbot鈥攊t is an **evidence engine**.

---

## Example Queries

* 鈥淪ummarize the consensus and disagreements across these papers.鈥?
* 鈥淲hich figures support the claim that X improves Y?鈥?
* 鈥淐ompare the methodologies used in papers A, B, and C.鈥?
* 鈥淲hat assumptions are shared across all sources?鈥?
* 鈥淲hat evidence contradicts hypothesis H?鈥?

---

## Intended Use Cases

* Literature reviews
* Research validation
* Technical due diligence
* Academic writing support
* Internal knowledge audits

---

## Status

馃毀 **Early development**
The initial focus is on robust ingestion, grounding, and retrieval.
Multi-agent orchestration and advanced evaluation workflows may be added later.

---

> **ReferenceMiner**
> *If it鈥檚 not cited, it doesn鈥檛 count.*
