# Web Crawler

ReferenceMiner includes an optional web crawler to help discover and download research papers from multiple academic sources.

## User Responsibility

**⚠️ Important**: By enabling and using the crawler, you acknowledge:

1. **Terms of Service Compliance**:
   - Google Scholar uses web scraping which may violate their Terms of Service
   - You are responsible for ensuring your use complies with all applicable ToS
   - Consider using API-based engines (PubMed, Semantic Scholar, etc.) for better compliance

2. **API Rate Limits**:
   - Each engine has configurable rate limits
   - Respect rate limits to avoid being blocked
   - Some engines may require API keys for higher limits

3. **Content Verification**:
   - Downloaded papers should be reviewed before inclusion in your reference collection
   - The crawler is a discovery tool, not a replacement for curation

## Architecture

### Module Structure

```
src/refminer/crawler/
├── __init__.py           # Main exports
├── base.py              # Abstract base crawler with rate limiting
├── models.py            # Pydantic models (SearchResult, SearchQuery, CrawlerConfig)
├── manager.py           # Crawler manager for orchestrating engines
├── downloader.py        # PDF downloader to references/
├── deep_crawler.py      # Citation-based expansion
└── engines/
    ├── __init__.py
    ├── airiti.py              # Airiti Library (web scraping)
    ├── nstl.py                # NSTL (web scraping)
    ├── google_scholar.py      # Web scraping (requires user responsibility)
    ├── pubmed.py              # NCBI E-utilities API
    ├── semantic_scholar.py    # Free API
    ├── arxiv.py               # arXiv API
    ├── crossref.py            # Crossref API
    ├── openalex.py            # OpenAlex API
    ├── core.py                # CORE API (requires API key)
    ├── europe_pmc.py          # Europe PMC API
    ├── biorxiv_medrxiv.py     # bioRxiv/medRxiv API
    ├── chinaxiv.py            # ChinaXiv (web scraping)
    └── cnki.py                # CNKI API (requires API key)
```

### Available Engines

| Engine           | Type         | API Key Required | Default Rate Limit | Notes                         |
| ---------------- | ------------ | ---------------- | ------------------ | ----------------------------- |
| airiti           | Web scraping | No               | 2 req/min          | Airiti Library                |
| google_scholar   | Web scraping | No               | 5 req/min          | May violate ToS               |
| chinaxiv         | Web scraping | No               | 3 req/min          | ChinaXiv preprints            |
| nstl             | Web scraping | No               | 2 req/min          | NSTL portal                   |
| pubmed           | API          | No               | 10 req/min         | Biomedical literature         |
| semantic_scholar | API          | No               | 1 req/min          | AI-powered search             |
| arxiv            | API          | No               | 10 req/min         | Preprints (CS, physics, math) |
| crossrefra       | API          | No               | 10 req/min         | DOI metadata                  |
| openalex         | API          | No               | 10 req/min         | 200M+ works, citation data    |
| core             | API          | **Yes**          | 5 req/min          | Open access papers            |
| europe_pmc       | API          | No               | 10 req/min         | Life sciences, open access    |
| biorxiv_medrxiv  | API          | No               | 5 req/min          | Biology/medicine preprints    |
| cnki             | API          | **Yes**          | 2 req/min          | Licensed API required         |

## Configuration

### Compact Settings Structure

The crawler uses a compact configuration to minimize `settings.json` size:

```json
{
  "crawler": {
    "enabled": true,
    "auto_download": false,
    "max_results_per_engine": 20,
    "timeout_seconds": 30,
    "enabled_engines": [
      "google_scholar",
      "pubmed",
      "semantic_scholar",
      "arxiv",
      "crossref",
      "openalex",
      "europe_pmc"
    ],
    "engine_settings": {
      "core": {
        "api_key": "your-core-api-key-here"
      },
      "google_scholar": {
        "rate_limit": 3
      }
    }
  }
}
```

### Configuration Fields

| Field                    | Type    | Default | Description                                        |
| ------------------------ | ------- | ------- | -------------------------------------------------- |
| `enabled`                | boolean | `true`  | Enable/disable crawler globally                    |
| `auto_download`          | boolean | `false` | Auto-download after search (requires confirmation) |
| `max_results_per_engine` | integer | `20`    | Max results to fetch per engine                    |
| `timeout_seconds`        | integer | `30`    | Default timeout for all operations                 |
| `enabled_engines`        | array   | `[...]` | List of enabled engine names                       |
| `engine_settings`        | object  | `{}`    | Per-engine overrides (rate limits, API keys)       |

### Engine-Specific Settings

Override defaults per engine in `engine_settings`:

```json
{
  "engine_settings": {
    "google_scholar": {
      "enabled": true,
      "rate_limit": 3,
      "timeout": 30,
      "max_retries": 3
    },
    "core": {
      "enabled": true,
      "api_key": "your-api-key",
      "rate_limit": 5
    }
  }
}
```

## API Endpoints

All endpoints are available at `/api/crawler/`:

| Method | Endpoint                 | Description                                        |
| ------ | ------------------------ | -------------------------------------------------- |
| GET    | `/engines`               | List available and enabled engines                 |
| GET    | `/config`                | Get crawler configuration                          |
| POST   | `/config`                | Update crawler configuration (affects persistence) |
| POST   | `/search`                | Search across enabled engines                      |
| POST   | `/download`              | Download PDFs from search results                  |
| POST   | `/batch-download/stream` | Batch download with SSE streaming                  |

## Usage

### From Web UI

1. Open **ProjectHub** → **Reference Bank** tab
2. Click **"Search Online"** button
3. Enter search query and select engines
4. Review results (title, abstract, authors, source)
5. Select papers to download
6. Click **"Download Selected"**
7. Papers are saved to `references/` and automatically indexed

### From Python API

```python
from refminer.crawler import CrawlerManager, SearchQuery
import asyncio

async def search_papers():
    # Load config from settings
    from refminer.server.globals import settings_manager
    config_dict = settings_manager.get_crawler_config()
    config = CrawlerConfig(**config_dict)

    manager = CrawlerManager(config)
    query = SearchQuery(
        query="machine learning",
        max_results=10,
        year_from=2020
    )

    async with manager:
        results = await manager.search(query)

    for result in results:
        print(f"{result.title} ({result.year})")
        print(f"  Authors: {', '.join(result.authors[:3])}")
        print(f"  Source: {result.source.source}")
        if result.doi:
            print(f"  DOI: {result.doi}")

asyncio.run(search_papers())
```

## Features

### Multi-Engine Search

- Query multiple engines concurrently
- Automatic deduplication by title/DOI/year
- Merge results with source attribution

### Rate Limiting

- Per-engine rate limits to avoid blocking
- Configurable via settings
- Automatic retry with exponential backoff

### PDF Download

- Direct PDF URL extraction
- Fallback to DOI resolution
- Landing page scraping for PDF links
- Automatic ingestion after download

### Deep Crawl (Future)

- Citation-based expansion
- Fetch papers that cite or are cited by seed papers
- Controlled by max papers limit

## Known Limitations

1. **Google Scholar**: Web scraping is fragile and may break with UI changes
2. **Rate Limits**: Free APIs have strict limits; may hit errors on frequent searches
3. **PDF Availability**: Not all papers have open-access PDFs
4. **Settings Persistence**: Current version has a bug where settings may not persist (to be fixed)

## Troubleshooting

### Crawler Not Working

1. Check if crawler is enabled in Settings → Crawler
2. Verify at least one engine is enabled
3. Check rate limits (too aggressive may cause blocking)
4. Review server logs for specific errors

### PDF Download Failing

1. Some papers are behind paywalls (no PDF available)
2. Try different engines (same paper may be available elsewhere)
3. Check if DOI resolver is working
4. Review downloader logs for specific errors

### Settings Not Persisting

**Known Issue**: Current version has a bug where crawler settings may not persist to disk. This will be fixed in an upcoming update.

**Workaround**: Settings are saved to `.index/settings.json`. You can manually edit this file to update crawler configuration.

## Dependencies

```txt
beautifulsoup4>=4.12.0
lxml>=4.9.0
httpx>=0.24.0
```

## Future Enhancements

- [ ] Fix settings persistence bug
- [ ] Add `search_papers` tool to LLM agent
- [ ] Implement citation export (BibTeX, EndNote)
- [ ] Add batch operations for bulk download
- [ ] Support for more engines (DOAJ, Zenodo, etc.)
- [ ] Advanced filtering (open access only, citation count threshold)
