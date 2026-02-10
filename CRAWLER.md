# Web Crawler

ReferenceMiner includes an optional crawler that discovers paper metadata and download links from multiple academic sources, then ingests downloaded PDFs into your local `references/` bank.

## Documentation Scope

This document covers:

- crawler architecture and module layout
- supported engines and defaults
- configuration schema used by the backend
- crawler API endpoints and request/response shapes
- practical usage and troubleshooting

For complete server API details, see `ENDPOINTS.md`.

## User Responsibility

Using crawler features means you are responsible for:

1. Terms of service compliance
   - Some engines rely on web scraping (for example `google_scholar`)
   - You must ensure your usage complies with site terms and local rules

2. Rate limit discipline
   - Each engine has its own request limit
   - Aggressive settings can cause temporary blocking or degraded results

3. Curating downloaded content
   - The crawler is a discovery pipeline, not an automatic quality filter
   - Review downloaded papers before relying on them in analysis

## Architecture

### Module Structure

```text
src/refminer/crawler/
|- __init__.py            # public exports
|- base.py                # base crawler + retry/rate limit behavior
|- models.py              # SearchQuery, SearchResult, CrawlerConfig
|- manager.py             # multi-engine orchestration + deduplication
|- downloader.py          # PDF download and filename handling
|- deep_crawler.py        # deeper expansion flow (citation-oriented)
|- selector_engine.py     # extraction strategy coordinator
|- selectors/
|  |- __init__.py
|  `- google_scholar.py
`- engines/
   |- __init__.py
   |- airiti.py
   |- arxiv.py
   |- biorxiv_medrxiv.py
   |- chaoxing.py
   |- chinaxiv.py
   |- cnki.py
   |- core.py
   |- crossref.py
   |- europe_pmc.py
   |- google_scholar.py
   |- nstl.py
   |- openalex.py
   |- pubmed.py
   |- semantic_scholar.py
   `- wanfang.py
```

### Runtime Flow

1. Frontend or API sends `SearchQuery`
2. `CrawlerManager` fans out requests to selected engines concurrently
3. Results are deduplicated by hash (`title|doi|year`)
4. Selected results are passed to `PDFDownloader`
5. Downloaded PDFs are ingested via `full_ingest_single_file(...)`
6. New entries become searchable in the normal retrieval pipeline

## Available Engines

Default values come from `CrawlerConfig` in `src/refminer/crawler/models.py`.

| Engine             | Type         | API Key Required | Default Rate Limit | Enabled by Default |
| ------------------ | ------------ | ---------------- | ------------------ | ------------------ |
| `airiti`           | Web scraping | No               | 2 req/min          | No                 |
| `chaoxing`         | Web scraping | No               | 2 req/min          | Yes                |
| `chinaxiv`         | Web scraping | No               | 3 req/min          | Yes                |
| `cnki`             | API          | Yes              | 2 req/min          | No                 |
| `google_scholar`   | Web scraping | No               | 5 req/min          | Yes                |
| `pubmed`           | API          | No               | 10 req/min         | Yes                |
| `semantic_scholar` | API          | No               | 1 req/min          | Yes                |
| `arxiv`            | API          | No               | 10 req/min         | Yes                |
| `crossref`         | API          | No               | 10 req/min         | Yes                |
| `openalex`         | API          | No               | 10 req/min         | Yes                |
| `core`             | API          | Yes              | 5 req/min          | No                 |
| `europe_pmc`       | API          | No               | 10 req/min         | Yes                |
| `biorxiv_medrxiv`  | API          | No               | 5 req/min          | No                 |
| `nstl`             | Web scraping | No               | 2 req/min          | No                 |
| `wanfang`          | Web scraping | No               | 2 req/min          | Yes                |

## Configuration

Crawler settings are persisted through the application settings store and returned by `GET /api/crawler/config`.

### CrawlerConfig Shape

```json
{
  "enabled": true,
  "auto_download": false,
  "max_results_per_engine": 20,
  "timeout_seconds": 30,
  "preset": "balanced",
  "ref_ident_mode": "string_only",
  "engines": {
    "google_scholar": {
      "enabled": true,
      "rate_limit": 5,
      "api_key": null,
      "timeout": 30,
      "max_retries": 3
    },
    "core": {
      "enabled": false,
      "rate_limit": 5,
      "api_key": "your-core-key",
      "timeout": 30,
      "max_retries": 3
    }
  }
}
```

### Key Fields

| Field                    | Type      | Description |
| ------------------------ | --------- | ----------- |
| `enabled`                | boolean   | Global crawler on/off switch |
| `auto_download`          | boolean   | Automatic download behavior |
| `max_results_per_engine` | integer   | Search cap used per engine |
| `timeout_seconds`        | integer   | Global crawler timeout default |
| `preset`                 | string    | Preset profile (`balanced`, `fast`, `thorough`, `minimal`, `custom`) |
| `ref_ident_mode`         | string    | Reference matching mode (`string_only`, `string_then_ocr`, `ocr_only`) |
| `engines`                | object    | Per-engine overrides (`enabled`, `rate_limit`, `api_key`, `timeout`, `max_retries`) |

## API Endpoints

All routes are under `/api/crawler`.

| Method | Path                     | Description |
| ------ | ------------------------ | ----------- |
| GET    | `/engines`               | Returns available and enabled engines |
| GET    | `/config`                | Returns current `CrawlerConfig` |
| POST   | `/config`                | Persists `CrawlerConfig` |
| POST   | `/search`                | Multi-engine search returning `SearchResult[]` |
| POST   | `/download`              | Download + ingest from `SearchResult[]` |
| POST   | `/batch-download/stream` | Queue-backed batch download flow |
| POST   | `/fetch-metadata`        | URL metadata resolver (arXiv/DOI/OpenReview/web tags) |

### Example: Search

```bash
curl -X POST http://localhost:8000/api/crawler/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "retrieval augmented generation",
    "engines": ["arxiv", "crossref", "openalex"],
    "max_results": 10,
    "year_from": 2021
  }'
```

### Example: Batch Download Stream

```bash
curl -X POST http://localhost:8000/api/crawler/batch-download/stream \
  -H "Content-Type: application/json" \
  -d '{"results": [{"title": "...", "authors": [], "source": "arxiv"}], "overwrite": false}'
```

The endpoint returns queued job IDs. Use queue APIs (`/api/queue/jobs`, `/api/queue/stream`) to observe progress.

## Usage

### From Web UI

1. Open ProjectHub and go to Reference Bank
2. Start an online search
3. Choose engines and run query
4. Review metadata before download
5. Download selected papers
6. Wait for ingestion to complete

### From Python

```python
import asyncio

from refminer.crawler import CrawlerManager, SearchQuery
from refminer.crawler.models import CrawlerConfig
from refminer.server.globals import settings_manager


async def search_papers() -> None:
    config = CrawlerConfig.from_dict(settings_manager.get_crawler_config())
    manager = CrawlerManager(config)
    query = SearchQuery(query="machine learning", max_results=10, year_from=2020)

    async with manager:
        results = await manager.search(query)

    for item in results[:5]:
        print(item.title, item.year, item.source)


asyncio.run(search_papers())
```

## Operational Notes

- Search is best-effort: one engine can fail while others still return results
- Deduplication is conservative; near-duplicate titles may still appear
- PDF availability varies by publisher access and license
- Ingestion after download attaches crawler-fetched bibliography fields when available

## Troubleshooting

### No Results

1. Confirm crawler is enabled (`GET /api/crawler/config`)
2. Confirm at least one requested engine is enabled (or explicitly set `engines` in search)
3. Relax filters (`year_from`, `year_to`, `max_results`)
4. Retry with API-based engines if scraping sources are unstable

### Download Failures

1. Check whether the source has an accessible PDF
2. Retry with `overwrite: false` to avoid replacing good local files
3. Inspect backend logs for downloader or ingest exceptions

### Metadata Looks Incomplete

1. Call `/api/crawler/fetch-metadata` for the source URL
2. Prefer DOI or arXiv URLs when available
3. Expect partial metadata for generic web pages without academic meta tags
