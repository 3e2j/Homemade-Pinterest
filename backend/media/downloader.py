import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import md5
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

import requests

from backend.media.utils import (
    compute_file_hash,
    load_json_file,
    path_to_output_rel,
    resolve_mapped_path,
    save_json_file,
)
from backend.paths import OUTPUT_DIR

MEDIA_ROOT_DIR = OUTPUT_DIR / "media"
IMAGE_DIR = MEDIA_ROOT_DIR / "images"
VIDEO_DIR = MEDIA_ROOT_DIR / "videos"
AVATAR_DIR = MEDIA_ROOT_DIR / "avatars"
URLS_CACHE_FILE = OUTPUT_DIR / ".seen_urls.json"

for folder in (IMAGE_DIR, VIDEO_DIR, AVATAR_DIR):
    folder.mkdir(parents=True, exist_ok=True)

VIDEO_EXTS = {".mp4", ".webm", ".mov"}
CONVERT_EXTS = {".jpg", ".jpeg", ".png"}
REQUEST_TIMEOUT_SECONDS = 10
MAX_THREADPOOL_WORKERS = 32
DOWNLOAD_STREAM_CHUNK = 8192

# Protect shared in-memory maps across threads
SHARED_LOCK = threading.Lock()


def media_target_folder(url: str) -> Path:
    ext = Path(urlparse(url).path).suffix.lower()
    return VIDEO_DIR if ext in VIDEO_EXTS else IMAGE_DIR


def canonical_media_filename(url: str) -> str:
    """Deterministic filename for a media URL (MD5 of URL).

    Normalizes common image extensions to ``.webp`` and video extensions to
    ``.mp4`` to match storage conventions.
    """
    if not url:
        return ""
    ext = Path(urlparse(url).path).suffix.lower()
    h = md5(url.encode()).hexdigest()
    if ext in CONVERT_EXTS:
        return f"{h}.webp"
    if ext in VIDEO_EXTS:
        return f"{h}.mp4"
    return f"{h}{ext}"


def load_url_cache() -> Dict[str, str]:
    """Load the URL -> filename map (avoids re-downloading identical URLs)."""
    data = load_json_file(URLS_CACHE_FILE, {})
    return data if isinstance(data, dict) else {}


def save_url_cache(url_map: Dict[str, str]) -> None:
    """Persist the URL -> filename mapping."""
    save_json_file(URLS_CACHE_FILE, url_map)


def download_single_file(
    url: str,
    folder: Path,
    hash_cache: Optional[Dict[str, str]] = None,
    url_cache: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """Download `url` into `folder` and return the relative stored path or None.

    - Uses MD5(url)+orig_ext as an intermediate download name.
    - Deduplicates by content hash via `hash_cache`; duplicate files are removed
      and mapped to the existing copy.
    - Updates `known_duplicates` under a lock to avoid races between threads.
    """
    if not url:
        return None

    # Fast-path: URL already resolved by another thread.
    if url_cache is not None:
        with SHARED_LOCK:
            mapped = url_cache.get(url)
        if isinstance(mapped, str) and resolve_mapped_path(mapped):
            return mapped

    final_name = canonical_media_filename(url)
    final_path = folder / final_name

    # File already exists on disk, no download needed.
    if final_path.exists():
        final_rel = path_to_output_rel(final_path)
        if url_cache is not None:
            with SHARED_LOCK:
                url_cache[url] = final_rel
        return final_rel

    # Download to an intermediate path using the raw URL extension.
    ext = Path(urlparse(url).path).suffix
    url_hash = md5(url.encode()).hexdigest()
    temp_path = folder / f"{url_hash}{ext}"
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS, stream=True)
        resp.raise_for_status()
        with temp_path.open("wb") as out_f:
            for chunk in resp.iter_content(chunk_size=DOWNLOAD_STREAM_CHUNK):
                if chunk:
                    out_f.write(chunk)
        print(f"[Download] Saved: {url} -> {temp_path.name}")
    except Exception as e:
        print(f"[Download] Failed: {url} ({e})")
        return None

    final_rel = path_to_output_rel(temp_path)

    if hash_cache is None:
        if url_cache is not None:
            with SHARED_LOCK:
                url_cache[url] = final_rel
        return final_rel

    file_hash = compute_file_hash(temp_path)
    if file_hash:
        with SHARED_LOCK:
            if file_hash not in hash_cache:
                hash_cache[file_hash] = final_rel
                if url_cache is not None:
                    url_cache[url] = final_rel
                return final_rel

            # Duplicate content found
            existing_name = hash_cache[file_hash]
            if not resolve_mapped_path(existing_name):
                # Existing file missing from disk; claim this slot
                hash_cache[file_hash] = final_rel
                if url_cache is not None:
                    url_cache[url] = final_rel
                return final_rel

            # Remove duplicate, point to existing
            try:
                temp_path.unlink()
            except Exception as e:
                print(f"[Duplicate] Failed to remove {temp_path.name}: {e}")
            if url_cache is not None:
                url_cache[url] = existing_name
            return existing_name

    if url_cache is not None:
        with SHARED_LOCK:
            url_cache[url] = final_rel
    return final_rel


def download_bulk_media(
    url_folder_pairs: List[tuple],
    hash_cache: Optional[Dict[str, str]] = None,
    max_workers: Optional[int] = None,
) -> Dict[str, Optional[str]]:
    """Download unique URLs from `url_folder_pairs` using a thread pool.

    Returns a map of url -> relative filename (None on failure). Each unique
    URL is downloaded at most once.
    """
    if not url_folder_pairs:
        return {}

    if max_workers is None:
        cpu = os.cpu_count() or 4
        max_workers = min(MAX_THREADPOOL_WORKERS, cpu * 4)

    url_cache = load_url_cache()

    # Deduplicate input; keep first-seen folder for each URL.
    unique_pairs: Dict[str, Path] = {}
    for url, folder in url_folder_pairs:
        if url:
            unique_pairs.setdefault(url, folder)

    results: Dict[str, Optional[str]] = {}
    with ThreadPoolExecutor(
        max_workers=min(max_workers, max(1, len(unique_pairs)))
    ) as executor:
        futures = {
            executor.submit(
                download_single_file, url, folder, hash_cache, url_cache
            ): url
            for url, folder in unique_pairs.items()
        }
        for future in as_completed(futures):
            url = futures[future]
            results[url] = future.result()

    save_url_cache(url_cache)
    print("[Download] media download complete")
    return results
