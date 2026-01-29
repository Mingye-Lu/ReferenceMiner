"""Backward-compatible import for the ReferenceMiner API server.

This module re-exports the FastAPI app from the refactored server package.
Usage remains unchanged: `uv run python -m uvicorn refminer.server:app --reload --app-dir src --port 8000`
"""

from refminer.server import app

__all__ = ["app"]
