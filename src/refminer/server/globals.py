"""Global managers and path utilities for the server."""
from __future__ import annotations

import sys
from pathlib import Path

from refminer.utils.paths import get_index_dir, get_references_dir
from refminer.projects.manager import ProjectManager
from refminer.settings import SettingsManager
from refminer.chats import ChatManager
from refminer.llm.client import set_settings_manager


def _get_base_dir() -> Path:
    """Get base directory, accounting for PyInstaller bundling."""
    if getattr(sys, "frozen", False):
        # Running as PyInstaller bundle - use executable's directory
        return Path(sys.executable).parent
    else:
        # Normal execution - relative to this file
        return Path(__file__).resolve().parent.parent.parent.parent


def _is_bundled() -> bool:
    """Check if running as a PyInstaller bundle."""
    return getattr(sys, "frozen", False)


def _get_frontend_dir() -> Path:
    """Get the frontend dist directory."""
    if _is_bundled():
        # PyInstaller extracts data to _MEIPASS
        return Path(sys._MEIPASS) / "frontend"
    else:
        return _get_base_dir() / "frontend" / "dist"


# Root directory of the repository
BASE_DIR = _get_base_dir()

# Project manager for CRUD operations
project_manager = ProjectManager(str(BASE_DIR))

# Settings manager for API key and other configuration
settings_manager = SettingsManager(get_index_dir(BASE_DIR))
set_settings_manager(settings_manager)

# Chat manager for persistent chat sessions
chat_manager = ChatManager(get_index_dir(BASE_DIR))

# Frontend directory for SPA serving
FRONTEND_DIR = _get_frontend_dir()


def get_bank_paths() -> tuple[Path, Path]:
    """Get references and index directory paths."""
    ref_dir = get_references_dir(BASE_DIR)
    idx_dir = get_index_dir(BASE_DIR)
    ref_dir.mkdir(parents=True, exist_ok=True)
    idx_dir.mkdir(parents=True, exist_ok=True)
    return ref_dir, idx_dir
