import json
import requests
from pathlib import Path
from urllib.parse import urlparse
from hashlib import md5
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
from typing import Dict, List, Optional, Any

# --- Configuration ---
CONFIG_FILE = "config.json"
OUTPUT_DIR = Path("output")
JSON_FILE = OUTPUT_DIR / "liked_tweets.json"
MEDIA_DIR = OUTPUT_DIR / "images/media"
AVATAR_DIR = OUTPUT_DIR / "images/avatars"
MEDIA_HASH_CACHE = OUTPUT_DIR / ".media_hashes.json"
DUPLICATE_URLS_FILE = OUTPUT_DIR / ".duplicate_urls.json"
PROCESSED_JSON = OUTPUT_DIR / "data.json"

for folder in [MEDIA_DIR, AVATAR_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

try:
    with open(CONFIG_FILE, encoding="utf8") as f:
        config = json.load(f)
except Exception as e:
    print(f"Failed to load {CONFIG_FILE}: {e}")
    sys.exit(1)

DOWNLOAD_IMAGES = config.get("DOWNLOAD_IMAGES", True)

# --- Constants ---
CONVERT_EXTS = {'.jpg', '.jpeg', '.png'}
WEBP_QUALITY = 60
REQUEST_TIMEOUT_SECONDS = 10
MAX_MEDIA_PER_TWEET = 4
MAX_TWEET_DOWNLOAD_WORKERS = 1 + MAX_MEDIA_PER_TWEET  # avatar + media
HASH_CHUNK_SIZE = 65536

# --- Utilities ---
def load_json_file(path: Path, default: Any):
    if path.exists():
        try:
            with open(path, "r", encoding="utf8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[LoadJSON] Failed to load {path}: {e}")
    return default

def save_json_file(path: Path, data: Any):
    try:
        with open(path, "w", encoding="utf8") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"[SaveJSON] Failed to save {path}: {e}")

def compute_file_hash(filepath: Path, chunk_size: int = HASH_CHUNK_SIZE) -> str:
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
    webp_path = filepath.with_suffix(".webp")
    if webp_path.exists():
        return webp_path
    try:
        with Image.open(filepath) as img:
            img.save(webp_path, "webp", quality=quality, method=6)
        filepath.unlink()
        return webp_path
    except Exception as e:
        print(f"[WebP] Failed to convert {filepath} to webp: {e}")
        return filepath

# --- Filename Canonicalization ---
def canonical_media_filename(url: str) -> str:
    """Return the on-disk filename we would use for a given media URL.
    JPG/PNG become .webp, others keep their original extension.
    """
    if not url:
        return ""
    ext = Path(urlparse(url).path).suffix.lower()
    h = md5(url.encode()).hexdigest()
    if ext in CONVERT_EXTS:
        return f"{h}.webp"
    return f"{h}{ext}"

# --- Hash & Duplicate Management ---
def load_hash_cache() -> Dict[str, str]:
    return load_json_file(MEDIA_HASH_CACHE, {})

def save_hash_cache(hash_map: Dict[str, str]):
    save_json_file(MEDIA_HASH_CACHE, hash_map)

def load_duplicate_urls() -> Dict[str, str]:
    data = load_json_file(DUPLICATE_URLS_FILE, {})
    return data if isinstance(data, dict) else {}

def save_duplicate_urls(url_map: Dict[str, str]):
    save_json_file(DUPLICATE_URLS_FILE, url_map)

def refresh_media_cache() -> None:
    """Maintain media cache: remove orphan files, dedupe duplicates, rebuild hash map."""
    if not DOWNLOAD_IMAGES:
        return

    # Build set of referenced filenames by hashing URLs in liked_tweets.json
    referenced_files = set()
    if JSON_FILE.exists():
        try:
            with open(JSON_FILE, encoding="utf8") as f:
                tweets = json.load(f)
            for t in tweets:
                # avatar
                av = t.get("user_avatar_url")
                if av:
                    referenced_files.add(canonical_media_filename(av))
                # media urls (limit consistent with processing)
                for url in t.get("tweet_media_urls", [])[:MAX_MEDIA_PER_TWEET]:
                    referenced_files.add(canonical_media_filename(url))
        except Exception as e:
            print(f"[Cache] Failed to compute referenced media: {e}")

    hash_cache = {}
    duplicates_removed = 0
    orphans_removed = 0
    seen_hashes = {}

    for folder in (MEDIA_DIR, AVATAR_DIR):
        for file_path in list(folder.iterdir()):
            if not file_path.is_file():
                continue
            fname = file_path.name
            if referenced_files and fname not in referenced_files:
                try:
                    file_path.unlink()
                    orphans_removed += 1
                    continue
                except Exception as e:
                    print(f"[Orphan] Failed to remove {fname}: {e}")
            file_hash = compute_file_hash(file_path)
            if not file_hash:
                continue
            if file_hash in seen_hashes:
                try:
                    file_path.unlink()
                    duplicates_removed += 1
                    print(f"[Duplicate] Removed {fname} (duplicate of {seen_hashes[file_hash]})")
                except Exception as e:
                    print(f"[Duplicate] Failed to remove {fname}: {e}")
                continue
            seen_hashes[file_hash] = fname
            hash_cache[file_hash] = fname

    save_hash_cache(hash_cache)
    if duplicates_removed:
        print(f"[Duplicate] Removed {duplicates_removed} duplicates.")
    if orphans_removed:
        print(f"[Orphan] Removed {orphans_removed} unreferenced files.")

# --- Media Downloading (Threaded) ---
def download_single_file(url: str, folder: Path, convert: bool = True, hash_cache: Optional[Dict[str, str]] = None,
                         known_duplicates: Optional[Dict[str, str]] = None) -> Optional[str]:
    if not url:
        return None
    if isinstance(known_duplicates, dict) and url in known_duplicates and known_duplicates[url]:
        # Already known duplicate; return canonical filename
        return known_duplicates[url]

    final_name = canonical_media_filename(url)
    # Recover original ext for initial download before potential conversion
    ext = Path(urlparse(url).path).suffix
    hashed_name = md5(url.encode()).hexdigest()
    final_path = folder / final_name

    if final_path.exists():
        return final_name

    original_path = folder / f"{hashed_name}{ext}"
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
        original_path.write_bytes(resp.content)
        print(f"[Download] Saved: {url} -> {original_path.name}")
    except Exception as e:
        print(f"[Download] Failed: {url} ({e})")
        return None

    if convert and original_path.suffix.lower() in CONVERT_EXTS:
        final_path = convert_to_webp(original_path)

    if hash_cache:
        file_hash = compute_file_hash(final_path)
        if file_hash in hash_cache:
            try:
                final_path.unlink()
                existing_name = hash_cache[file_hash]
                if isinstance(known_duplicates, dict):
                    known_duplicates[url] = existing_name
                return existing_name
            except Exception as e:
                print(f"[Duplicate] Failed to remove {final_path.name}: {e}")
        else:
            hash_cache[file_hash] = final_path.name
            # For future lookups of same URL (rare but possible)
            if isinstance(known_duplicates, dict):
                known_duplicates[url] = final_path.name

    return final_path.name

def download_media_for_tweet(urls: List[tuple], hash_cache: Optional[Dict[str, str]] = None) -> Dict[str, Optional[str]]:
    """
    Download all media for a single tweet.
    Uses threads, max 5 files (avatar + 4 media) per tweet.
    Returns dict {url: filename}
    """
    results = {}
    known_duplicates = load_duplicate_urls()

    # Use a small thread pool because only 5 downloads per tweet
    with ThreadPoolExecutor(max_workers=min(MAX_TWEET_DOWNLOAD_WORKERS, len(urls))) as executor:
        futures = {executor.submit(download_single_file, url, folder, True, hash_cache, known_duplicates): url
                   for url, folder in urls}

        for future in as_completed(futures):
            url = futures[future]
            results[url] = future.result()

    save_duplicate_urls(known_duplicates)
    return results

# --- Tweet Processing ---
def process_tweets(tweets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    processed = []
    hash_cache = load_hash_cache() if DOWNLOAD_IMAGES else None

    for idx, tweet in enumerate(tweets):
        media_urls = tweet.get("tweet_media_urls", [])[:MAX_MEDIA_PER_TWEET]  # limit media per tweet
        # Skip tweets that have no media at all
        if not media_urls:
            continue
        avatar_url = tweet.get("user_avatar_url", "")

        # Prepare download list (avatar + media)
        urls_to_download = []
        if DOWNLOAD_IMAGES:
            if avatar_url:
                urls_to_download.append((avatar_url, AVATAR_DIR))
            urls_to_download.extend([(url, MEDIA_DIR) for url in media_urls])

        # Download only
        downloaded = download_media_for_tweet(urls_to_download, hash_cache=hash_cache) if DOWNLOAD_IMAGES else {}

        # Sequential processing
        avatar_name = downloaded.get(avatar_url, avatar_url)
        media_names = [downloaded.get(url, url) for url in media_urls]

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
    if DOWNLOAD_IMAGES:
        refresh_media_cache()

    with open(JSON_FILE, encoding="utf8") as f:
        tweets = json.load(f)

    processed_tweets = process_tweets(tweets)
    with open(PROCESSED_JSON, "w", encoding="utf8") as f:
        json.dump(processed_tweets, f)

    print(f"[Main] Processed tweets saved to {PROCESSED_JSON}")

if __name__ == "__main__":
    main()