"""Shared utilities for media operations."""

import json
from hashlib import md5
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from backend.settings import (
    COMPATIBLE_WEBP_EXTS,
    HASH_CHUNK_SIZE,
    MEDIA_DIRS,
    MEDIA_ROOT_DIR,
    OUTPUT_DIR,
    VIDEO_EXTS,
)


def load_json_file(path: Path, default: Any):
    """Load JSON from path or return default on any error."""
    if path.exists():
        try:
            with open(path, "r", encoding="utf8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load {path}: {e}")
    return default


def save_json_file(path: Path, data: Any):
    """Write data as JSON to path."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf8") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"Failed to save {path}: {e}")


def compute_file_hash(filepath: Path, chunk_size: int = HASH_CHUNK_SIZE) -> str:
    """Return MD5 hex digest for filepath."""
    h = md5()
    try:
        with filepath.open("rb") as f:
            while chunk := f.read(chunk_size):
                h.update(chunk)
        return h.hexdigest()
    except Exception as e:
        print(f"Failed to hash {filepath}: {e}")
        return ""


def path_to_output_rel(filepath: Path) -> str:
    """Convert filepath to output-relative path string."""

    return filepath.resolve().relative_to(OUTPUT_DIR.resolve()).as_posix()


def resolve_mapped_path(mapped: str) -> Optional[Path]:
    """Resolve cached path string to actual filesystem path."""

    if not mapped:
        return None

    mapped_path = Path(mapped)
    if mapped_path.is_absolute():
        return mapped_path if mapped_path.exists() else None

    direct = (OUTPUT_DIR / mapped_path).resolve()
    if direct.exists():
        return direct

    media_rel = (MEDIA_ROOT_DIR / mapped_path).resolve()
    if media_rel.exists():
        return media_rel

    for folder in MEDIA_DIRS:
        candidate = folder / mapped
        if candidate.exists():
            return candidate

    return None


def get_media_type(url: str) -> str:
    """Determine media type (images/videos/avatars) from URL."""

    ext = Path(urlparse(url).path).suffix.lower()
    if ext in VIDEO_EXTS:
        return "videos"
    elif ext in COMPATIBLE_WEBP_EXTS:
        return "images"
    return "images"


def url_to_filename(url: str) -> str:
    """Extract original filename from URL (last part of path)."""

    if not url:
        return ""
    path = urlparse(url).path
    return Path(path).name or "unknown"
