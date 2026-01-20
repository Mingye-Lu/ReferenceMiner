"""Settings manager for persistent application configuration."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

PROVIDERS = {"deepseek", "openai", "gemini", "anthropic", "custom"}

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
        if self._migrate_provider_settings():
            self._save()

    def _load(self) -> dict:
        """Load settings from disk."""
        if not self.settings_file.exists():
            return {}
        try:
            with open(self.settings_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _migrate_provider_settings(self) -> bool:
        """Migrate legacy base URL/model keys into per-provider settings."""
        settings = self._settings
        provider_settings = settings.get("provider_settings")
        if provider_settings is None or not isinstance(provider_settings, dict):
            provider_settings = {}

        provider = settings.get("llm_provider")
        provider = provider if provider in PROVIDERS else "deepseek"

        legacy_base_url = settings.get("llm_base_url") or settings.get("deepseek_base_url")
        legacy_model = settings.get("llm_model") or settings.get("deepseek_model")

        if provider not in provider_settings and (legacy_base_url or legacy_model):
            provider_settings[provider] = {}
        if provider in provider_settings:
            entry = dict(provider_settings.get(provider, {}))
            changed = False
            if legacy_base_url and not entry.get("base_url"):
                entry["base_url"] = legacy_base_url
                changed = True
            if legacy_model and not entry.get("model"):
                entry["model"] = legacy_model
                changed = True
            if changed:
                provider_settings[provider] = entry
                settings["provider_settings"] = provider_settings
                return True
        return False

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
        """Get API key for a provider, fallback to env var if available."""
        provider = provider or self.get_provider()
        keys = self._get_provider_keys()
        key = keys.get(provider)
        if key:
            return key.strip()

        if provider == "deepseek":
            legacy = self._settings.get("deepseek_api_key")
            if legacy:
                return legacy.strip()
            env_key = os.getenv("DEEPSEEK_API_KEY")
            return env_key.strip() if env_key else None

        env_map = {
            "openai": "OPENAI_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
        }
        env_key = os.getenv(env_map.get(provider, ""))
        return env_key.strip() if env_key else None

    def set_api_key(self, api_key: str, provider: Optional[str] = None) -> None:
        """Save API key for a provider."""
        provider = provider or self.get_provider()
        if provider not in PROVIDERS:
            raise ValueError("Unsupported provider")
        keys = dict(self._get_provider_keys())
        keys[provider] = api_key.strip()
        self._settings["provider_keys"] = keys
        if provider == "deepseek":
            self._settings["deepseek_api_key"] = api_key.strip()
        self._save()

    def get_base_url(self, provider: Optional[str] = None) -> str:
        """Get LLM base URL."""
        provider = provider or self.get_provider()
        provider_settings = self._get_provider_settings()
        provider_entry = provider_settings.get(provider, {}) if isinstance(provider_settings, dict) else {}
        stored = provider_entry.get("base_url") or self._settings.get("llm_base_url") or self._settings.get("deepseek_base_url")
        if stored:
            return stored
        if provider == "deepseek":
            env_url = os.getenv("DEEPSEEK_BASE_URL")
            if env_url:
                return env_url
        return DEFAULT_BASE_URLS.get(provider, DEFAULT_BASE_URLS["custom"])

    def set_base_url(self, base_url: str, provider: Optional[str] = None) -> None:
        """Save LLM base URL."""
        provider = provider or self.get_provider()
        provider_settings = dict(self._get_provider_settings())
        entry = dict(provider_settings.get(provider, {}))
        entry["base_url"] = base_url
        provider_settings[provider] = entry
        self._settings["provider_settings"] = provider_settings
        if provider == self.get_provider():
            self._settings["llm_base_url"] = base_url
        if provider == "deepseek":
            self._settings["deepseek_base_url"] = base_url
        self._save()

    def get_model(self, provider: Optional[str] = None) -> str:
        """Get LLM model name."""
        provider = provider or self.get_provider()
        provider_settings = self._get_provider_settings()
        provider_entry = provider_settings.get(provider, {}) if isinstance(provider_settings, dict) else {}
        stored = provider_entry.get("model") or self._settings.get("llm_model") or self._settings.get("deepseek_model")
        if stored:
            return stored
        if provider == "deepseek":
            env_model = os.getenv("DEEPSEEK_MODEL")
            if env_model:
                return env_model
        return DEFAULT_MODELS.get(provider, DEFAULT_MODELS["custom"])

    def set_model(self, model: str, provider: Optional[str] = None) -> None:
        """Save LLM model name."""
        provider = provider or self.get_provider()
        provider_settings = dict(self._get_provider_settings())
        entry = dict(provider_settings.get(provider, {}))
        entry["model"] = model
        provider_settings[provider] = entry
        self._settings["provider_settings"] = provider_settings
        if provider == self.get_provider():
            self._settings["llm_model"] = model
        if provider == "deepseek":
            self._settings["deepseek_model"] = model
        self._save()

    def get_provider_settings(self) -> dict[str, dict[str, str]]:
        """Get per-provider base URL and model settings."""
        settings: dict[str, dict[str, str]] = {}
        provider_settings = self._get_provider_settings()
        active_provider = self.get_provider()
        legacy_base_url = self._settings.get("llm_base_url") or self._settings.get("deepseek_base_url")
        legacy_model = self._settings.get("llm_model") or self._settings.get("deepseek_model")

        for provider in PROVIDERS:
            entry = provider_settings.get(provider, {}) if isinstance(provider_settings, dict) else {}
            base_url = entry.get("base_url")
            model = entry.get("model")

            if provider == active_provider:
                if not base_url:
                    base_url = legacy_base_url
                if not model:
                    model = legacy_model

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
            model=self.get_model(provider)
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
        if provider == "deepseek" and "deepseek_api_key" in self._settings:
            del self._settings["deepseek_api_key"]
        self._save()
