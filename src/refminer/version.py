"""Application version metadata."""
from __future__ import annotations

import os

APP_NAME = "ReferenceMiner"
APP_VERSION = "1.0.0"
APP_REPO = os.getenv("REFMINER_REPO", "Mingye-Lu/ReferenceMiner")
APP_REPO_URL = f"https://github.com/{APP_REPO}"

__all__ = ["APP_NAME", "APP_VERSION", "APP_REPO", "APP_REPO_URL"]
