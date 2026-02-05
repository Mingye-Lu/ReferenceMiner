"""Crawler API routes."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from refminer.crawler import CrawlerManager, PDFDownloader, SearchQuery
from refminer.crawler.models import CrawlerConfig, SearchResult
from refminer.ingest.incremental import full_ingest_single_file
from refminer.server.globals import (
    get_bank_paths,
    queue_events,
    queue_store,
    settings_manager,
)

logger = logging.getLogger(__name__)


class BatchDownloadRequest(BaseModel):
    results: list[SearchResult]
    overwrite: bool = False


router = APIRouter(prefix="/api/crawler", tags=["crawler"])


def _load_crawler_config() -> CrawlerConfig:
    """Load crawler config from settings manager."""
    crawler_data = settings_manager.get_crawler_config()
    if crawler_data:
        return CrawlerConfig.from_dict(crawler_data)
    return CrawlerConfig()


@router.get("/engines")
async def list_engines() -> dict[str, Any]:
    """List available crawler engines."""
    config = _load_crawler_config()
    manager = CrawlerManager(config)
    return {
        "engines": manager.list_engines(),
        "enabled": manager.list_enabled_engines(),
    }


@router.get("/config")
async def get_config() -> CrawlerConfig:
    """Get crawler configuration."""
    return _load_crawler_config()


@router.post("/config")
async def update_config(config: CrawlerConfig) -> CrawlerConfig:
    """Update crawler configuration."""
    settings_manager.set_crawler_config(config.model_dump())
    return config


@router.post("/search")
async def search_papers(query: SearchQuery) -> list[SearchResult]:
    """Search for papers across enabled engines."""
    config = _load_crawler_config()
    if not config.enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Crawler is disabled in settings",
        )
    manager = CrawlerManager(config)

    try:
        async with manager:
            results = await manager.search(
                query,
                engines=query.engines,
                allow_disabled=bool(query.engines),
            )
        return results
    except Exception as e:
        logger.error(f"[Crawler] Search failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}",
        )


@router.post("/download")
async def download_papers(
    results: list[SearchResult], overwrite: bool = False
) -> dict[str, Any]:
    """Download PDFs from search results."""
    ref_dir, _ = get_bank_paths()

    downloader = PDFDownloader(ref_dir)

    try:
        async with downloader:
            downloads = await downloader.download_batch(results, overwrite)

        success_count = sum(1 for path in downloads.values() if path is not None)
        return {
            "total": len(results),
            "success": success_count,
            "failed": len(results) - success_count,
            "downloads": {
                result_hash: str(path) if path else None
                for result_hash, path in downloads.items()
            },
        }
    except Exception as e:
        logger.error(f"[Crawler] Download failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Download failed: {str(e)}",
        )


@router.post("/batch-download/stream")
async def batch_download_stream(
    req: BatchDownloadRequest,
) -> dict[str, Any]:
    """Batch download with per-file queue jobs."""
    ref_dir, idx_dir = get_bank_paths()
    job_ids = []

    async def _run_single_download(result: SearchResult, job_id: str):
        """Download and ingest a single paper."""
        try:
            queue_store.update_job(
                job_id,
                status="processing",
                phase="downloading",
                progress=10,
            )

            downloader = PDFDownloader(ref_dir)
            async with downloader:
                pdf_path = await downloader.download(result, req.overwrite)

            if not pdf_path:
                queue_store.update_job(
                    job_id,
                    status="error",
                    phase=None,
                    error="Failed to download PDF",
                    progress=100,
                )
                logger.warning(f"[Crawler] Failed to download: {result.title}")
                return

            queue_store.update_job(
                job_id,
                status="processing",
                phase="indexing",
                progress=30,
            )

            entry = full_ingest_single_file(
                pdf_path,
                references_dir=ref_dir,
                index_dir=idx_dir,
                build_vectors=True,
            )

            queue_store.update_job(
                job_id,
                status="complete",
                phase=None,
                progress=100,
                rel_path=entry.rel_path,
                name=Path(entry.rel_path).name,
            )

            logger.info(f"[Crawler] Downloaded and ingested: {result.title}")

        except Exception as e:
            logger.error(
                f"[Crawler] Failed to process {result.title}: {e}", exc_info=True
            )
            queue_store.update_job(
                job_id,
                status="error",
                phase=None,
                error=str(e),
                progress=100,
            )

    import asyncio

    for result in req.results:
        job = queue_store.create_job(
            job_type="crawler_download_single",
            scope="bank",
            name=result.title[:100],
            status="pending",
            phase="downloading",
        )
        job_ids.append(job["id"])
        asyncio.create_task(_run_single_download(result, job["id"]))

    return {"job_ids": job_ids, "status": "queued", "count": len(job_ids)}
