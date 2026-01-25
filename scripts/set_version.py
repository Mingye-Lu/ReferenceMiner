#!/usr/bin/env python
"""Set version across all package files."""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

VERSION_FILES = [
    ROOT / "package.json",
    ROOT / "frontend" / "package.json",
    ROOT / "installer" / "package.json",
]

PYTHON_VERSION_FILE = ROOT / "src" / "refminer" / "version.py"


def update_json(path: Path, version: str) -> None:
    """Update version in a package.json file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    old = data.get("version", "unknown")
    data["version"] = version
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"  {path.relative_to(ROOT)}: {old} -> {version}")


def update_python(path: Path, version: str) -> None:
    """Update APP_VERSION in version.py."""
    content = path.read_text(encoding="utf-8")
    old_match = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', content)
    old = old_match.group(1) if old_match else "unknown"
    new_content = re.sub(
        r'APP_VERSION\s*=\s*"[^"]+"',
        f'APP_VERSION = "{version}"',
        content,
    )
    path.write_text(new_content, encoding="utf-8")
    print(f"  {path.relative_to(ROOT)}: {old} -> {version}")


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python set_version.py <version>")
        print("Example: python set_version.py 1.0.0")
        sys.exit(1)

    version = sys.argv[1]

    # Basic semver validation
    if not re.match(r"^\d+\.\d+\.\d+(-[\w.]+)?$", version):
        print(f"Error: Invalid version format '{version}'")
        print("Expected format: X.Y.Z or X.Y.Z-suffix")
        sys.exit(1)

    print(f"Setting version to {version}:\n")

    # Update Python version
    update_python(PYTHON_VERSION_FILE, version)

    # Update JSON files
    for path in VERSION_FILES:
        if path.exists():
            update_json(path, version)
        else:
            print(f"  {path.relative_to(ROOT)}: SKIPPED (not found)")

    print("\nDone. Run build.bat to rebuild.")


if __name__ == "__main__":
    main()
