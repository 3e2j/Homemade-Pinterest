import json
import requests
from pathlib import Path
from urllib.parse import urlparse
from hashlib import md5
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys

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

# --- Utilities ---
def load_json_file(path, default):
    if path.exists():
        try:
            with open(path, "r", encoding="utf8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[LoadJSON] Failed to load {path}: {e}")
    return default

def save_json_file(path, data):
    try:
        with open(path, "w", encoding="utf8") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"[SaveJSON] Failed to save {path}: {e}")

def compute_file_hash(filepath, chunk_size=65536):
    h = md5()
    try:
        with filepath.open("rb") as f:
            while chunk := f.read(chunk_size):
                h.update(chunk)
        return h.hexdigest()
    except Exception as e:
        print(f"[Hash] Failed to hash {filepath}: {e}")
        return ""

def convert_to_webp(filepath, quality=60):
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

# --- Hash & Duplicate Management ---
def load_hash_cache():
    return load_json_file(MEDIA_HASH_CACHE, {})

def save_hash_cache(hash_map):
    save_json_file(MEDIA_HASH_CACHE, hash_map)

def load_duplicate_urls():
    return set(load_json_file(DUPLICATE_URLS_FILE, []))

def save_duplicate_urls(urls):
    save_json_file(DUPLICATE_URLS_FILE, list(urls))

def recompute_hashes_and_remove_duplicates():
    if not DOWNLOAD_IMAGES:
        return

    hash_cache = load_hash_cache()
    duplicates_removed = 0
    seen_hashes = {}

    for folder in [MEDIA_DIR, AVATAR_DIR]:
        for file_path in folder.iterdir():
            if not file_path.is_file():
                continue

            file_hash = compute_file_hash(file_path)
            if not file_hash:
                continue

            if file_hash in seen_hashes:
                try:
                    file_path.unlink()
                    duplicates_removed += 1
                    print(f"[Duplicate] Removed {file_path.name} (duplicate of {seen_hashes[file_hash]})")
                except Exception as e:
                    print(f"[Duplicate] Failed to remove {file_path.name}: {e}")
                continue

            seen_hashes[file_hash] = file_path.name
            if file_hash not in hash_cache:
                hash_cache[file_hash] = file_path.name
                print(f"[HashUpdate] Added missing hash for {file_path.name}")

    save_hash_cache(hash_cache)
    if duplicates_removed > 0:
        print(f"[Duplicate] Removed {duplicates_removed} duplicates and updated hash cache.")

# --- Media Downloading (Threaded) ---
def download_single_file(url, folder, convert=True, hash_cache=None, known_duplicates=None):
    if not url or (known_duplicates and url in known_duplicates):
        return None

    ext = Path(urlparse(url).path).suffix
    hashed_name = md5(url.encode()).hexdigest()
    final_name = f"{hashed_name}.webp" if ext.lower() in {".jpg", ".jpeg", ".png"} else f"{hashed_name}{ext}"
    final_path = folder / final_name

    if final_path.exists():
        return final_name

    original_path = folder / f"{hashed_name}{ext}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        original_path.write_bytes(resp.content)
        print(f"[Download] Saved: {url} -> {original_path.name}")
    except Exception as e:
        print(f"[Download] Failed: {url} ({e})")
        return None

    if convert and original_path.suffix.lower() in {".jpg", ".jpeg", ".png"}:
        final_path = convert_to_webp(original_path)

    if hash_cache:
        file_hash = compute_file_hash(final_path)
        if file_hash in hash_cache:
            try:
                final_path.unlink()
                if known_duplicates is not None:
                    known_duplicates.add(url)
                return hash_cache[file_hash]
            except Exception as e:
                print(f"[Duplicate] Failed to remove {final_path.name}: {e}")
        else:
            hash_cache[file_hash] = final_path.name

    return final_path.name

def download_media_for_tweet(urls, hash_cache=None):
    """
    Download all media for a single tweet.
    Uses threads, max 5 files (avatar + 4 media) per tweet.
    Returns dict {url: filename}
    """
    results = {}
    known_duplicates = load_duplicate_urls()

    # Use a small thread pool because only 5 downloads per tweet
    with ThreadPoolExecutor(max_workers=min(5, len(urls))) as executor:
        futures = {executor.submit(download_single_file, url, folder, True, hash_cache, known_duplicates): url
                   for url, folder in urls}

        for future in as_completed(futures):
            url = futures[future]
            results[url] = future.result()

    save_duplicate_urls(known_duplicates)
    return results

# --- Tweet Processing ---
def process_tweets(tweets):
    processed = []
    hash_cache = load_hash_cache() if DOWNLOAD_IMAGES else None

    for idx, tweet in enumerate(tweets):
        media_urls = tweet.get("tweet_media_urls", [])[:4]  # limit to 4 media per tweet
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
def main():
    if DOWNLOAD_IMAGES:
        recompute_hashes_and_remove_duplicates()

    with open(JSON_FILE, encoding="utf8") as f:
        tweets = json.load(f)

    processed_tweets = process_tweets(tweets)
    with open(PROCESSED_JSON, "w", encoding="utf8") as f:
        json.dump(processed_tweets, f)

    print(f"[Main] Processed tweets saved to {PROCESSED_JSON}")

if __name__ == "__main__":
    main()