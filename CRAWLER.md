# Crawler Implementation Summary

## Implementation Complete

The crawler backend has been successfully implemented for ReferenceMiner. Here's what was built:

## Module Structure

```
src/refminer/crawler/
├── __init__.py           # Main exports
├── base.py              # Abstract base crawler with rate limiting
├── models.py            # Pydantic models (SearchResult, SearchQuery, CrawlerConfig)
├── manager.py           # Crawler manager for orchestrating engines
├── downloader.py        # PDF downloader to references/
└── engines/
    ├── __init__.py
    ├── google_scholar.py      # Web scraping (user responsibility)
    ├── pubmed.py              # NCBI E-utilities API
    └── semantic_scholar.py   # Free API
```

## API Endpoints

All endpoints are available at `/api/crawler/`:

- `GET /engines` - List available and enabled engines
- `GET /config` - Get crawler configuration
- `POST /config` - Update crawler configuration
- `POST /search` - Search across enabled engines
- `POST /download` - Download PDFs from search results
- `POST /batch-download/stream` - Batch download with SSE streaming

## Settings Integration

Added to `src/refminer/settings/manager.py`:

- `get_crawler_config()` - Get crawler settings
- `set_crawler_config()` - Save crawler settings
- `is_crawler_enabled()` - Check if crawler is enabled
- `set_crawler_enabled()` - Enable/disable crawler
- `is_auto_download_enabled()` - Check auto-download setting
- `set_auto_download_enabled()` - Enable/disable auto-download

## Configuration Structure

```json
{
  "crawler": {
    "enabled": true,
    "auto_download": false,
    "max_results_per_engine": 20,
    "timeout_seconds": 30,
    "engines": {
      "google_scholar": {
        "enabled": true,
        "rate_limit": 5,
        "api_key": null,
        "timeout": 30,
        "max_retries": 3
      },
      "pubmed": {
        "enabled": true,
        "rate_limit": 10,
        "api_key": null,
        "timeout": 30,
        "max_retries": 3
      },
      "semantic_scholar": {
        "enabled": true,
        "rate_limit": 10,
        "api_key": null,
        "timeout": 30,
        "max_retries": 3
      }
    }
  }
}
```

## Features

1. **Multi-engine search** - Search across Google Scholar, PubMed, and Semantic Scholar concurrently
2. **Rate limiting** - Per-engine rate limits to avoid blocking
3. **Deduplication** - Automatic removal of duplicate results
4. **PDF downloading** - Optional download to `references/` directory
5. **Queue integration** - SSE streaming for long-running operations
6. **Settings persistence** - Configuration saved to `.index/settings.json`

## Test Results

Successfully tested crawler search:
- Google Scholar: Working (web scraping)
- PubMed: Available (API)
- Semantic Scholar: Available (API, may hit rate limits)

## Dependencies Added

```txt
beautifulsoup4>=4.12.0
lxml>=4.9.0
```

## Usage Example

```python
from refminer.crawler import CrawlerManager, SearchQuery
import asyncio

async def search_papers():
    manager = CrawlerManager()
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
        print(f"  Source: {result.source}")
        if result.doi:
            print(f"  DOI: {result.doi}")

asyncio.run(search_papers())
```

## Important Notes

1. **Google Scholar**: Uses web scraping which may violate terms of service. User responsibility for compliance.
2. **Auto-download**: Disabled by default. Users must enable in settings.
3. **Local-first**: Downloaded PDFs go to `references/` and are immediately indexed.
4. **Rate limits**: Each engine has configurable rate limits to avoid blocking.

## Next Steps (Future)

1. Add `search_papers` tool to agent for automatic paper discovery
2. Implement frontend: crawler search interface, results display, download controls
3. Add more engines: arXiv, CORE, DOAJ, Zenodo
4. Implement citation export functionality
5. Add batch operations for bulk download
