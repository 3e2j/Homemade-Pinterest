"""Shared utilities for media operations."""

import json
from hashlib import md5
from pathlib import Path
from typing import Any, Optional

HASH_CHUNK_SIZE = 65536


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
    from backend.paths import OUTPUT_DIR

    return filepath.resolve().relative_to(OUTPUT_DIR.resolve()).as_posix()


def resolve_mapped_path(mapped: str) -> Optional[Path]:
    """Resolve cached path string to actual filesystem path."""
    from backend.paths import OUTPUT_DIR

    if not mapped:
        return None

    mapped_path = Path(mapped)
    if mapped_path.is_absolute():
        return mapped_path if mapped_path.exists() else None

    direct = (OUTPUT_DIR / mapped_path).resolve()
    if direct.exists():
        return direct

    media_dirs = [
        OUTPUT_DIR / "media" / "images",
        OUTPUT_DIR / "media" / "videos",
        OUTPUT_DIR / "media" / "avatars",
    ]
    for folder in media_dirs:
        candidate = folder / mapped
        if candidate.exists():
            return candidate

    return None
