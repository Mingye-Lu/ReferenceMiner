"""Version and update helpers."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

from refminer.version import APP_REPO, APP_VERSION


def _read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _read_packed_ref(git_dir: Path, ref: str) -> Optional[str]:
    packed_refs = git_dir / "packed-refs"
    contents = _read_text(packed_refs)
    if not contents:
        return None
    for line in contents.splitlines():
        if not line or line.startswith("#") or line.startswith("^"):
            continue
        parts = line.split(" ", 1)
        if len(parts) == 2 and parts[1].strip() == ref:
            return parts[0].strip()
    return None


def read_git_commit(base_dir: Path) -> Optional[str]:
    """Read the current git commit hash if available."""
    git_dir = base_dir / ".git"
    head = _read_text(git_dir / "HEAD")
    if not head:
        return None
    if head.startswith("ref:"):
        ref = head.split(" ", 1)[1].strip()
        commit = _read_text(git_dir / ref)
        if commit:
            return commit
        return _read_packed_ref(git_dir, ref)
    return head


def get_local_commit(base_dir: Path) -> Optional[str]:
    """Resolve the local commit hash from env or git metadata."""
    env_commit = os.getenv("REFMINER_COMMIT")
    if env_commit:
        return env_commit.strip()
    return read_git_commit(base_dir)


def get_local_version() -> str:
    """Return the local app version string."""
    return APP_VERSION


def get_repo_slug() -> str:
    """Return the GitHub repo slug used for update checks."""
    return os.getenv("REFMINER_REPO", APP_REPO)


def normalize_version(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    version = value.strip()
    if version.lower().startswith("v"):
        version = version[1:]
    return version or None


def parse_version_tuple(value: Optional[str]) -> Optional[tuple[int, ...]]:
    if not value:
        return None
    numbers = re.findall(r"\d+", value)
    if not numbers:
        return None
    return tuple(int(n) for n in numbers[:4])


def is_newer_version(latest: Optional[str], current: Optional[str]) -> bool:
    latest_tuple = parse_version_tuple(latest)
    current_tuple = parse_version_tuple(current)
    if not latest_tuple or not current_tuple:
        return False
    length = max(len(latest_tuple), len(current_tuple))
    latest_tuple += (0,) * (length - len(latest_tuple))
    current_tuple += (0,) * (length - len(current_tuple))
    return latest_tuple > current_tuple
