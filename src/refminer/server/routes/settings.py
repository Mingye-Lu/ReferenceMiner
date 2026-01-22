"""Settings management endpoints."""
from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException

from refminer.server.globals import settings_manager, get_bank_paths
from refminer.server.models import (
    ApiKeyRequest,
    ApiKeyValidateRequest,
    LlmSettingsRequest,
    ModelsListRequest,
)
from refminer.server.utils import clear_bank_indexes

router = APIRouter(prefix="/api/settings", tags=["settings"])

PROVIDERS = ("deepseek", "openai", "gemini", "anthropic", "custom")


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
                return [str(item.get("id")) for item in models if isinstance(item, dict) and item.get("id")]
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
    }


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
    return {"success": True, "has_api_key": settings_manager.has_api_key(provider), "provider": provider}


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
        base_url = settings_manager.get_base_url(provider) if provider else (config.base_url if config else "https://api.openai.com/v1")
    if not model:
        model = settings_manager.get_model(provider) if provider else (config.model if config else "")

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
        base_url = settings_manager.get_base_url(provider) if provider else (config.base_url if config else "https://api.openai.com/v1")

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
        raise HTTPException(status_code=400, detail="Base URL must be a valid http(s) URL")
    if not model:
        raise HTTPException(status_code=400, detail="Model cannot be empty")

    normalized_url = base_url.rstrip("/")
    settings_manager.set_provider(provider)
    settings_manager.set_base_url(normalized_url, provider)
    settings_manager.set_model(model, provider)
    return {"success": True, "base_url": normalized_url, "model": model, "active_provider": provider}


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
