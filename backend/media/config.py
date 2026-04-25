"""Configuration and constants for media processing."""

import json
import sys

from backend.paths import CONFIG_FILE, OUTPUT_DIR

JSON_FILE = OUTPUT_DIR / "liked_tweets.json"
MEDIA_ROOT_DIR = OUTPUT_DIR / "media"
IMAGE_DIR = MEDIA_ROOT_DIR / "images"
VIDEO_DIR = MEDIA_ROOT_DIR / "videos"
AVATAR_DIR = MEDIA_ROOT_DIR / "avatars"
MEDIA_HASH_CACHE = OUTPUT_DIR / ".media_hashes.json"
PROCESSED_JSON = OUTPUT_DIR / "data.json"

for folder in (IMAGE_DIR, VIDEO_DIR, AVATAR_DIR):
    folder.mkdir(parents=True, exist_ok=True)

try:
    with open(CONFIG_FILE, encoding="utf8") as f:
        _config = json.load(f)
except Exception as e:
    print(f"Failed to load {CONFIG_FILE}: {e}")
    sys.exit(1)

DOWNLOAD_IMAGES = _config.get("DOWNLOAD_IMAGES", True)

CONVERT_EXTS = {".jpg", ".jpeg", ".png"}
VIDEO_EXTS = {".mp4", ".webm", ".mov"}
WEBP_QUALITY = 60
MAX_MEDIA_PER_TWEET = 4
WEBP_METHOD = 6
HASH_CHUNK_SIZE = 65536
