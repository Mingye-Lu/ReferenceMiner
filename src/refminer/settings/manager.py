"""Settings manager for persistent application configuration."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class DeepSeekConfig:
    """Configuration for DeepSeek API."""
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

    def get_api_key(self) -> Optional[str]:
        """Get API key from settings file, fallback to env var."""
        key = self._settings.get("deepseek_api_key")
        if key:
            return key.strip()
        env_key = os.getenv("DEEPSEEK_API_KEY")
        return env_key.strip() if env_key else None

    def set_api_key(self, api_key: str) -> None:
        """Save API key to settings."""
        self._settings["deepseek_api_key"] = api_key.strip()
        self._save()

    def get_base_url(self) -> str:
        """Get DeepSeek base URL."""
        return self._settings.get(
            "deepseek_base_url",
            os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        )

    def set_base_url(self, base_url: str) -> None:
        """Save DeepSeek base URL."""
        self._settings["deepseek_base_url"] = base_url
        self._save()

    def get_model(self) -> str:
        """Get DeepSeek model name."""
        return self._settings.get(
            "deepseek_model",
            os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        )

    def set_model(self, model: str) -> None:
        """Save DeepSeek model name."""
        self._settings["deepseek_model"] = model
        self._save()

    def get_deepseek_config(self) -> Optional[DeepSeekConfig]:
        """Get full DeepSeek configuration if API key is available."""
        api_key = self.get_api_key()
        if not api_key:
            return None
        return DeepSeekConfig(
            api_key=api_key,
            base_url=self.get_base_url(),
            model=self.get_model()
        )

    def get_masked_api_key(self) -> Optional[str]:
        """Get API key with most characters masked for display (first 3 + last 4 visible)."""
        key = self.get_api_key()
        if not key:
            return None
        if len(key) <= 7:
            return "*" * len(key)
        return key[:3] + "*" * (len(key) - 7) + key[-4:]

    def has_api_key(self) -> bool:
        """Check if an API key is configured."""
        return bool(self.get_api_key())

    def clear_api_key(self) -> None:
        """Remove the API key from settings."""
        if "deepseek_api_key" in self._settings:
            del self._settings["deepseek_api_key"]
            self._save()
