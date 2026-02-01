"""Crawler API routes."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status

from refminer.crawler import CrawlerManager, PDFDownloader, SearchQuery
from refminer.crawler.models import CrawlerConfig, SearchResult
from refminer.server.globals import get_bank_paths, queue_events, queue_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/crawler", tags=["crawler"])


@router.get("/engines")
async def list_engines() -> dict[str, Any]:
    """List available crawler engines."""
    manager = CrawlerManager()
    return {
        "engines": manager.list_engines(),
        "enabled": manager.list_enabled_engines(),
    }


@router.get("/config")
async def get_config() -> CrawlerConfig:
    """Get crawler configuration."""
    manager = CrawlerManager()
    return manager.config


@router.post("/config")
async def update_config(config: CrawlerConfig) -> CrawlerConfig:
    """Update crawler configuration."""
    manager = CrawlerManager()
    manager.config = config
    return manager.config


@router.post("/search")
async def search_papers(query: SearchQuery) -> list[SearchResult]:
    """Search for papers across enabled engines."""
    manager = CrawlerManager()

    try:
        async with manager:
            results = await manager.search(query)
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
    results: list[SearchResult],
    overwrite: bool = False,
) -> dict[str, Any]:
    """Batch download with queue job and SSE streaming."""
    job = queue_store.create_job(
        job_type="crawler_download",
        scope="global",
        name="Batch download papers",
        status="pending",
        phase="initializing",
    )

    queue_store.update_job(
        job["id"],
        status="processing",
        phase="downloading",
        progress=0,
    )

    ref_dir, _ = get_bank_paths()

    async def _run_download():
        try:

            def progress_callback(i: int, total: int, title: str) -> None:
                queue_store.update_job(
                    job["id"],
                    progress=int((i / total) * 100) if total > 0 else 0,
                )

            downloader = PDFDownloader(
                ref_dir,
                progress_callback=progress_callback,
            )

            async with downloader:
                downloads = await downloader.download_batch(results, overwrite)

            success_count = sum(1 for path in downloads.values() if path is not None)

            queue_store.update_job(
                job["id"],
                status="complete",
                phase="done",
                progress=100,
            )

            logger.info(
                f"[Crawler] Batch download complete: {success_count}/{len(results)}"
            )
        except Exception as e:
            logger.error(f"[Crawler] Batch download failed: {e}", exc_info=True)
            queue_store.update_job(
                job["id"],
                status="failed",
                phase="error",
                error=str(e),
            )

    import asyncio

    asyncio.create_task(_run_download())

    return {"job_id": job["id"], "status": "queued"}
