"""Crawler API routes."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

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


def _search_result_to_bibliography(result: SearchResult) -> dict[str, Any]:
    """Convert SearchResult to bibliography dict for ingest."""
    bib: dict[str, Any] = {}
    
    if result.title:
        bib["title"] = result.title
    
    if result.authors:
        bib["authors"] = [{"literal": author} for author in result.authors]
    
    if result.year:
        bib["year"] = result.year
    
    if result.doi:
        bib["doi"] = result.doi
    
    if result.abstract:
        bib["abstract"] = result.abstract
    
    if result.journal:
        bib["journal"] = result.journal
    
    if result.volume:
        bib["volume"] = result.volume
    
    if result.issue:
        bib["issue"] = result.issue
    
    if result.pages:
        bib["pages"] = result.pages
    
    if result.citation_count:
        bib["citation_count"] = result.citation_count
    
    bib["extraction"] = "crawler_pre_fetched"
    
    return bib


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
    """Download PDFs from search results and ingest them."""
    ref_dir, idx_dir = get_bank_paths()

    downloader = PDFDownloader(ref_dir)

    try:
        async with downloader:
            downloads = await downloader.download_batch(results, overwrite)

        ingested = {}
        for result, pdf_path in zip(results, downloads.values()):
            if pdf_path:
                try:
                    bibliography = _search_result_to_bibliography(result)
                    entry = full_ingest_single_file(
                        pdf_path,
                        references_dir=ref_dir,
                        index_dir=idx_dir,
                        build_vectors=True,
                        bibliography=bibliography,
                    )
                    ingested[result.get_hash()] = {
                        "path": str(pdf_path),
                        "rel_path": entry.rel_path,
                        "bibliography": entry.bibliography,
                    }
                except Exception as e:
                    logger.error(
                        f"[Crawler] Failed to ingest {result.title}: {e}", exc_info=True
                    )
                    ingested[result.get_hash()] = {
                        "path": str(pdf_path),
                        "error": str(e),
                    }
            else:
                ingested[result.get_hash()] = None

        success_count = sum(1 for v in ingested.values() if v and "error" not in v)
        return {
            "total": len(results),
            "success": success_count,
            "failed": len(results) - success_count,
            "downloads": ingested,
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

            bibliography = _search_result_to_bibliography(result)
            entry = full_ingest_single_file(
                pdf_path,
                references_dir=ref_dir,
                index_dir=idx_dir,
                build_vectors=True,
                bibliography=bibliography,
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


class FetchMetadataRequest(BaseModel):
    """Request to fetch metadata from a URL."""
    url: str
    arxiv_id: Optional[str] = None
    doi: Optional[str] = None


class FetchMetadataResponse(BaseModel):
    """Response containing fetched metadata."""
    title: Optional[str] = None
    authors: Optional[list[str]] = None
    year: Optional[int] = None
    source: str = "unknown"  # "arxiv", "doi", "webpage"
    pdf_url: Optional[str] = None
    is_academic: bool = False


@router.post("/fetch-metadata")
async def fetch_metadata(req: FetchMetadataRequest) -> FetchMetadataResponse:
    """Fetch metadata from a URL (arXiv, DOI, or generic webpage)."""
    import re
    import httpx
    
    # Synthesize URL if missing but ID exists (ensures fallback works if primary API fails)
    if not req.url:
        if req.arxiv_id:
            req.url = f"https://arxiv.org/abs/{req.arxiv_id}"
        elif req.doi:
            req.url = f"https://doi.org/{req.doi}"
    
    # Check for arXiv
    if req.arxiv_id or (req.url and "arxiv" in req.url.lower()):
        arxiv_id = req.arxiv_id
        if not arxiv_id and req.url:
            # Extract arXiv ID from URL
            match = re.search(r'arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5}(?:v\d+)?)', req.url, re.IGNORECASE)
            if match:
                arxiv_id = match.group(1)
        
        if arxiv_id:
            try:
                # Use arXiv API to get metadata
                api_url = f"https://export.arxiv.org/api/query?id_list={arxiv_id}"
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(api_url)
                    if resp.status_code == 200:
                        import xml.etree.ElementTree as ET
                        root = ET.fromstring(resp.text)
                        ns = {"atom": "http://www.w3.org/2005/Atom"}
                        entry = root.find("atom:entry", ns)
                        if entry is not None:
                            title_elem = entry.find("atom:title", ns)
                            title = title_elem.text.strip() if title_elem is not None and title_elem.text else None
                            
                            authors = []
                            for author_elem in entry.findall("atom:author/atom:name", ns):
                                if author_elem.text:
                                    authors.append(author_elem.text.strip())
                            
                            year = None
                            published = entry.find("atom:published", ns)
                            if published is not None and published.text:
                                try:
                                    year = int(published.text[:4])
                                except (ValueError, IndexError):
                                    pass
                            
                            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
                            
                            return FetchMetadataResponse(
                                title=title,
                                authors=authors if authors else None,
                                year=year,
                                source="arxiv",
                                pdf_url=pdf_url,
                                is_academic=True
                            )
            except Exception as e:
                logger.warning(f"ArXiv metadata fetch failed: {e}")
    
    # Check for DOI
    if req.doi or (req.url and "doi.org" in req.url.lower()):
        doi = req.doi
        if not doi and req.url:
            match = re.search(r'doi\.org/(10\.\d{4,9}/[^\s]+)', req.url)
            if match:
                doi = match.group(1)
        
        if doi:
            try:
                # Use CrossRef API
                api_url = f"https://api.crossref.org/works/{doi}"
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(api_url, headers={"Accept": "application/json"})
                    if resp.status_code == 200:
                        data = resp.json().get("message", {})
                        title = data.get("title", [None])[0]
                        authors = []
                        for author in data.get("author", []):
                            name = f"{author.get('given', '')} {author.get('family', '')}".strip()
                            if name:
                                authors.append(name)
                        
                        year = None
                        published = data.get("published-print") or data.get("published-online") or data.get("created")
                        if published and "date-parts" in published:
                            try:
                                year = published["date-parts"][0][0]
                            except (IndexError, TypeError):
                                pass
                        
                        return FetchMetadataResponse(
                            title=title,
                            authors=authors if authors else None,
                            year=year,
                            source="doi",
                            pdf_url=None,  # DOI doesn't provide direct PDF
                            is_academic=True
                        )
            except Exception as e:
                logger.warning(f"DOI metadata fetch failed: {e}")
    
    # Fallback: fetch webpage title
    # Check for OpenReview
    if req.url and "openreview.net" in req.url.lower():
        try:
            # Extract ID from URL
            or_id = None
            match = re.search(r'id=([a-zA-Z0-9_]+)', req.url)
            if match:
                or_id = match.group(1)
            
            if or_id:
                # Use OpenReview API
                # Try v1 API first (most common for older papers)
                api_url = f"https://api.openreview.net/notes?id={or_id}"
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(api_url)
                    if resp.status_code == 200:
                        data = resp.json()
                        notes = data.get("notes", [])
                        if notes:
                            note = notes[0]
                            content = note.get("content", {})
                            
                            title = content.get("title")
                            authors = content.get("authors", [])
                            
                            # Try to find year from various date fields
                            year = None
                            # cdate is creation date (ms timestamp)
                            cdate = note.get("cdate")
                            if cdate:
                                import datetime
                                year = datetime.datetime.fromtimestamp(cdate/1000).year
                            
                            pdf_url = f"https://openreview.net/pdf?id={or_id}"
                            
                            return FetchMetadataResponse(
                                title=title,
                                authors=authors,
                                year=year,
                                source="openreview",
                                pdf_url=pdf_url,
                                is_academic=True
                            )
                    
                    # If v1 fails or returns empty, one might try v2, but v1 is standard for "forum" URLs
        except Exception as e:
            logger.warning(f"OpenReview metadata fetch failed: {e}")

    # Fallback: fetch webpage title and academic meta tags
    if req.url:
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, verify=False) as client:
                # Use a real browser UA to avoid blocking
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
                }
                resp = await client.get(req.url, headers=headers)
                
                # Handle PDF content type directly
                content_type = resp.headers.get("content-type", "").lower()
                if "application/pdf" in content_type:
                    # It's a PDF file. We can't parse HTML.
                    # Return filename as title if possible, or just the URL basename
                    import urllib.parse
                    parsed = urllib.parse.urlparse(req.url)
                    filename = Path(parsed.path).name
                    return FetchMetadataResponse(
                        title=filename or "PDF Document",
                        authors=["PDF File"],
                        year=None,
                        source="pdf_url",
                        pdf_url=req.url,
                        is_academic=True 
                    )

                if resp.status_code == 403 or resp.status_code == 401:
                    # Forbidden/Unauthorized - Fallback to using URL as title
                     # Extract domain for source
                    domain_match = re.match(r'https?://([^/]+)', req.url)
                    domain = domain_match.group(1) if domain_match else "webpage"
                    domain = re.sub(r'^www\.', '', domain)
                    
                    return FetchMetadataResponse(
                        title=req.url,
                        authors=["Third-party Website"],
                        year=None,
                        source=domain,
                        pdf_url=None,
                        is_academic=False
                    )

                if resp.status_code == 200:
                    from bs4 import BeautifulSoup
                    import html
                    
                    soup = BeautifulSoup(resp.text, "html.parser")
                    
                    # 1. Highwire / Google Scholar Tags
                    citation_title = soup.find("meta", attrs={"name": "citation_title"})
                    citation_authors = soup.find_all("meta", attrs={"name": "citation_author"})
                    citation_date = soup.find("meta", attrs={"name": "citation_date"}) or \
                                    soup.find("meta", attrs={"name": "citation_publication_date"}) or \
                                    soup.find("meta", attrs={"name": "citation_online_date"})
                    citation_pdf = soup.find("meta", attrs={"name": "citation_pdf_url"})
                    
                    # 2. Dublin Core Tags
                    dc_title = soup.find("meta", attrs={"name": "DC.title"}) or soup.find("meta", attrs={"name": "DC.Title"})
                    dc_creators = soup.find_all("meta", attrs={"name": "DC.creator"}) or soup.find_all("meta", attrs={"name": "DC.Creator"})
                    dc_date = soup.find("meta", attrs={"name": "DC.date"}) or soup.find("meta", attrs={"name": "DC.Date"}) or \
                              soup.find("meta", attrs={"name": "DC.issued"})
                    
                    # 3. OpenGraph Tags for Fallback
                    og_title = soup.find("meta", property="og:title")
                    og_site_name = soup.find("meta", property="og:site_name")

                    title = None
                    authors = []
                    year = None
                    pdf_url = None
                    is_academic = False

                    # Title Priority
                    if citation_title and citation_title.get("content"):
                        title = citation_title["content"].strip()
                        is_academic = True
                    elif dc_title and dc_title.get("content"):
                        title = dc_title["content"].strip()
                        is_academic = True
                    elif og_title and og_title.get("content"):
                        title = og_title["content"].strip()
                    
                    # Authors Priority
                    if citation_authors:
                        authors = [a["content"].strip() for a in citation_authors if a.get("content")]
                    elif dc_creators:
                        authors = [a["content"].strip() for a in dc_creators if a.get("content")]
                    
                    # Date Priority
                    date_str = None
                    if citation_date and citation_date.get("content"):
                        date_str = citation_date["content"]
                    elif dc_date and dc_date.get("content"):
                        date_str = dc_date["content"]
                    
                    if date_str:
                        # date format can be YYYY-MM-DD or YYYY/MM/DD or just YYYY
                        match = re.search(r'(\d{4})', date_str)
                        if match:
                            year = int(match.group(1))

                    # PDF Priority
                    if citation_pdf and citation_pdf.get("content"):
                        pdf_url = citation_pdf["content"]

                    # Fallback Title
                    if not title:
                        title_tag = soup.find("title")
                        title = title_tag.get_text().strip() if title_tag else None
                    
                    if title:
                        title = html.unescape(title)
                    
                    # Extract domain for source
                    domain_match = re.match(r'https?://([^/]+)', req.url)
                    domain = domain_match.group(1) if domain_match else "webpage"
                    domain = re.sub(r'^www\.', '', domain)

                    # Determine source label
                    source_label = domain
                    if og_site_name and og_site_name.get("content"):
                        source_label = og_site_name["content"]

                    # If we found academic tags, trust them
                    if is_academic:
                        return FetchMetadataResponse(
                            title=title,
                            authors=authors,
                            year=year,
                            source="web_meta",
                            pdf_url=pdf_url,
                            is_academic=True
                        )

                    # Otherwise, careful fallback
                    return FetchMetadataResponse(
                        title=title or domain,
                        authors=[source_label] if source_label else ["Third-party Website"],
                        year=None,
                        source=domain,
                        pdf_url=None,
                        is_academic=False
                    )
        except Exception as e:
            logger.warning(f"Webpage metadata fetch failed: {e}")
    
    return FetchMetadataResponse(source="unknown")
