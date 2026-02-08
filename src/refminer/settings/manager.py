"""Settings manager for persistent application configuration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

PROVIDERS = {"deepseek", "openai", "gemini", "anthropic", "custom"}
CITATION_COPY_FORMATS = ("apa", "mla", "chicago", "gbt7714", "numeric")

DEFAULT_BASE_URLS = {
    "deepseek": "https://api.deepseek.com",
    "openai": "https://api.openai.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "anthropic": "https://api.anthropic.com/v1",
    "custom": "https://api.openai.com/v1",
}

DEFAULT_MODELS = {
    "deepseek": "deepseek-chat",
    "openai": "gpt-4o-mini",
    "gemini": "gemini-1.5-flash",
    "anthropic": "claude-3-haiku-20240307",
    "custom": "gpt-4o-mini",
}

OCR_MODELS = {
    "paddle-mobile": {
        "label": "PaddleOCR Mobile (v4)",
        "size": "15MB",
        "overhead": "Low",
        "download_url": "https://paddleocr.bj.bcebos.com/PP-OCRv4/english/en_PP-OCRv4_rec_infer.tar",
        "filename": "en_PP-OCRv4_rec_infer.tar",
        "is_downloadable": True,
    },
    "deepseek-ocr-2": {
        "label": "DeepSeek-OCR 2",
        "size": "6.78GB",
        "overhead": "High (16GB VRAM)",
        "hf_repo_id": "deepseek-ai/DeepSeek-OCR2",
        "is_downloadable": True,
    },
    "glm-ocr": {
        "label": "GLM-OCR",
        "size": "2.65GB",
        "overhead": "Medium (8GB VRAM)",
        "hf_repo_id": "zai-org/GLM-OCR",
        "is_downloadable": True,
    },
    "crnn-light": {
        "label": "CRNN Lightweight",
        "size": "10MB",
        "overhead": "Very Low",
        # Using specific crnn model or placeholder if not available. fallback to mobile
        "download_url": "https://paddleocr.bj.bcebos.com/PP-OCRv3/english/en_PP-OCRv3_rec_infer.tar",
        "filename": "en_PP-OCRv3_rec_infer.tar",
        "is_downloadable": True,
    },
    "external": {
        "label": "External API (Custom)",
        "size": "N/A",
        "overhead": "Network Latency",
        "is_downloadable": False,
    },
}


@dataclass
class ChatCompletionsConfig:
    """Configuration for OpenAI-compatible chat completions."""

    api_key: str
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"


class SettingsManager:
    """Manages application settings with file persistence."""

    def __init__(self, index_dir: Optional[Path] = None):
        if index_dir is None:
            index_dir = Path.cwd() / ".index"
        self.index_dir = index_dir
        self.settings_file = self.index_dir / "settings.json"
        self._settings: dict = self._load()

    def _load(self) -> dict:
        """Load settings from disk."""
        if not self.settings_file.exists():
            return {}
        try:
            with open(self.settings_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _save(self) -> None:
        """Persist settings to disk."""
        self.index_dir.mkdir(parents=True, exist_ok=True)
        with open(self.settings_file, "w", encoding="utf-8") as f:
            json.dump(self._settings, f, indent=2)

    def get_provider(self) -> str:
        """Get the active LLM provider."""
        provider = self._settings.get("llm_provider")
        return provider if provider in PROVIDERS else "deepseek"

    def set_provider(self, provider: str) -> None:
        """Save the active LLM provider."""
        if provider not in PROVIDERS:
            raise ValueError("Unsupported provider")
        self._settings["llm_provider"] = provider
        self._save()

    def _get_provider_keys(self) -> dict:
        keys = self._settings.get("provider_keys")
        return keys if isinstance(keys, dict) else {}

    def _get_provider_settings(self) -> dict:
        settings = self._settings.get("provider_settings")
        return settings if isinstance(settings, dict) else {}

    def get_api_key(self, provider: Optional[str] = None) -> Optional[str]:
        """Get API key for a provider."""
        provider = provider or self.get_provider()
        keys = self._get_provider_keys()
        key = keys.get(provider)
        if key:
            return key.strip()
        return None

    def set_api_key(self, api_key: str, provider: Optional[str] = None) -> None:
        """Save API key for a provider."""
        provider = provider or self.get_provider()
        if provider not in PROVIDERS:
            raise ValueError("Unsupported provider")
        keys = dict(self._get_provider_keys())
        keys[provider] = api_key.strip()
        self._settings["provider_keys"] = keys
        self._save()

    def get_base_url(self, provider: Optional[str] = None) -> str:
        """Get LLM base URL."""
        provider = provider or self.get_provider()
        provider_settings = self._get_provider_settings()
        provider_entry = (
            provider_settings.get(provider, {})
            if isinstance(provider_settings, dict)
            else {}
        )
        stored = provider_entry.get("base_url")
        if stored:
            return stored
        return DEFAULT_BASE_URLS.get(provider, DEFAULT_BASE_URLS["custom"])

    def set_base_url(self, base_url: str, provider: Optional[str] = None) -> None:
        """Save LLM base URL."""
        provider = provider or self.get_provider()
        provider_settings = dict(self._get_provider_settings())
        entry = dict(provider_settings.get(provider, {}))
        entry["base_url"] = base_url
        provider_settings[provider] = entry
        self._settings["provider_settings"] = provider_settings
        self._save()

    def get_model(self, provider: Optional[str] = None) -> str:
        """Get LLM model name."""
        provider = provider or self.get_provider()
        provider_settings = self._get_provider_settings()
        provider_entry = (
            provider_settings.get(provider, {})
            if isinstance(provider_settings, dict)
            else {}
        )
        stored = provider_entry.get("model")
        if stored:
            return stored
        return DEFAULT_MODELS.get(provider, DEFAULT_MODELS["custom"])

    def set_model(self, model: str, provider: Optional[str] = None) -> None:
        """Save LLM model name."""
        provider = provider or self.get_provider()
        provider_settings = dict(self._get_provider_settings())
        entry = dict(provider_settings.get(provider, {}))
        entry["model"] = model
        provider_settings[provider] = entry
        self._settings["provider_settings"] = provider_settings
        self._save()

    def get_provider_settings(self) -> dict[str, dict[str, str]]:
        """Get per-provider base URL and model settings."""
        settings: dict[str, dict[str, str]] = {}
        provider_settings = self._get_provider_settings()

        for provider in PROVIDERS:
            entry = (
                provider_settings.get(provider, {})
                if isinstance(provider_settings, dict)
                else {}
            )
            base_url = entry.get("base_url")
            model = entry.get("model")

            if not base_url:
                base_url = DEFAULT_BASE_URLS.get(provider, DEFAULT_BASE_URLS["custom"])
            if not model:
                model = DEFAULT_MODELS.get(provider, DEFAULT_MODELS["custom"])

            settings[provider] = {"base_url": base_url, "model": model}

        return settings

    def get_chat_completions_config(self) -> Optional[ChatCompletionsConfig]:
        """Get full LLM configuration if API key is available."""
        provider = self.get_provider()
        api_key = self.get_api_key(provider)
        if not api_key:
            return None
        return ChatCompletionsConfig(
            api_key=api_key,
            base_url=self.get_base_url(provider),
            model=self.get_model(provider),
        )

    def get_masked_api_key(self, provider: Optional[str] = None) -> Optional[str]:
        """Get API key masked for display (short, fixed-width)."""
        key = self.get_api_key(provider)
        if not key:
            return None
        if len(key) <= 7:
            return "*" * len(key)
        return f"{key[:3]}{'*' * 15}{key[-4:]}"

    def has_api_key(self, provider: Optional[str] = None) -> bool:
        """Check if an API key is configured for a provider."""
        return bool(self.get_api_key(provider))

    def clear_api_key(self, provider: Optional[str] = None) -> None:
        """Remove the API key for a provider."""
        provider = provider or self.get_provider()
        keys = dict(self._get_provider_keys())
        if provider in keys:
            del keys[provider]
            self._settings["provider_keys"] = keys
        self._save()

    def get_citation_copy_format(self) -> str:
        """Get the preferred citation format for copying AI responses."""
        fmt = self._settings.get("citation_copy_format")
        return fmt if fmt in CITATION_COPY_FORMATS else "apa"

    def set_citation_copy_format(self, fmt: str) -> None:
        """Save the preferred citation format for copying AI responses."""
        if fmt not in CITATION_COPY_FORMATS:
            raise ValueError("Unsupported citation format")
        self._settings["citation_copy_format"] = fmt
        self._save()

    def get_crawler_config(self) -> dict:
        """Get crawler configuration."""
        crawler_settings = self._settings.get("crawler")
        return crawler_settings if isinstance(crawler_settings, dict) else {}

    def set_crawler_config(self, config: dict) -> None:
        """Save crawler configuration."""
        self._settings["crawler"] = config
        self._save()

    def is_crawler_enabled(self) -> bool:
        """Check if crawler is enabled."""
        crawler_config = self.get_crawler_config()
        return crawler_config.get("enabled", True)

    def set_crawler_enabled(self, enabled: bool) -> None:
        """Enable or disable crawler."""
        crawler_config = self.get_crawler_config()
        crawler_config["enabled"] = enabled
        self.set_crawler_config(crawler_config)

    def is_auto_download_enabled(self) -> bool:
        """Check if auto-download is enabled."""
        crawler_config = self.get_crawler_config()
        return crawler_config.get("auto_download", False)

    def set_auto_download_enabled(self, enabled: bool) -> None:
        """Enable or disable auto-download."""
        crawler_config = self.get_crawler_config()
        crawler_config["auto_download"] = enabled
        self.set_crawler_config(crawler_config)

    def get_ocr_config(self) -> dict:
        """Get OCR configuration."""
        ocr_settings = self._settings.get("ocr")
        if not isinstance(ocr_settings, dict):
            return {
                "model": "paddle-mobile",  # Default to lightweight
                "base_url": "",
                "api_key": "",
            }
        return ocr_settings

    def set_ocr_config(self, config: dict) -> None:
        """Save OCR configuration."""
        self._settings["ocr"] = config
        self._save()
