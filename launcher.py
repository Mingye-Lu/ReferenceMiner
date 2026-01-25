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
import subprocess
from pathlib import Path


def parent_is_alive(pid: int) -> bool:
    """Check if a process with the given PID exists on Windows."""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
        return str(pid) in result.stdout
    except Exception:
        return False


def watch_parent(parent_pid: int) -> None:
    """Exit when parent process dies."""
    while True:
        time.sleep(2)
        if not parent_is_alive(parent_pid):
            print("Parent process exited, shutting down...")
            os._exit(0)


def get_base_dir() -> Path:
    """Get the application base directory for data storage.

    Priority:
    1. REFMINER_DATA_DIR environment variable (set by Electron for packaged builds)
    2. Executable's directory (PyInstaller bundle fallback)
    3. Script's directory (development mode)
    """
    data_dir = os.environ.get("REFMINER_DATA_DIR")
    if data_dir:
        return Path(data_dir)

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
    if os.environ.get("REFMINER_OPEN_BROWSER") != "1":
        return
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

    # Start parent watchdog if launched from Electron
    parent_pid = os.environ.get("REFMINER_PARENT_PID")
    if parent_pid:
        threading.Thread(
            target=watch_parent,
            args=(int(parent_pid),),
            daemon=True,
        ).start()

    # Run the server
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
