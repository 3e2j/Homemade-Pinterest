"""Project paths and constants."""

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = BACKEND_DIR.parent.resolve()

CONFIG_FILE = PROJECT_ROOT / "config.json"
OUTPUT_DIR = PROJECT_ROOT / "output"
FRONTEND_DIR = PROJECT_ROOT / "frontend"

LIKED_TWEETS_FILE = OUTPUT_DIR / "liked_tweets.json"
PROCESSED_JSON = OUTPUT_DIR / "data.json"

MEDIA_ROOT_DIR = OUTPUT_DIR / "media"
IMAGE_DIR = MEDIA_ROOT_DIR / "images"
VIDEO_DIR = MEDIA_ROOT_DIR / "videos"
AVATAR_DIR = MEDIA_ROOT_DIR / "avatars"

MEDIA_DIRS = [IMAGE_DIR, VIDEO_DIR, AVATAR_DIR]

for folder in MEDIA_DIRS:
    folder.mkdir(parents=True, exist_ok=True)

MAX_MEDIA_PER_TWEET = 4
COMPATIBLE_WEBP_EXTS = {".jpg", ".jpeg", ".png"}
VIDEO_EXTS = {".mp4", ".webm", ".mov"}
WEBP_QUALITY = 60
WEBP_METHOD = 6
HASH_CHUNK_SIZE = 65536

JSON_INDENT = 2

DATA_ENDPOINT = "data.json"

try:
    with open(CONFIG_FILE, encoding="utf8") as f:
        _config = json.load(f)
except Exception as e:
    print(f"Failed to load {CONFIG_FILE}: {e}")
    sys.exit(1)

DOWNLOAD_IMAGES = _config.get("DOWNLOAD_IMAGES", True)
