"""Project paths and constants."""

import json
from pathlib import Path

from backend.logger import error, info

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
HASH_CHUNK_SIZE = 65536

JSON_INDENT = 2

DATA_ENDPOINT = "data.json"

# Config defaults
_DEFAULT_CONFIG = {
    "webp_conversion": {
        "enabled": True,
        "quality": 80,
        "method": 6,
    },
    "server": {
        "closeOnPageClose": False,
    },
}


def _validate_webp_config(config: dict) -> dict:
    """Validate and normalize WebP configuration."""
    webp_config = config.get("webp_conversion", {})

    if not isinstance(webp_config, dict):
        error("webp_conversion must be a dictionary")
        webp_config = {}

    enabled = webp_config.get("enabled", True)
    if not isinstance(enabled, bool):
        error(f"webp_conversion.enabled must be boolean, got {type(enabled).__name__}")
        enabled = True

    quality = webp_config.get("quality", 80)
    if not isinstance(quality, int) or quality < 1 or quality > 100:
        error(f"webp_conversion.quality must be int 1-100, got {quality}")
        quality = 80

    method = webp_config.get("method", 6)
    if not isinstance(method, int) or method < 0 or method > 6:
        error(f"webp_conversion.method must be int 0-6, got {method}")
        method = 6

    return {
        "enabled": enabled,
        "quality": quality,
        "method": method,
    }


def _validate_server_config(config: dict) -> dict:
    """Validate and normalize server configuration."""
    server_config = config.get("server", {})

    if not isinstance(server_config, dict):
        error("server must be a dictionary")
        server_config = {}

    close_on_page_close = server_config.get("closeOnPageClose", False)
    if not isinstance(close_on_page_close, bool):
        error(
            f"server.closeOnPageClose must be boolean, got {type(close_on_page_close).__name__}"
        )
        close_on_page_close = False

    return {
        "closeOnPageClose": close_on_page_close,
    }


try:
    with open(CONFIG_FILE, encoding="utf8") as f:
        _config = json.load(f)

    if not isinstance(_config, dict):
        error(f"config.json must be a dictionary, got {type(_config).__name__}")
        _config = _DEFAULT_CONFIG

    # Validate each section
    _webp_config = _validate_webp_config(_config)
    _server_config = _validate_server_config(_config)

    info(f"Loaded config from {CONFIG_FILE}")

except FileNotFoundError:
    error(f"Config file not found: {CONFIG_FILE}")
    _webp_config = _DEFAULT_CONFIG["webp_conversion"]
    _server_config = _DEFAULT_CONFIG["server"]
except json.JSONDecodeError as e:
    error(f"Failed to parse {CONFIG_FILE}: {e}")
    _webp_config = _DEFAULT_CONFIG["webp_conversion"]
    _server_config = _DEFAULT_CONFIG["server"]
except Exception as e:
    error(f"Unexpected error loading {CONFIG_FILE}: {e}")
    _webp_config = _DEFAULT_CONFIG["webp_conversion"]
    _server_config = _DEFAULT_CONFIG["server"]

# WebP conversion settings
WEBP_ENABLED = _webp_config.get("enabled", True)
WEBP_QUALITY = _webp_config.get("quality", 80)
WEBP_METHOD = _webp_config.get("method", 6)
