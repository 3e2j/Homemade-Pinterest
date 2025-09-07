"""parse_media.py
==================

Minimal helpers to download, normalize, and deduplicate tweet media.

Outputs: files under ``output/images`` and a compact ``output/data.json``.

Key decisions:
- Filenames = MD5(URL) for determinism.
- Convert common rasters (.jpg/.png) to .webp to reduce disk usage.
- Maintain two small on-disk caches: file-hash->filename and url->filename.
"""

import json
import requests
from pathlib import Path
from urllib.parse import urlparse
from hashlib import md5
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import sys
from typing import Dict, List, Optional, Any
import threading

# --- Configuration ---
CONFIG_FILE = "config.json"
OUTPUT_DIR = Path("output")
JSON_FILE = OUTPUT_DIR / "liked_tweets.json"
MEDIA_DIR = OUTPUT_DIR / "images/media"
AVATAR_DIR = OUTPUT_DIR / "images/avatars"
MEDIA_HASH_CACHE = OUTPUT_DIR / ".media_hashes.json"
DUPLICATE_URLS_FILE = OUTPUT_DIR / ".duplicate_urls.json"
PROCESSED_JSON = OUTPUT_DIR / "data.json"

for folder in (MEDIA_DIR, AVATAR_DIR):
    # Create output directories up-front so code can assume they exist.
    folder.mkdir(parents=True, exist_ok=True)

try:
    with open(CONFIG_FILE, encoding="utf8") as f:
        config = json.load(f)
except Exception as e:
    print(f"Failed to load {CONFIG_FILE}: {e}")
    sys.exit(1)

DOWNLOAD_IMAGES = config.get("DOWNLOAD_IMAGES", True)

# --- Constants ---
# Extensions we convert to WebP (others are preserved as-is).
CONVERT_EXTS = {'.jpg', '.jpeg', '.png'}

# Tuning: quality, timeouts and IO chunk sizes
WEBP_QUALITY = 60
REQUEST_TIMEOUT_SECONDS = 10
MAX_MEDIA_PER_TWEET = 4
HASH_CHUNK_SIZE = 65536
WEBP_METHOD = 6  # Pillow webp 'method' (0-6): higher may be slower but smaller
MAX_THREADPOOL_WORKERS = 32
DOWNLOAD_STREAM_CHUNK = 8192

# Protect shared in-memory maps (hash cache, duplicate map) across threads
SHARED_LOCK = threading.Lock()

# --- Utilities ---
def load_json_file(path: Path, default: Any):
    """Load JSON from `path` or return `default` on any error."""
    if path.exists():
        try:
            with open(path, "r", encoding="utf8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[LoadJSON] Failed to load {path}: {e}")
    return default

def save_json_file(path: Path, data: Any):
    """Write `data` as JSON to `path`. Logs failures instead of raising."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf8") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"[SaveJSON] Failed to save {path}: {e}")

def compute_file_hash(filepath: Path, chunk_size: int = HASH_CHUNK_SIZE) -> str:
    """Return MD5 hex digest for `filepath` or empty string on error.

    Reads the file in chunks to avoid high memory use.
    """
    h = md5()
    try:
        with filepath.open("rb") as f:
            while chunk := f.read(chunk_size):
                h.update(chunk)
        return h.hexdigest()
    except Exception as e:
        print(f"[Hash] Failed to hash {filepath}: {e}")
        return ""

def convert_to_webp(filepath: Path, quality: int = WEBP_QUALITY) -> Path:
    """Convert `filepath` to WebP and remove the original on success.

    Returns the path to the WebP file, or the original path on failure.
    """
    webp_path = filepath.with_suffix(".webp")
    if webp_path.exists():
        return webp_path
    try:
        with Image.open(filepath) as img:
            img.save(webp_path, "webp", quality=quality, method=WEBP_METHOD)
        filepath.unlink()
        return webp_path
    except Exception as e:
        print(f"[WebP] Failed to convert {filepath} to webp: {e}")
        return filepath

# --- Filename Canonicalization ---
def canonical_media_filename(url: str) -> str:
    """Deterministic filename for a media URL (MD5 of URL).

    Normalizes common image extensions to ``.webp`` to match storage.
    """
    if not url:
        return ""
    ext = Path(urlparse(url).path).suffix.lower()
    h = md5(url.encode()).hexdigest()
    return f"{h}.webp" if ext in CONVERT_EXTS else f"{h}{ext}"

# --- Hash & Duplicate Management ---
def load_hash_cache() -> Dict[str, str]:
    """Load the content-hash -> filename cache used for deduplication."""
    return load_json_file(MEDIA_HASH_CACHE, {})

def save_hash_cache(hash_map: Dict[str, str]):
    """Save the hash->filename cache to disk."""
    save_json_file(MEDIA_HASH_CACHE, hash_map)

def load_duplicate_urls() -> Dict[str, str]:
    """Load the URL -> filename map (avoids re-downloading identical URLs)."""
    data = load_json_file(DUPLICATE_URLS_FILE, {})
    return data if isinstance(data, dict) else {}

def save_duplicate_urls(url_map: Dict[str, str]):
    """Persist the URL->filename mapping."""
    save_json_file(DUPLICATE_URLS_FILE, url_map)

def full_cleanup() -> None:
    """Remove orphaned files, dedupe identical files, and rebuild caches.

    This is tolerant: errors are logged and the process continues.
    """
    if not DOWNLOAD_IMAGES:
        return

    # Build referenced filenames set from JSON (if available)
    referenced_files = set()
    if JSON_FILE.exists():
        try:
            with open(JSON_FILE, encoding="utf8") as f:
                tweets = json.load(f)
            for t in tweets:
                av = t.get("user_avatar_url")
                if av:
                    referenced_files.add(canonical_media_filename(av))
                for url in t.get("tweet_media_urls", [])[:MAX_MEDIA_PER_TWEET]:
                    referenced_files.add(canonical_media_filename(url))
        except Exception as e:
            print(f"[UnreferencedFiles] Failed to compute referenced media: {e}")

    # First pass: remove files not referenced by the tweets JSON (if available)
    orphans_removed = 0
    for folder in (MEDIA_DIR, AVATAR_DIR):
        for file_path in list(folder.iterdir()):
            if not file_path.is_file():
                continue
            if referenced_files and file_path.name not in referenced_files:
                try:
                    file_path.unlink()
                    orphans_removed += 1
                except Exception as e:
                    print(f"[UnreferencedFiles] Failed to remove {file_path.name}: {e}")

    if orphans_removed:
        print(f"[UnreferencedFiles] Removed {orphans_removed} unreferenced files.")

    # Second pass: dedupe by content-hash and rebuild hash cache
    hash_map = {}
    seen_hashes = {}
    duplicates_removed = 0
    removed_to_kept = {}  # map removed filename -> kept filename

    for folder in (MEDIA_DIR, AVATAR_DIR):
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
                # duplicate content -> remove this file and map to the canonical name
                kept_name = seen_hashes[file_hash]
                try:
                    removed_name = file_path.name
                    file_path.unlink()
                    duplicates_removed += 1
                    removed_to_kept[removed_name] = kept_name
                    print(f"[Duplicate] Removed {removed_name} (duplicate of {kept_name})")
                except Exception as e:
                    print(f"[Duplicate] Failed to remove {file_path.name}: {e}")
                continue
            # unique file
            seen_hashes[file_hash] = file_path.name
            hash_map[file_hash] = file_path.name

    save_hash_cache(hash_map)
    if duplicates_removed:
        print(f"[Duplicate] Removed {duplicates_removed} duplicates.")

    # Third: repair URL->filename mappings to reflect removed/kept files
    dup_map = load_duplicate_urls()
    changed = False
    for url, mapped in list(dup_map.items()):
        # If mapped was removed during dedupe, update to kept name
        if mapped in removed_to_kept:
            dup_map[url] = removed_to_kept[mapped]
            changed = True
        # If mapped no longer exists on disk, drop the mapping
        elif mapped and not ((MEDIA_DIR / mapped).exists() or (AVATAR_DIR / mapped).exists()):
            del dup_map[url]
            changed = True

    if changed:
        save_duplicate_urls(dup_map)

# --- Media Downloading (Threaded) ---
def download_single_file(url: str, folder: Path, convert: bool = True, hash_cache: Optional[Dict[str, str]] = None,
                         known_duplicates: Optional[Dict[str, str]] = None) -> Optional[str]:
    """Download `url` into `folder` and return the stored filename or None.

    Notes:
    - Uses an intermediate name (MD5(url)+orig_ext) for the download, then
      optionally converts to webp and moves to the canonical filename.
    - Uses `hash_cache` to dedupe identical content; updates `known_duplicates`
      under a lock to avoid races between threads.
    """
    if not url:
        return None

    # Fast-path: if another thread already recorded this URL, return it.
    if isinstance(known_duplicates, dict):
        with SHARED_LOCK:
            if known_duplicates.get(url):
                return known_duplicates[url]

    final_name = canonical_media_filename(url)
    ext = Path(urlparse(url).path).suffix
    hashed_name = md5(url.encode()).hexdigest()
    final_path = folder / final_name

    if final_path.exists():
        return final_name

    original_path = folder / f"{hashed_name}{ext}"
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS, stream=True)
        resp.raise_for_status()
        with original_path.open("wb") as out_f:
            for chunk in resp.iter_content(chunk_size=DOWNLOAD_STREAM_CHUNK):
                if chunk:
                    out_f.write(chunk)
        print(f"[Download] Saved: {url} -> {original_path.name}")
    except Exception as e:
        print(f"[Download] Failed: {url} ({e})")
        return None

    if convert and original_path.suffix.lower() in CONVERT_EXTS:
        final_path = convert_to_webp(original_path)

    if hash_cache is not None:
        file_hash = compute_file_hash(final_path)
        with SHARED_LOCK:
            if file_hash in hash_cache:
                try:
                    # Duplicate content: remove this copy and point to existing file
                    final_path.unlink()
                    existing_name = hash_cache[file_hash]
                    if isinstance(known_duplicates, dict):
                        known_duplicates[url] = existing_name
                    return existing_name
                except Exception as e:
                    print(f"[Duplicate] Failed to remove {final_path.name}: {e}")
            else:
                hash_cache[file_hash] = final_path.name

    return final_path.name


def download_bulk_media(url_folder_pairs: List[tuple], hash_cache: Optional[Dict[str, str]] = None,
                        max_workers: Optional[int] = None) -> Dict[str, Optional[str]]:
    """Download unique URLs from `url_folder_pairs` using a thread pool.

    Returns a map url->filename (None on failure). Avoids downloading the same
    URL multiple times by using a local unique set.
    """
    if not url_folder_pairs:
        return {}

    # normalize max_workers
    if max_workers is None:
        cpu = os.cpu_count() or 4
        max_workers = min(MAX_THREADPOOL_WORKERS, cpu * 4)

    known_duplicates = load_duplicate_urls()
    results: Dict[str, Optional[str]] = {}

    # Deduplicate input URLs; keep first-seen target folder for each URL.
    unique_pairs = {}
    for url, folder in url_folder_pairs:
        if not url:
            continue
        unique_pairs.setdefault(url, folder)

    with ThreadPoolExecutor(max_workers=min(max_workers, max(1, len(unique_pairs)))) as executor:
        futures = {executor.submit(download_single_file, url, folder, True, hash_cache, known_duplicates): url
                   for url, folder in unique_pairs.items()}

        for future in as_completed(futures):
            url = futures[future]
            results[url] = future.result()

    save_duplicate_urls(known_duplicates)
    return results

# --- Tweet Processing ---
def process_tweets(tweets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Simplify raw tweet records and optionally download referenced media.

    Returns a list of processed dicts with stable filenames for media.
    """
    processed = []
    hash_cache = load_hash_cache() if DOWNLOAD_IMAGES else None

    # Collect URLs and corresponding target folders for a single bulk download.
    all_url_pairs: List[tuple] = []
    tweets_with_media: List[tuple] = []  # (idx, tweet, media_urls, avatar_url)

    for idx, tweet in enumerate(tweets):
        media_urls = tweet.get("tweet_media_urls", [])[:MAX_MEDIA_PER_TWEET]
        if not media_urls:
            continue
        avatar_url = tweet.get("user_avatar_url", "")
        tweets_with_media.append((idx, tweet, media_urls, avatar_url))
        if DOWNLOAD_IMAGES:
            if avatar_url:
                all_url_pairs.append((avatar_url, AVATAR_DIR))
            all_url_pairs.extend([(url, MEDIA_DIR) for url in media_urls])

    downloaded_map: Dict[str, Optional[str]] = {}
    if DOWNLOAD_IMAGES and all_url_pairs:
        downloaded_map = download_bulk_media(all_url_pairs, hash_cache=hash_cache)

    for idx, tweet, media_urls, avatar_url in tweets_with_media:
        avatar_name = downloaded_map.get(avatar_url, avatar_url) if DOWNLOAD_IMAGES else avatar_url
        media_names = [downloaded_map.get(url, url) for url in media_urls] if DOWNLOAD_IMAGES else media_urls

        processed.append({
            "id": str(tweet.get("tweet_id") or idx),
            "avatar": avatar_name,
            "username": tweet.get("user_name", ""),
            "handle": tweet.get("user_handle", ""),
            "content": tweet.get("tweet_content", ""),
            "media": media_names,
            "is_video": any("video_thumb" in url for url in media_urls),
            "possibly_sensitive": tweet.get("possibly_sensitive", "")
        })

    if DOWNLOAD_IMAGES:
        save_hash_cache(hash_cache)
    return processed

# --- Main ---
def main() -> None:
    """Entry point: optionally clean, process liked tweets, and write `data.json`."""
    if DOWNLOAD_IMAGES:
        full_cleanup()

    with open(JSON_FILE, encoding="utf8") as f:
        tweets = json.load(f)

    processed_tweets = process_tweets(tweets)
    with open(PROCESSED_JSON, "w", encoding="utf8") as f:
        json.dump(processed_tweets, f)

    print(f"[Main] Processed tweets saved to {PROCESSED_JSON}")

if __name__ == "__main__":
    main()