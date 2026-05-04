"""Shared utilities for media operations."""

import json
from hashlib import md5
from pathlib import Path
from typing import Any, Optional

from backend.logger import error, warning
from backend.settings import (
    HASH_CHUNK_SIZE,
    MEDIA_DIRS,
    MEDIA_ROOT_DIR,
    OUTPUT_DIR,
)

# Ensure media directories exist
for folder in MEDIA_DIRS:
    folder.mkdir(parents=True, exist_ok=True)


def load_json_file(path: Path, default: Any):
    """Load JSON from path or return default on any error."""
    if path.exists():
        try:
            with open(path, "r", encoding="utf8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            error(f"Failed to parse JSON from {path}: {e}")
        except Exception as e:
            error(f"Failed to load {path}: {e}")
    return default


def save_json_file(path: Path, data: Any):
    """Write data as JSON to path."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        error(f"Failed to save {path}: {e}")


def compute_file_hash(filepath: Path, chunk_size: int = HASH_CHUNK_SIZE) -> str:
    """Return MD5 hex digest for filepath."""
    h = md5()
    try:
        with filepath.open("rb") as f:
            while chunk := f.read(chunk_size):
                h.update(chunk)
        return h.hexdigest()
    except Exception as e:
        error(f"Failed to hash {filepath}: {e}")
        return ""


def path_to_output_rel(filepath: Path) -> str:
    """Convert filepath to output-relative path string."""
    try:
        return filepath.resolve().relative_to(OUTPUT_DIR.resolve()).as_posix()
    except ValueError as e:
        error(f"Path {filepath} is not relative to {OUTPUT_DIR}: {e}")
        return ""


def _is_safe_path(path: Path, allowed_parent: Path) -> bool:
    """Check if path is within allowed_parent (prevents path traversal)."""
    try:
        path.resolve().relative_to(allowed_parent.resolve())
        return True
    except ValueError:
        return False


def resolve_mapped_path(mapped: str) -> Optional[Path]:
    """Resolve cached path string to actual filesystem path.

    Validates that resolved path is within OUTPUT_DIR to prevent path traversal attacks.
    """
    if not mapped:
        return None

    try:
        mapped_path = Path(mapped)

        # Prevent absolute paths outside OUTPUT_DIR
        if mapped_path.is_absolute():
            if _is_safe_path(mapped_path, OUTPUT_DIR) and mapped_path.exists():
                return mapped_path
            return None

        # Try output directory
        direct = (OUTPUT_DIR / mapped_path).resolve()
        if _is_safe_path(direct, OUTPUT_DIR) and direct.exists():
            return direct

        # Try media root
        media_rel = (MEDIA_ROOT_DIR / mapped_path).resolve()
        if _is_safe_path(media_rel, OUTPUT_DIR) and media_rel.exists():
            return media_rel

        # Try individual media folders
        for folder in MEDIA_DIRS:
            candidate = (folder / mapped).resolve()
            if _is_safe_path(candidate, OUTPUT_DIR) and candidate.exists():
                return candidate

        return None
    except Exception as e:
        warning(f"Error resolving path {mapped}: {e}")
        return None
