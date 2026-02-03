"""Enhanced PDF downloader with fallback strategies."""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Any, Callable, Optional

import httpx
from bs4 import BeautifulSoup

from refminer.crawler.models import SearchResult
from refminer.crawler.selector_engine import (
    FieldSelector,
    SelectorEngine,
    SelectorStrategy,
    SelectorType,
)

logger = logging.getLogger(__name__)


PDF_LINK_SELECTORS = FieldSelector(
    field_name="pdf_link",
    strategies=[
        SelectorStrategy(
            selector="a[href$='.pdf']",
            selector_type=SelectorType.CSS,
            priority=100,
            description="Direct PDF link",
        ),
        SelectorStrategy(
            selector="a[href*='.pdf?']",
            selector_type=SelectorType.CSS,
            priority=90,
            description="PDF link with query params",
        ),
        SelectorStrategy(
            selector="//a[contains(@href, '.pdf')]",
            selector_type=SelectorType.XPATH,
            priority=80,
            description="XPath for PDF links",
        ),
        SelectorStrategy(
            selector="a[href*='download']",
            selector_type=SelectorType.CSS,
            priority=50,
            description="Download link",
        ),
    ],
    required=False,
)

CITATION_PDF_META = FieldSelector(
    field_name="citation_pdf_meta",
    strategies=[
        SelectorStrategy(
            selector="meta[name='citation_pdf_url']",
            selector_type=SelectorType.CSS,
            priority=100,
            description="Standard citation PDF meta tag",
        ),
        SelectorStrategy(
            selector="//meta[@name='citation_pdf_url']",
            selector_type=SelectorType.XPATH,
            priority=90,
            description="XPath for citation PDF meta",
        ),
        SelectorStrategy(
            selector="meta[property='citation_pdf_url']",
            selector_type=SelectorType.CSS,
            priority=80,
            description="OpenGraph citation PDF meta",
        ),
    ],
    required=False,
)


class PDFDownloader:
    """Downloads PDFs from search results to references directory."""

    def __init__(
        self,
        references_dir: Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> None:
        self.references_dir = references_dir
        self.progress_callback = progress_callback
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(60.0),
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
        return self._client

    async def download(
        self, result: SearchResult, overwrite: bool = False
    ) -> Optional[Path]:
        """Download PDF from a search result.

        Args:
            result: Search result with PDF URL
            overwrite: Overwrite existing file

        Returns:
            Path to downloaded file, or None if failed
        """
        filename = self._generate_filename(result)
        output_path = self.references_dir / filename

        if output_path.exists() and not overwrite:
            logger.info(f"[PDFDownloader] File already exists: {filename}")
            return output_path

        if result.source == "airiti":
            airiti_info = result.metadata.get("airiti_download")
            if isinstance(airiti_info, dict):
                download_path = await self._download_airiti(output_path, airiti_info)
                if download_path:
                    return download_path

        pdf_url = await self._find_pdf_url(result)
        if not pdf_url:
            logger.warning(f"[PDFDownloader] No PDF URL found for: {result.title}")
            return None

        try:
            client = await self._get_client()
            response = await client.get(pdf_url)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "").lower()

            if "application/pdf" in content_type:
                output_path.write_bytes(response.content)
                logger.info(f"[PDFDownloader] Downloaded: {filename}")
                return output_path

            if "text/html" in content_type:
                logger.info(
                    f"[PDFDownloader] HTML response, trying to extract PDF link..."
                )
                extracted_pdf = await self._extract_pdf_from_html(
                    response.text, pdf_url
                )
                if extracted_pdf:
                    pdf_response = await client.get(extracted_pdf)
                    pdf_response.raise_for_status()
                    output_path.write_bytes(pdf_response.content)
                    logger.info(f"[PDFDownloader] Downloaded (extracted): {filename}")
                    return output_path

            logger.warning(f"[PDFDownloader] Unexpected content type: {content_type}")
            return None

        except Exception as e:
            logger.error(
                f"[PDFDownloader] Failed to download {result.title}: {e}",
                exc_info=True,
            )
            return None

    async def _download_airiti(
        self, output_path: Path, airiti_info: dict[str, Any]
    ) -> Optional[Path]:
        download_url = airiti_info.get("download_url")
        download_token = airiti_info.get("download_token")
        doc_id = airiti_info.get("download_doc_id")
        if not (download_url and download_token and doc_id):
            return None

        try:
            client = await self._get_client()
            headers = {
                "X-Requested-With": "XMLHttpRequest",
                "AjaxRequestVerificationToken": download_token,
                "Content-Type": "application/x-www-form-urlencoded",
            }
            response = await client.post(
                download_url, data={"docID": doc_id}, headers=headers
            )
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()

            if (
                "application/pdf" in content_type
                or "application/octet-stream" in content_type
            ):
                output_path.write_bytes(response.content)
                logger.info(f"[PDFDownloader] Downloaded (Airiti): {output_path.name}")
                return output_path

            if response.content.startswith(b"%PDF"):
                output_path.write_bytes(response.content)
                logger.info(f"[PDFDownloader] Downloaded (Airiti): {output_path.name}")
                return output_path

            logger.warning(
                f"[PDFDownloader] Airiti download returned content type: {content_type}"
            )
            return None
        except Exception as e:
            logger.error(f"[PDFDownloader] Airiti download failed: {e}", exc_info=True)
            return None

    async def _find_pdf_url(self, result: SearchResult) -> Optional[str]:
        """Find the best PDF URL from a search result."""
        if result.pdf_url:
            return result.pdf_url

        if result.url:
            if result.url.endswith(".pdf"):
                return result.url

            if "arxiv.org" in result.url:
                return result.url.replace("/abs/", "/pdf/") + ".pdf"

            if "biorxiv.org" in result.url or "medrxiv.org" in result.url:
                return result.url + ".full.pdf"

        if result.doi:
            return await self._resolve_doi_to_pdf(result.doi)

        return None

    async def _resolve_doi_to_pdf(self, doi: str) -> Optional[str]:
        """Try to resolve DOI to PDF URL."""
        try:
            client = await self._get_client()

            doi_url = f"https://doi.org/{doi}"
            response = await client.get(doi_url, follow_redirects=False)

            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location", "")
                if location:
                    if location.endswith(".pdf"):
                        return location

                    pdf_link = await self._extract_pdf_from_html(
                        (await client.get(location)).text, location
                    )
                    if pdf_link:
                        return pdf_link

            return None

        except Exception as e:
            logger.debug(f"[PDFDownloader] Failed to resolve DOI: {e}")
            return None

    async def _extract_pdf_from_html(self, html: str, base_url: str) -> Optional[str]:
        """Extract PDF URL from HTML content using multiple selector strategies."""
        try:
            soup = BeautifulSoup(html, "html.parser")
            engine = SelectorEngine(soup)

            pdf_links = engine.find_elements(PDF_LINK_SELECTORS)
            if pdf_links:
                href_value = pdf_links[0].get("href")
                href = href_value if isinstance(href_value, str) else ""
                if href.startswith("http"):
                    return href
                if href.startswith("/"):
                    from urllib.parse import urlparse

                    parsed = urlparse(base_url)
                    return f"{parsed.scheme}://{parsed.netloc}{href}"

            meta_pdf = engine.find_element(CITATION_PDF_META)
            if meta_pdf:
                content = meta_pdf.get("content")
                return content if isinstance(content, str) else None

            return None

        except Exception as e:
            logger.debug(f"[PDFDownloader] Failed to extract PDF from HTML: {e}")
            return None

    async def download_batch(
        self,
        results: list[SearchResult],
        overwrite: bool = False,
    ) -> dict[str, Optional[Path]]:
        """Download multiple PDFs.

        Args:
            results: List of search results
            overwrite: Overwrite existing files

        Returns:
            Dict mapping result hash to download path
        """
        downloads: dict[str, Optional[Path]] = {}

        for i, result in enumerate(results):
            if self.progress_callback:
                self.progress_callback(i, len(results), result.title)

            path = await self.download(result, overwrite)
            downloads[result.get_hash()] = path

        return downloads

    def _generate_filename(self, result: SearchResult) -> str:
        """Generate a safe filename from search result."""
        title = result.title
        year = result.year or ""

        safe_title = self._sanitize_filename(title)
        if year:
            return f"{safe_title}_{year}.pdf"
        return f"{safe_title}.pdf"

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for safe filesystem use."""
        sanitized = re.sub(r'[<>:"/\\|?*]', "", filename)
        sanitized = sanitized.strip()
        sanitized = sanitized[:200]
        return sanitized or "untitled"

    async def check_duplicate(self, result: SearchResult) -> Optional[Path]:
        """Check if a PDF already exists for this result.

        Args:
            result: Search result to check

        Returns:
            Path to existing file, or None if not found
        """
        filename = self._generate_filename(result)
        output_path = self.references_dir / filename

        if output_path.exists():
            return output_path

        return None

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self) -> PDFDownloader:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
