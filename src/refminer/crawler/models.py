"""Pydantic models for crawler module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional

RefIdentMode = Literal["string_only", "string_then_ocr", "ocr_only"]

from pydantic import BaseModel, Field


class SearchQuery(BaseModel):
    """Search query parameters."""

    query: str = Field(..., description="Search query string")
    engines: Optional[list[str]] = Field(
        None, description="Specific engines to search (overrides settings)"
    )
    year_from: Optional[int] = Field(None, description="Minimum publication year")
    year_to: Optional[int] = Field(None, description="Maximum publication year")
    max_results: int = Field(20, description="Maximum results per engine")
    fields: Optional[list[str]] = Field(None, description="Specific fields to search")
    include_abstract: bool = Field(True, description="Include abstract in results")


class SearchResult(BaseModel):
    """Single search result from a crawler engine."""

    title: str = Field(..., description="Paper title")
    authors: list[str] = Field(default_factory=list, description="Author names")
    year: Optional[int] = Field(None, description="Publication year")
    doi: Optional[str] = Field(None, description="Digital Object Identifier")
    abstract: Optional[str] = Field(None, description="Paper abstract")
    source: str = Field(..., description="Source engine name")
    url: Optional[str] = Field(None, description="Paper landing page URL")
    pdf_url: Optional[str] = Field(None, description="Direct PDF download URL")
    journal: Optional[str] = Field(None, description="Journal name")
    volume: Optional[str] = Field(None, description="Volume")
    issue: Optional[str] = Field(None, description="Issue")
    pages: Optional[str] = Field(None, description="Page range")
    citation_count: Optional[int] = Field(None, description="Number of citations")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    def get_hash(self) -> str:
        """Get unique hash for deduplication."""
        import hashlib

        content = f"{self.title}|{self.doi or ''}|{self.year or ''}"
        return hashlib.sha256(content.encode()).hexdigest()


CrawlerPresetName = Literal["balanced", "fast", "thorough", "minimal", "custom"]


class EngineConfig(BaseModel):
    """Configuration for a single crawler engine."""

    enabled: bool = Field(True, description="Whether this engine is enabled")
    rate_limit: int = Field(5, description="Requests per second limit")
    api_key: Optional[str] = Field(None, description="API key if required")
    timeout: int = Field(30, description="Request timeout in seconds")
    max_retries: int = Field(3, description="Maximum retry attempts")


class CrawlerConfig(BaseModel):
    """Global crawler configuration."""

    enabled: bool = Field(True, description="Whether crawler is enabled")
    auto_download: bool = Field(False, description="Automatically download PDFs")
    max_results_per_engine: int = Field(20, description="Max results per engine")
    timeout_seconds: int = Field(30, description="Default timeout")
    preset: CrawlerPresetName = Field("balanced", description="Active preset name")
    engines: dict[str, EngineConfig] = Field(
        default_factory=lambda: {
            "airiti": EngineConfig(
                enabled=False, rate_limit=2, api_key=None, timeout=30, max_retries=3
            ),
            "chinaxiv": EngineConfig(
                enabled=True, rate_limit=3, api_key=None, timeout=30, max_retries=3
            ),
            "cnki": EngineConfig(
                enabled=False, rate_limit=2, api_key=None, timeout=30, max_retries=3
            ),
            "google_scholar": EngineConfig(
                enabled=True, rate_limit=5, api_key=None, timeout=30, max_retries=3
            ),
            "pubmed": EngineConfig(
                enabled=True, rate_limit=10, api_key=None, timeout=30, max_retries=3
            ),
            "semantic_scholar": EngineConfig(
                enabled=True, rate_limit=1, api_key=None, timeout=30, max_retries=3
            ),
            "arxiv": EngineConfig(
                enabled=True, rate_limit=10, api_key=None, timeout=30, max_retries=3
            ),
            "crossref": EngineConfig(
                enabled=True, rate_limit=10, api_key=None, timeout=30, max_retries=3
            ),
            "openalex": EngineConfig(
                enabled=True, rate_limit=10, api_key=None, timeout=30, max_retries=3
            ),
            "core": EngineConfig(
                enabled=False, rate_limit=5, api_key=None, timeout=30, max_retries=3
            ),
            "europe_pmc": EngineConfig(
                enabled=True, rate_limit=10, api_key=None, timeout=30, max_retries=3
            ),
            "biorxiv_medrxiv": EngineConfig(
                enabled=False, rate_limit=5, api_key=None, timeout=30, max_retries=3
            ),
            "nstl": EngineConfig(
                enabled=False, rate_limit=2, api_key=None, timeout=30, max_retries=3
            ),
            "wanfang": EngineConfig(
                enabled=True, rate_limit=2, api_key=None, timeout=30, max_retries=3
            ),
            "chaoxing": EngineConfig(
                enabled=True, rate_limit=2, api_key=None, timeout=30, max_retries=3
            ),
        },
        description="Per-engine configurations",
    )
    ref_ident_mode: RefIdentMode = Field(
        "string_only", description="Reference identification mode"
    )

    def get_engine_config(self, engine_name: str) -> EngineConfig:
        """Get configuration for a specific engine."""
        return self.engines.get(engine_name, EngineConfig())

    def is_engine_enabled(self, engine_name: str) -> bool:
        """Check if an engine is enabled."""
        config = self.get_engine_config(engine_name)
        return self.enabled and config.enabled

    @classmethod
    def from_dict(cls, data: dict) -> CrawlerConfig:
        """Create CrawlerConfig from dict (e.g., from SettingsManager)."""
        engines_data = data.get("engines", {})

        default_config = cls()
        engines = {}

        for engine_name, default_engine_config in default_config.engines.items():
            if engine_name in engines_data:
                engine_config = engines_data[engine_name]
                if isinstance(engine_config, dict):
                    engines[engine_name] = EngineConfig(
                        enabled=engine_config.get("enabled", True),
                        rate_limit=engine_config.get("rate_limit", 5),
                        api_key=engine_config.get("api_key"),
                        timeout=engine_config.get("timeout", 30),
                        max_retries=engine_config.get("max_retries", 3),
                    )
                else:
                    engines[engine_name] = default_engine_config
            else:
                engines[engine_name] = default_engine_config

        return cls(
            enabled=data.get("enabled", True),
            auto_download=data.get("auto_download", False),
            max_results_per_engine=data.get("max_results_per_engine", 20),
            timeout_seconds=data.get("timeout_seconds", 30),
            preset=data.get("preset", "balanced"),
            engines=engines,
            ref_ident_mode=data.get("ref_ident_mode", "string_only"),
        )
