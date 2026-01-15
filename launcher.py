#!/usr/bin/env python
"""
ReferenceMiner Desktop Launcher

Entry point for the PyInstaller-bundled executable.
Starts the FastAPI server and opens the browser.
"""

import os
import sys
import webbrowser
import threading
import time
from pathlib import Path


def get_base_dir() -> Path:
    """Get the application base directory."""
    if getattr(sys, "frozen", False):
        # Running as PyInstaller bundle
        return Path(sys.executable).parent
    return Path(__file__).parent


def ensure_directories() -> None:
    """Create required directories if they don't exist."""
    base = get_base_dir()
    (base / "references").mkdir(exist_ok=True)
    (base / ".index").mkdir(exist_ok=True)


def open_browser(port: int, delay: float = 1.5) -> None:
    """Open browser after server starts."""
    time.sleep(delay)
    url = f"http://localhost:{port}"
    print(f"Opening browser at {url}")
    webbrowser.open(url)


def main() -> None:
    # Set working directory to executable location
    base_dir = get_base_dir()
    os.chdir(base_dir)

    # Ensure required directories exist
    ensure_directories()

    # Add src to path for development mode
    src_path = base_dir / "src"
    if src_path.exists() and str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    # Import after path setup
    import uvicorn
    from refminer.server import app

    port = int(os.environ.get("REFMINER_PORT", 8000))

    print("=" * 50)
    print("  ReferenceMiner")
    print("=" * 50)
    print(f"  Starting server at http://localhost:{port}")
    print(f"  Working directory: {base_dir}")
    print()
    print("  Place your PDF/DOCX files in the 'references' folder")
    print("  Press Ctrl+C to stop the server")
    print("=" * 50)

    # Open browser in background thread
    threading.Thread(target=open_browser, args=(port,), daemon=True).start()

    # Run the server
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
