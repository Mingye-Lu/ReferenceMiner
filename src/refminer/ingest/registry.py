from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from refminer.utils.paths import get_index_dir


@dataclass
class HashRegistry:
    """Registry mapping SHA256 hashes to file paths for duplicate detection."""
    by_hash: dict[str, str] = field(default_factory=dict)  # sha256 -> rel_path
    by_path: dict[str, str] = field(default_factory=dict)  # rel_path -> sha256


def _registry_path(root: Path | None = None, index_dir: Path | None = None) -> Path:
    # Hash registry belongs to the index, but we often associate it with the project folder.
    # In the decoupled layout, we use the index folder for consistency.
    idx_dir = index_dir or get_index_dir(root)
    return idx_dir / "hash_registry.json"


def load_registry(root: Path | None = None, index_dir: Path | None = None, references_dir: Path | None = None) -> HashRegistry:
    """Load hash registry from disk. Returns empty registry if file doesn't exist."""
    path = _registry_path(root, index_dir=index_dir)
    if not path.exists():
        return HashRegistry()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return HashRegistry(
            by_hash=data.get("by_hash", {}),
            by_path=data.get("by_path", {}),
        )
    except (json.JSONDecodeError, KeyError):
        return HashRegistry()


def save_registry(registry: HashRegistry, root: Path | None = None, index_dir: Path | None = None, references_dir: Path | None = None) -> None:
    """Save hash registry to disk."""
    path = _registry_path(root, index_dir=index_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "by_hash": registry.by_hash,
        "by_path": registry.by_path,
    }
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def check_duplicate(sha256: str, registry: HashRegistry) -> Optional[str]:
    """Check if a file with this hash already exists. Returns existing rel_path or None."""
    return registry.by_hash.get(sha256)


def register_file(rel_path: str, sha256: str, registry: HashRegistry) -> None:
    """Register a file's hash in the registry."""
    registry.by_hash[sha256] = rel_path
    registry.by_path[rel_path] = sha256


def unregister_file(rel_path: str, registry: HashRegistry) -> None:
    """Remove a file from the registry."""
    sha256 = registry.by_path.pop(rel_path, None)
    if sha256:
        registry.by_hash.pop(sha256, None)


def init_registry_from_manifest(root: Path | None = None) -> HashRegistry:
    """Initialize registry from existing manifest.json (migration helper)."""
    from refminer.ingest.manifest import load_manifest

    registry = HashRegistry()
    try:
        manifest = load_manifest(root)
        for entry in manifest:
            register_file(entry.rel_path, entry.sha256, registry)
    except FileNotFoundError:
        pass
    return registry
