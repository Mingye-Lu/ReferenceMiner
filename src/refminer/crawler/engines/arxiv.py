"""ArXiv crawler using the arXiv API."""

from __future__ import annotations

import logging
import urllib.parse
from typing import Any, Optional

from refminer.crawler.base import BaseCrawler
from refminer.crawler.models import SearchQuery, SearchResult

logger = logging.getLogger(__name__)


class ArXivCrawler(BaseCrawler):
    """ArXiv crawler using the arXiv API."""

    @property
    def name(self) -> str:
        return "arxiv"

    @property
    def base_url(self) -> str:
        return "http://export.arxiv.org/api/query"

    @property
    def requires_api_key(self) -> bool:
        return False

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        """Search ArXiv for papers."""
        results: list[SearchResult] = []

        try:
            search_url = self._build_search_url(query)
            response = await self._fetch(search_url)
            results = self._parse_results(response.text, query)

            logger.info(f"[{self.name}] Found {len(results)} results")
        except Exception as e:
            logger.error(f"[{self.name}] Search failed: {e}", exc_info=True)

        return results

    def _build_search_url(self, query: SearchQuery) -> str:
        """Build ArXiv search URL."""
        params = {
            "search_query": f"all:{query.query}",
            "start": "0",
            "max_results": str(query.max_results),
        }

        if query.year_from:
            params["search_query"] += f" AND submittedDate:[{query.year_from}0101 TO *]"
        if query.year_to:
            params["search_query"] += f" AND submittedDate:[* TO {query.year_to}1231]"

        encoded_params = urllib.parse.urlencode(params)
        return f"{self.base_url}?{encoded_params}"

    def _parse_results(self, xml_text: str, query: SearchQuery) -> list[SearchResult]:
        """Parse ArXiv XML response."""
        try:
            import xml.etree.ElementTree as ET
        except ImportError:
            logger.error(f"[{self.name}] xml.etree.ElementTree not available")
            return []

        results: list[SearchResult] = []

        try:
            root = ET.fromstring(xml_text)
            namespace = {"atom": "http://www.w3.org/2005/Atom"}

            entries = root.findall("atom:entry", namespace)
            for entry in entries:
                try:
                    result = self._parse_single_entry(entry, namespace, query)
                    if result:
                        results.append(result)
                except Exception as e:
                    logger.debug(f"[{self.name}] Failed to parse entry: {e}")
                    continue
        except ET.ParseError as e:
            logger.error(f"[{self.name}] Failed to parse XML: {e}")

        return results

    def _parse_single_entry(
        self, entry: Any, namespace: dict[str, str], query: SearchQuery
    ) -> Optional[SearchResult]:
        """Parse a single ArXiv entry."""
        title_elem = entry.find("atom:title", namespace)
        if title_elem is None:
            return None

        title = title_elem.text.strip() if title_elem.text else ""
        if not title:
            return None

        authors = self._parse_authors(entry, namespace)
        year = self._parse_year(entry, namespace)
        abstract = self._parse_abstract(entry, namespace)
        url = self._parse_url(entry, namespace)
        pdf_url = self._parse_pdf_url(entry, namespace)
        journal = "arXiv"

        result = SearchResult(
            title=title,
            authors=authors,
            year=year,
            doi=None,
            abstract=abstract,
            source=self.name,
            url=url,
            pdf_url=pdf_url,
            journal=journal,
            volume=None,
            issue=None,
            pages=None,
            citation_count=None,
        )

        return result

    def _parse_authors(self, entry: Any, namespace: dict[str, str]) -> list[str]:
        """Parse authors from entry."""
        authors: list[str] = []
        author_elems = entry.findall("atom:author/atom:name", namespace)

        for author_elem in author_elems:
            name = author_elem.text.strip() if author_elem.text else ""
            if name:
                authors.append(name)

        return authors

    def _parse_year(self, entry: Any, namespace: dict[str, str]) -> Optional[int]:
        """Parse publication year from entry."""
        published_elem = entry.find("atom:published", namespace)
        if published_elem is not None and published_elem.text:
            date_str = published_elem.text
            try:
                return int(date_str[:4])
            except (ValueError, IndexError):
                pass
        return None

    def _parse_abstract(self, entry: Any, namespace: dict[str, str]) -> Optional[str]:
        """Parse abstract from entry."""
        summary_elem = entry.find("atom:summary", namespace)
        if summary_elem is not None and summary_elem.text:
            return summary_elem.text.strip()
        return None

    def _parse_url(self, entry: Any, namespace: dict[str, str]) -> Optional[str]:
        """Parse landing page URL from entry."""
        id_elem = entry.find("atom:id", namespace)
        if id_elem is not None and id_elem.text:
            return id_elem.text.strip()
        return None

    def _parse_pdf_url(self, entry: Any, namespace: dict[str, str]) -> Optional[str]:
        """Parse PDF URL from entry."""
        for link in entry.findall("atom:link", namespace):
            link_type = link.get("type", "")
            href = link.get("href", "")
            if link_type == "application/pdf" and href:
                return href
        return None
