"""Settings management endpoints."""

from __future__ import annotations

import time
from typing import Optional
from urllib.parse import urlparse

import httpx
import shutil
import tarfile
import zipfile
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel

from refminer.server.globals import settings_manager, get_bank_paths
from refminer.server.models import (
    ApiKeyRequest,
    ApiKeyValidateRequest,
    CitationFormatRequest,
    LlmSettingsRequest,
    ApiKeyValidateRequest,
    CitationFormatRequest,
    LlmSettingsRequest,
    ModelsListRequest,
    OcrSettingsRequest,
    OcrDownloadModelRequest,
)
from refminer.settings.manager import OCR_MODELS, DEFAULT_OCR_BASE_URL
from refminer.server.utils import clear_bank_indexes
from refminer.utils.versioning import (
    get_local_version,
    get_repo_slug,
    is_newer_version,
    normalize_version,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])

PROVIDERS = ("deepseek", "openai", "gemini", "anthropic", "custom")
GITHUB_API = "https://api.github.com"


def _github_headers() -> dict:
    return {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ReferenceMiner",
    }


def _github_get_json(url: str) -> Optional[dict]:
    with httpx.Client(timeout=10.0) as client:
        response = client.get(url, headers=_github_headers())
    if response.status_code == 404:
        return None
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else None


def _fetch_latest_release(repo: str) -> Optional[dict]:
    return _github_get_json(f"{GITHUB_API}/repos/{repo}/releases/latest")


def _candidate_model_urls(base_url: str) -> list[str]:
    """Generate candidate URLs for the models endpoint."""
    stripped = base_url.rstrip("/")
    candidates = [f"{stripped}/models"]
    if "/v1" not in stripped:
        candidates.append(f"{stripped}/v1/models")
    return candidates


def _fetch_models(base_url: str, api_key: str) -> list[str]:
    """Fetch available models from OpenAI-compatible API."""
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    last_error = ""
    for url in _candidate_model_urls(base_url):
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
            models = data.get("data") if isinstance(data, dict) else None
            if isinstance(models, list):
                return [
                    str(item.get("id"))
                    for item in models
                    if isinstance(item, dict) and item.get("id")
                ]
            last_error = "Unexpected models payload"
        except httpx.HTTPStatusError as e:
            last_error = f"HTTP {e.response.status_code}: {e.response.text}"
        except Exception as e:
            last_error = str(e)
    raise HTTPException(status_code=400, detail=last_error or "Failed to fetch models")


@router.get("")
async def get_settings():
    """Get current settings (API key is masked)."""
    provider = settings_manager.get_provider()
    provider_keys = {
        key: {
            "has_key": settings_manager.has_api_key(key),
            "masked_key": settings_manager.get_masked_api_key(key),
        }
        for key in PROVIDERS
    }
    provider_settings = settings_manager.get_provider_settings()
    return {
        "active_provider": provider,
        "provider_keys": provider_keys,
        "provider_settings": provider_settings,
        "has_api_key": settings_manager.has_api_key(provider),
        "masked_api_key": settings_manager.get_masked_api_key(provider),
        "base_url": settings_manager.get_base_url(provider),
        "model": settings_manager.get_model(provider),
        "citation_copy_format": settings_manager.get_citation_copy_format(),
    }


@router.get("/version")
async def get_version():
    """Get current application version."""
    return {"version": get_local_version()}


@router.post("/api-key")
async def save_api_key(req: ApiKeyRequest):
    """Save the provider API key."""
    api_key = req.api_key.strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="API key cannot be empty")
    provider = req.provider or settings_manager.get_provider()
    if provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail="Unsupported provider")
    settings_manager.set_api_key(api_key, provider)
    return {
        "success": True,
        "has_api_key": settings_manager.has_api_key(provider),
        "masked_api_key": settings_manager.get_masked_api_key(provider),
        "provider": provider,
    }


@router.delete("/api-key")
async def delete_api_key(provider: Optional[str] = None):
    """Remove the saved API key."""
    provider = provider or settings_manager.get_provider()
    if provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail="Unsupported provider")
    settings_manager.clear_api_key(provider)
    return {
        "success": True,
        "has_api_key": settings_manager.has_api_key(provider),
        "provider": provider,
    }


@router.post("/validate")
async def validate_api_key(req: ApiKeyValidateRequest):
    """Validate OpenAI-compatible API credentials and model selection."""
    config = settings_manager.get_chat_completions_config()
    api_key = (req.api_key or "").strip() if req else ""
    base_url = (req.base_url or "").strip() if req else ""
    model = (req.model or "").strip() if req else ""
    provider = (req.provider or "").strip() if req else ""
    provider = provider or settings_manager.get_provider()
    if provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail="Unsupported provider")

    if not api_key:
        api_key = settings_manager.get_api_key(provider)
        if not api_key:
            if not config:
                raise HTTPException(status_code=400, detail="No API key configured")
            api_key = config.api_key
    if not base_url:
        base_url = (
            settings_manager.get_base_url(provider)
            if provider
            else (config.base_url if config else "https://api.openai.com/v1")
        )
    if not model:
        model = (
            settings_manager.get_model(provider)
            if provider
            else (config.model if config else "")
        )

    candidates = _candidate_model_urls(base_url)

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    last_error = ""
    for url in candidates:
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
            return {"valid": True}
        except httpx.HTTPStatusError as e:
            last_error = f"HTTP {e.response.status_code}: {e.response.text}"
        except Exception as e:
            last_error = str(e)

    return {"valid": False, "error": last_error or "Validation failed"}


@router.post("/models")
async def list_models(req: ModelsListRequest):
    """List available models via OpenAI-compatible /models endpoint."""
    config = settings_manager.get_chat_completions_config()
    api_key = (req.api_key or "").strip() if req else ""
    base_url = (req.base_url or "").strip() if req else ""
    provider = (req.provider or "").strip() if req else ""
    provider = provider or settings_manager.get_provider()
    if provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail="Unsupported provider")

    if not api_key:
        api_key = settings_manager.get_api_key(provider)
        if not api_key:
            if not config:
                raise HTTPException(status_code=400, detail="No API key configured")
            api_key = config.api_key
    if not base_url:
        base_url = (
            settings_manager.get_base_url(provider)
            if provider
            else (config.base_url if config else "https://api.openai.com/v1")
        )

    models = _fetch_models(base_url, api_key)
    return {"models": models, "provider": provider}


@router.post("/llm")
async def save_llm_settings(req: LlmSettingsRequest):
    """Save OpenAI-compatible base URL and model name."""
    base_url = req.base_url.strip()
    model = req.model.strip()
    provider = req.provider or settings_manager.get_provider()
    if provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail="Unsupported provider")
    if not base_url:
        raise HTTPException(status_code=400, detail="Base URL cannot be empty")
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(
            status_code=400, detail="Base URL must be a valid http(s) URL"
        )
    if not model:
        raise HTTPException(status_code=400, detail="Model cannot be empty")

    normalized_url = base_url.rstrip("/")
    settings_manager.set_provider(provider)
    settings_manager.set_base_url(normalized_url, provider)
    settings_manager.set_model(model, provider)
    return {
        "success": True,
        "base_url": normalized_url,
        "model": model,
        "active_provider": provider,
    }


@router.post("/citation-format")
async def save_citation_format(req: CitationFormatRequest):
    """Save the preferred citation format for copying AI responses."""
    fmt = req.format.strip().lower()
    valid_formats = ("apa", "mla", "chicago", "gbt7714", "numeric")
    if fmt not in valid_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid format. Must be one of: {', '.join(valid_formats)}",
        )
    settings_manager.set_citation_copy_format(fmt)
    return {"success": True, "citation_copy_format": fmt}


@router.post("/reset")
async def reset_all_data():
    """Clear all chunks, indexes, manifest, and chat sessions. Reference files remain untouched."""
    try:
        _, idx_dir = get_bank_paths()
        clear_bank_indexes(idx_dir)

        # CRITICAL: We do NOT touch files in references/ folder
        # Reference files are the user's primary data and must never be deleted

        return {
            "success": True,
            "message": "All metadata, indexes, and chat sessions cleared. Reference files preserved.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset data: {str(e)}")


@router.get("/update-check")
async def update_check():
    """Check GitHub for a newer version."""
    repo = get_repo_slug()
    repo_url = f"https://github.com/{repo}"
    current_version = get_local_version()
    result = {
        "repo": repo,
        "current": {"version": current_version},
        "latest": {"version": None, "url": None, "source": None},
        "is_update_available": False,
        "checked_at": int(time.time() * 1000),
        "error": None,
    }

    try:
        latest_release = _fetch_latest_release(repo)
        if latest_release:
            tag = latest_release.get("tag_name")
            version = normalize_version(tag)
            result["latest"] = {
                "version": version,
                "url": latest_release.get("html_url") or repo_url,
                "source": "release",
            }
    except Exception as e:
        result["error"] = str(e)

    latest_version = result["latest"]["version"]
    if latest_version and is_newer_version(latest_version, current_version):
        result["is_update_available"] = True

    return result


@router.get("/ocr")
async def get_ocr_settings():
    """Get OCR configuration and available models."""
    config = settings_manager.get_ocr_config()

    # Check installation status
    models_info = {}
    ocr_base_dir = settings_manager.index_dir / "models" / "ocr"

    for key, info in OCR_MODELS.items():
        # Create a copy to avoid mutating global state
        model_data = info.copy()
        
        # Check if installed
        model_dir = ocr_base_dir / key
        # We consider it installed if the directory exists and has files
        # A more robust check might verify specific files, but this is sufficient for now
        is_installed = model_dir.exists() and any(model_dir.iterdir())
        
        model_data["installed"] = is_installed
        models_info[key] = model_data

    return {
        "config": config,
        "models": models_info,
    }


@router.post("/ocr")
async def save_ocr_settings(req: OcrSettingsRequest):
    """Save OCR configuration."""
    config = {
        "model": req.model,
        "base_url": (req.base_url or DEFAULT_OCR_BASE_URL).strip() or DEFAULT_OCR_BASE_URL,
        "api_key": req.api_key,
    }
    settings_manager.set_ocr_config(config)
    return {"success": True, "config": config}


# Global progress tracker: {model_key: int} where int is 0-100, -1 for error, -2 for cancelled
download_progress: dict[str, int] = {}
# Download state: {model_key: "downloading" | "paused" | "cancelled"}
download_state: dict[str, str] = {}


async def _download_worker(
    model_key: str, download_url: str, target_file: Path, ocr_dir: Path
):
    try:
        download_progress[model_key] = 0
        download_state[model_key] = "downloading"
        
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", download_url, follow_redirects=True) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                with open(target_file, "wb") as f:
                    async for chunk in resp.aiter_bytes():
                        # Check for cancellation
                        state = download_state.get(model_key, "downloading")
                        if state == "cancelled":
                            raise Exception("Download cancelled by user")
                        
                        # Check for pause - wait until resumed
                        while download_state.get(model_key) == "paused":
                            import asyncio
                            await asyncio.sleep(0.5)
                            if download_state.get(model_key) == "cancelled":
                                raise Exception("Download cancelled by user")
                        
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            download_progress[model_key] = int((downloaded / total) * 90)

        # Check cancellation before extraction
        if download_state.get(model_key) == "cancelled":
            raise Exception("Download cancelled by user")

        # Extract (simulate last 10% for extraction)
        if filename := target_file.name:
            if filename.endswith(".tar") or filename.endswith(".tar.gz"):
                with tarfile.open(target_file, "r:*") as tar:
                    tar.extractall(path=ocr_dir)
            elif filename.endswith(".zip"):
                with zipfile.ZipFile(target_file, "r") as zip_ref:
                    zip_ref.extractall(ocr_dir)

        download_progress[model_key] = 100
        download_state[model_key] = "completed"

    except Exception as e:
        print(f"Download worker failed: {e}")
        if download_state.get(model_key) == "cancelled":
            download_progress[model_key] = -2  # Cancelled
        else:
            download_progress[model_key] = -1  # Error
        # Cleanup
        if target_file.exists():
            target_file.unlink()
        if ocr_dir.exists():
            shutil.rmtree(ocr_dir, ignore_errors=True)

def get_directory_size(path: Path) -> int:
    """Calculate total size of a directory recursively."""
    if not path.exists():
        return 0
    return sum(p.stat().st_size for p in path.rglob('*') if p.is_file())


def _hf_download_worker(model_key: str, repo_id: str, ocr_dir: Path):
    """
    Custom HF model downloader with true pause/resume/cancel support.
    Uses HF API to get file list and httpx for downloading with progress tracking.
    """
    import time
    import httpx
    from huggingface_hub import HfApi, hf_hub_url
    
    try:
        download_progress[model_key] = 0  # Initialize at 0
        download_state[model_key] = "downloading"
        
        # Get file list and sizes from HF API
        api = HfApi()
        try:
            # Try with files_metadata=True to get file sizes
            try:
                repo_info = api.repo_info(repo_id=repo_id, repo_type="model", files_metadata=True)
            except Exception:
                # Fallback for older versions or if files_metadata is not supported
                print("DEBUG: files_metadata=True failed, trying without")
                repo_info = api.repo_info(repo_id=repo_id, repo_type="model")
            
            files = repo_info.siblings  # List of RepoFile objects
        except Exception as e:
            print(f"Failed to get repo info: {e}")
            download_progress[model_key] = -1
            return
        
        if not files:
            print("No files found in repository")
            download_progress[model_key] = -1
            return
        
        
        # Calculate total size
        total_size = sum(f.size or 0 for f in files)
        print(f"DEBUG: Repo total size: {total_size} bytes, files: {len(files)}")
        
        # If total size is 0 (metadata missing), try to fetch via HEAD requests
        if total_size == 0 and files:
            print("DEBUG: Total size is 0, attempting to fetch sizes via HEAD requests...")
            import httpx
            with httpx.Client(timeout=10, follow_redirects=True) as client:
                for f in files:
                    try:
                        url = hf_hub_url(repo_id=repo_id, filename=f.rfilename, repo_type="model")
                        resp = client.head(url)
                        if "Content-Length" in resp.headers:
                            size = int(resp.headers["Content-Length"])
                            f.size = size  # Update file object
                            total_size += size
                            print(f"DEBUG: Fetched size for {f.rfilename}: {size}")
                    except Exception as e:
                        print(f"DEBUG: Failed to fetch size for {f.rfilename}: {e}")
            print(f"DEBUG: New total size: {total_size}")

        downloaded_size = 0
        
        # Create output directory
        ocr_dir.mkdir(parents=True, exist_ok=True)
        
        # Download each file
        for file_info in files:
            # Check for cancellation
            if download_state.get(model_key) == "cancelled":
                raise Exception("Download cancelled by user")
            
            # Handle pause
            while download_state.get(model_key) == "paused":
                time.sleep(0.5)
                if download_state.get(model_key) == "cancelled":
                    raise Exception("Download cancelled by user")
            
            filename = file_info.rfilename
            file_size = file_info.size or 0
            target_path = ocr_dir / filename
            
            # Create parent directories if needed
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Skip if already fully downloaded
            if target_path.exists() and target_path.stat().st_size == file_size:
                downloaded_size += file_size
                if total_size > 0:
                    prog = int((downloaded_size / total_size) * 100)
                    download_progress[model_key] = min(prog, 99)
                print(f"DEBUG: Skipping {filename} (already downloaded). Progress: {download_progress[model_key]}%")
                continue
            
            print(f"DEBUG: Downloading {filename} (size: {file_size})")
            
            # Get download URL
            url = hf_hub_url(repo_id=repo_id, filename=filename, repo_type="model")
            
            # Download with resume support
            file_downloaded = 0
            if target_path.exists():
                file_downloaded = target_path.stat().st_size
                # Add existing partial size to total downloaded
                downloaded_size += file_downloaded
                print(f"DEBUG: Resuming {filename} from {file_downloaded} bytes")
            
            headers = {}
            if file_downloaded > 0:
                headers["Range"] = f"bytes={file_downloaded}-"
            
            with httpx.Client(timeout=None, follow_redirects=True) as client:
                with client.stream("GET", url, headers=headers) as resp:
                    if resp.status_code == 416:
                        # Range not satisfiable = file complete
                        if target_path.exists():
                            # Re-verify size to be sure, or just count what we have
                            current_size = target_path.stat().st_size
                             # Fix up downloaded_size if needed (we already added file_downloaded)
                            # Logic: we added file_downloaded. If 416, we add 0. 
                            # If file_downloaded < file_size, we are missing data but server says range invalid.
                            # Just continue.
                            print(f"DEBUG: Range not satisfiable for {filename}, assuming complete.")
                            pass
                    
                    elif resp.status_code in (200, 206):
                        mode = "ab" if file_downloaded > 0 else "wb"
                        with open(target_path, mode) as f:
                            last_log_time = time.time()
                            for chunk in resp.iter_bytes(chunk_size=65536):
                                # Check cancellation
                                if download_state.get(model_key) == "cancelled":
                                    raise Exception("Download cancelled by user")
                                
                                # Handle pause
                                while download_state.get(model_key) == "paused":
                                    time.sleep(0.5)
                                    if download_state.get(model_key) == "cancelled":
                                        raise Exception("Download cancelled by user")
                                
                                f.write(chunk)
                                downloaded_size += len(chunk)
                                
                                # Update progress every 0.5s to avoid too many writes
                                if time.time() - last_log_time > 0.5:
                                    if total_size > 0:
                                        progress = int((downloaded_size / total_size) * 100)
                                        download_progress[model_key] = min(progress, 99)
                                    last_log_time = time.time()
        
        # Final check for cancellation
        if download_state.get(model_key) == "cancelled":
            raise Exception("Download cancelled by user")
        
        download_progress[model_key] = 100
        download_state[model_key] = "completed"
        print(f"DEBUG: Download completed for {model_key}")
        
    except Exception as e:
        print(f"HF Download worker failed: {e}")
        if download_state.get(model_key) == "cancelled":
            download_progress[model_key] = -2  # Cancelled
        else:
            download_progress[model_key] = -1  # Error
        # Cleanup on cancel/error
        if ocr_dir.exists():
            shutil.rmtree(ocr_dir, ignore_errors=True)


@router.post("/ocr/download")
async def download_ocr_model(
    req: OcrDownloadModelRequest, background_tasks: BackgroundTasks
):
    model_key = req.model
    if model_key not in OCR_MODELS:
        raise HTTPException(status_code=400, detail="Invalid model key")

    model_info = OCR_MODELS[model_key]
    download_url = model_info.get("download_url")
    hf_repo_id = model_info.get("hf_repo_id")
    
    if not download_url and not hf_repo_id:
        raise HTTPException(
            status_code=400, detail="Model does not support direct download"
        )

    # Check if already downloading or done (optional, but good for UX)
    current_progress = download_progress.get(model_key)
    if current_progress is not None and 0 <= current_progress < 100:
        return {"success": True, "message": "Download already in progress"}

    ocr_dir = settings_manager.index_dir / "models" / "ocr" / model_key
    
    # Clean start
    if ocr_dir.exists():
        shutil.rmtree(ocr_dir)
        
    ocr_dir.mkdir(parents=True, exist_ok=True)

    # Start appropriate background task
    if hf_repo_id:
        # HF models use custom downloader in background task
        background_tasks.add_task(_hf_download_worker, model_key, hf_repo_id, ocr_dir)
    else:
        if not isinstance(download_url, str) or not download_url:
            raise HTTPException(status_code=400, detail="Invalid model download URL")
        # Direct URL download
        filename = model_info.get("filename", "model.tar")
        target_file = ocr_dir / filename
        background_tasks.add_task(
            _download_worker, model_key, download_url, target_file, ocr_dir
        )

    return {
        "success": True,
        "message": f"Started download for {model_info['label']}",
    }


@router.delete("/ocr/models/{model_key}")
async def delete_ocr_model(model_key: str):
    """Delete a downloaded OCR model."""
    if model_key not in OCR_MODELS:
        raise HTTPException(status_code=400, detail="Invalid model key")

    ocr_dir = settings_manager.index_dir / "models" / "ocr" / model_key
    
    if not ocr_dir.exists():
        return {"success": True, "message": "Model not found (already deleted)"}

    try:
        shutil.rmtree(ocr_dir)
        # Also clear any progress
        if model_key in download_progress:
            del download_progress[model_key]
            
        return {"success": True, "message": f"Deleted model {model_key}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete model: {str(e)}")


@router.get("/ocr/download/status")
async def get_download_status(model: str):
    """Get the download progress and state for a specific model."""
    progress = download_progress.get(model)
    state = download_state.get(model, "idle")
    if progress is None:
        return {"progress": None, "state": "idle"}
    return {"progress": progress, "state": state}


@router.post("/ocr/download/pause")
async def pause_ocr_download(req: OcrDownloadModelRequest):
    """Pause an ongoing download."""
    model_key = req.model
    if model_key not in OCR_MODELS:
        raise HTTPException(status_code=400, detail="Invalid model key")
    
    current_state = download_state.get(model_key)
    if current_state != "downloading":
        return {"success": False, "message": "Download is not active"}
    
    download_state[model_key] = "paused"
    return {"success": True, "message": f"Download paused for {model_key}"}


@router.post("/ocr/download/resume")
async def resume_ocr_download(req: OcrDownloadModelRequest):
    """Resume a paused download."""
    model_key = req.model
    if model_key not in OCR_MODELS:
        raise HTTPException(status_code=400, detail="Invalid model key")
    
    current_state = download_state.get(model_key)
    if current_state != "paused":
        return {"success": False, "message": "Download is not paused"}
    
    download_state[model_key] = "downloading"
    return {"success": True, "message": f"Download resumed for {model_key}"}


@router.post("/ocr/download/cancel")
async def cancel_ocr_download(req: OcrDownloadModelRequest):
    """Cancel an ongoing or paused download and cleanup."""
    model_key = req.model
    if model_key not in OCR_MODELS:
        raise HTTPException(status_code=400, detail="Invalid model key")
    
    current_state = download_state.get(model_key)
    if current_state not in ("downloading", "paused"):
        return {"success": False, "message": "No active download to cancel"}
    
    # Set cancellation state - the download worker will detect this and stop
    download_state[model_key] = "cancelled"
    download_progress[model_key] = -2
    
    # Give the worker a moment to detect cancellation and cleanup
    import asyncio
    await asyncio.sleep(0.5)
    
    # Immediately cleanup the download directory
    ocr_dir = settings_manager.index_dir / "models" / "ocr" / model_key
    if ocr_dir.exists():
        try:
            shutil.rmtree(ocr_dir, ignore_errors=True)
        except Exception as e:
            print(f"Failed to cleanup cancelled download: {e}")
    
    return {"success": True, "message": f"Download cancelled and cleaned up for {model_key}"}
