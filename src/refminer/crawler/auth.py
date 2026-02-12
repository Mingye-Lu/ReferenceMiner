"""Helpers for per-engine crawler authentication profiles."""

from __future__ import annotations

from typing import Any

SUPPORTED_CRAWLER_AUTH_TYPES = {
    "none",
    "cookie_header",
    "bearer",
    "api_key",
    "custom_headers",
}


def _normalize_headers(raw_headers: Any) -> dict[str, str]:
    if not isinstance(raw_headers, dict):
        return {}

    headers: dict[str, str] = {}
    for key, value in raw_headers.items():
        if not isinstance(key, str):
            continue
        name = key.strip()
        if not name:
            continue
        if value is None:
            continue
        header_value = str(value).strip()
        if not header_value:
            continue
        headers[name] = header_value
    return headers


def normalize_crawler_auth_profile(raw_profile: Any) -> dict[str, Any]:
    """Normalize a crawler auth profile into a predictable structure."""
    if not isinstance(raw_profile, dict):
        return {
            "auth_type": "none",
            "secret": None,
            "headers": {},
            "api_key_header": "X-API-Key",
            "updated_at": None,
        }

    auth_type = str(raw_profile.get("auth_type") or "none").strip().lower()
    if auth_type not in SUPPORTED_CRAWLER_AUTH_TYPES:
        auth_type = "none"

    secret_value = raw_profile.get("secret")
    secret = None
    if isinstance(secret_value, str):
        cleaned_secret = secret_value.strip()
        if cleaned_secret:
            secret = cleaned_secret

    headers = _normalize_headers(raw_profile.get("headers"))
    api_key_header = raw_profile.get("api_key_header")
    if not isinstance(api_key_header, str) or not api_key_header.strip():
        api_key_header = "X-API-Key"

    updated_at = raw_profile.get("updated_at")
    if not isinstance(updated_at, int):
        updated_at = None

    return {
        "auth_type": auth_type,
        "secret": secret,
        "headers": headers,
        "api_key_header": api_key_header.strip(),
        "updated_at": updated_at,
    }


def build_auth_headers(profile: dict[str, Any] | None) -> dict[str, str]:
    """Build HTTP headers from a normalized auth profile."""
    normalized = normalize_crawler_auth_profile(profile)
    headers = dict(normalized["headers"])
    auth_type = normalized["auth_type"]
    secret = normalized["secret"]

    if not secret:
        return headers

    if auth_type == "cookie_header":
        headers.setdefault("Cookie", secret)
    elif auth_type == "bearer":
        headers.setdefault("Authorization", f"Bearer {secret}")
    elif auth_type == "api_key":
        key_name = normalized.get("api_key_header") or "X-API-Key"
        headers.setdefault(str(key_name), secret)

    return headers


def mask_secret(secret: str | None) -> str | None:
    """Return a short masked display value for secrets."""
    if not secret:
        return None
    if len(secret) <= 7:
        return "*" * len(secret)
    return f"{secret[:3]}{'*' * 15}{secret[-4:]}"
