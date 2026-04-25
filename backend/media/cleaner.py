"""Media cleanup: orphan removal and deduplication."""

import json
from hashlib import md5
from pathlib import Path
from typing import Optional

from backend.media.config import (
    AVATAR_DIR,
    CONVERT_EXTS,
    IMAGE_DIR,
    JSON_FILE,
    MAX_MEDIA_PER_TWEET,
    MEDIA_HASH_CACHE,
    VIDEO_DIR,
    VIDEO_EXTS,
)
from backend.media.utils import (
    compute_file_hash,
    path_to_output_rel,
    save_json_file,
)


def _referenced_filenames() -> set:
    """Build set of filenames currently referenced by tweets JSON."""
    referenced = set()
    if not JSON_FILE.exists():
        return referenced

    try:
        with open(JSON_FILE, encoding="utf8") as f:
            tweets = json.load(f)
        for t in tweets:
            av = t.get("user_avatar_url")
            if av:
                referenced.add(_filename_from_url(av, AVATAR_DIR))
            for url in t.get("tweet_media_urls", [])[:MAX_MEDIA_PER_TWEET]:
                referenced.add(_filename_from_url(url))
    except Exception as e:
        print(f"[Cleanup] Failed to compute referenced media: {e}")
    return referenced


def _filename_from_url(url: str, folder: Optional[Path] = None) -> str:
    """Get canonical filename for a URL."""
    ext = Path(url).suffix.lower()
    h = md5(url.encode()).hexdigest()
    if ext in CONVERT_EXTS:
        filename = f"{h}.webp"
    else:
        filename = f"{h}{ext}"
    target_folder = folder or (VIDEO_DIR if ext in VIDEO_EXTS else IMAGE_DIR)
    return path_to_output_rel(target_folder / filename)


def _remove_orphans() -> int:
    """Remove files not referenced by tweets JSON. Returns count removed."""
    referenced = _referenced_filenames()
    orphans_removed = 0

    for folder in (IMAGE_DIR, VIDEO_DIR, AVATAR_DIR):
        for file_path in list(folder.iterdir()):
            if not file_path.is_file():
                continue
            rel_path = path_to_output_rel(file_path)
            if referenced and (rel_path not in referenced):
                try:
                    file_path.unlink()
                    orphans_removed += 1
                except Exception as e:
                    print(f"[Cleanup] Failed to remove {file_path.name}: {e}")

    return orphans_removed


def _deduplicate_by_content() -> tuple:
    """Remove duplicate files by content hash. Returns (count_removed, hash_map)."""
    hash_map = {}
    seen_hashes = {}
    duplicates_removed = 0

    for folder in (IMAGE_DIR, VIDEO_DIR, AVATAR_DIR):
        for file_path in list(folder.iterdir()):
            if not file_path.is_file():
                continue
            try:
                file_hash = compute_file_hash(file_path)
            except Exception:
                file_hash = ""

            if not file_hash:
                continue

            if file_hash in seen_hashes:
                kept_name = seen_hashes[file_hash]
                try:
                    removed_name = path_to_output_rel(file_path)
                    file_path.unlink()
                    duplicates_removed += 1
                    print(
                        f"[Cleanup] Removed {removed_name} (duplicate of {kept_name})"
                    )
                except Exception as e:
                    print(
                        f"[Cleanup] Failed to remove {path_to_output_rel(file_path)}: {e}"
                    )
                continue

            rel_name = path_to_output_rel(file_path)
            seen_hashes[file_hash] = rel_name
            hash_map[file_hash] = rel_name

    return duplicates_removed, hash_map


def cleanup() -> None:
    """Remove orphaned files, dedupe identical files, and rebuild caches."""
    orphans = _remove_orphans()
    if orphans:
        print(f"[Cleanup] Removed {orphans} unreferenced files.")

    dupes, hash_map = _deduplicate_by_content()
    save_json_file(MEDIA_HASH_CACHE, hash_map)
    if dupes:
        print(f"[Cleanup] Removed {dupes} duplicates.")
