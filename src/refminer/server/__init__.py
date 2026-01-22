"""ReferenceMiner API server - FastAPI application factory."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from refminer.utils.paths import get_references_dir
from refminer.server.globals import BASE_DIR, FRONTEND_DIR, _is_bundled
from refminer.server.routes import (
    projects_router,
    settings_router,
    chats_router,
    files_router,
    ask_router,
    bank_router,
)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="ReferenceMiner API", version="0.1.0")

    # CORS: Allow localhost dev server in dev mode, or same-origin in bundled mode
    cors_origins = ["*"] if _is_bundled() else ["http://localhost:5173", "http://127.0.0.1:5173"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount the references directory to serve files
    # Files will be at /files/{rel_path}
    app.mount("/files", StaticFiles(directory=str(get_references_dir(BASE_DIR))), name="files")

    # Include API routers
    app.include_router(projects_router)
    app.include_router(settings_router)
    app.include_router(chats_router)
    app.include_router(files_router)
    app.include_router(ask_router)
    app.include_router(bank_router)

    # Mount frontend assets if available
    if FRONTEND_DIR.exists() and (FRONTEND_DIR / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="frontend_assets")

    # SPA serving routes
    @app.get("/")
    async def serve_root():
        """Serve the frontend index.html at root."""
        index_path = FRONTEND_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        # Fallback for development without built frontend
        return {"message": "ReferenceMiner API", "docs": "/docs"}

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """
        SPA fallback route - serves static files or index.html for client-side routing.
        This must be the LAST route registered.
        """
        # Skip API routes (handled by earlier routes)
        if full_path.startswith("api/") or full_path.startswith("files/"):
            raise HTTPException(status_code=404, detail="Not found")

        # Try to serve the exact file
        file_path = FRONTEND_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)

        # Fallback to index.html for SPA routing (e.g., /project/123)
        index_path = FRONTEND_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path)

        # No frontend available
        raise HTTPException(status_code=404, detail="Not found")

    return app


# Create the default app instance
app = create_app()

# Export commonly used items
__all__ = [
    "app",
    "create_app",
    "BASE_DIR",
    "FRONTEND_DIR",
]
