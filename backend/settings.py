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

MAX_MEDIA_PER_TWEET = 4

DOWNLOAD_MAX_RETRIES = 3
COMPATIBLE_WEBP_EXTS = {".jpg", ".jpeg", ".png"}
VIDEO_EXTS = {".mp4", ".webm", ".mov"}
HASH_CHUNK_SIZE = 65536

# WebP validation constraints
WEBP_QUALITY_MIN = 1
WEBP_QUALITY_MAX = 100
WEBP_METHOD_MIN = 0
WEBP_METHOD_MAX = 6

# WebP fallback defaults
WEBP_QUALITY_DEFAULT = 80
WEBP_METHOD_DEFAULT = 6

JSON_INDENT = 2

DATA_ENDPOINT = "data.json"

# Config defaults (INPUT schema)
_DEFAULT_CONFIG = {
    "webp_conversion": {
        "enabled": True,
        "quality": 80,
        "method": 6,
    },
    "server": {
        "closeOnPageClose": True,
    },
}


def _validate_config(config: dict) -> dict:
    """Validate and normalize full configuration."""

    return {
        "webp": _validate_webp_config(
            config.get("webp_conversion"),
            _DEFAULT_CONFIG["webp_conversion"],
        ),
        "server": _validate_server_config(
            config.get("server"),
            _DEFAULT_CONFIG["server"],
        ),
    }


def _validate_webp_config(webp_config: dict | None, defaults: dict) -> dict:
    if not isinstance(webp_config, dict):
        error("webp_conversion must be a dictionary, using defaults")
        webp_config = {}

    enabled = webp_config.get("enabled", defaults["enabled"])
    if not isinstance(enabled, bool):
        error(
            f"webp_conversion.enabled must be boolean, got {type(enabled).__name__}, using {defaults['enabled']}"
        )
        enabled = defaults["enabled"]

    quality = webp_config.get("quality", defaults["quality"])
    if not isinstance(quality, int) or not (
        WEBP_QUALITY_MIN <= quality <= WEBP_QUALITY_MAX
    ):
        error(
            f"webp_conversion.quality must be int {WEBP_QUALITY_MIN}-{WEBP_QUALITY_MAX}, got {quality}, using {defaults['quality']}"
        )
        quality = defaults["quality"]

    method = webp_config.get("method", defaults["method"])
    if not isinstance(method, int) or not (
        WEBP_METHOD_MIN <= method <= WEBP_METHOD_MAX
    ):
        error(
            f"webp_conversion.method must be int {WEBP_METHOD_MIN}-{WEBP_METHOD_MAX}, got {method}, using {defaults['method']}"
        )
        method = defaults["method"]

    return {
        "enabled": enabled,
        "quality": quality,
        "method": method,
    }


def _validate_server_config(server_config: dict | None, defaults: dict) -> dict:
    if not isinstance(server_config, dict):
        error("server must be a dictionary, using defaults")
        server_config = {}

    close_on_page_close = server_config.get(
        "closeOnPageClose", defaults["closeOnPageClose"]
    )
    if not isinstance(close_on_page_close, bool):
        error(
            f"server.closeOnPageClose must be boolean, got {type(close_on_page_close).__name__}, using {defaults['closeOnPageClose']}"
        )
        close_on_page_close = defaults["closeOnPageClose"]

    return {
        "closeOnPageClose": close_on_page_close,
    }


def _load_config() -> dict:
    """Load and validate configuration from file, or return defaults on any error."""

    try:
        with open(CONFIG_FILE, encoding="utf8") as f:
            config = json.load(f)
    except FileNotFoundError:
        error(f"Config file not found: {CONFIG_FILE}, using defaults")
        return _validate_config(_DEFAULT_CONFIG)
    except json.JSONDecodeError as e:
        error(f"Failed to parse {CONFIG_FILE}: {e}, using defaults")
        return _validate_config(_DEFAULT_CONFIG)
    except Exception as e:
        error(f"Unexpected error loading {CONFIG_FILE}: {e}, using defaults")
        return _validate_config(_DEFAULT_CONFIG)

    if not isinstance(config, dict):
        error(
            f"config.json must be a dictionary, got {type(config).__name__}, using defaults"
        )
        return _validate_config(_DEFAULT_CONFIG)

    validated = _validate_config(config)
    info(f"Loaded config from {CONFIG_FILE}")
    return validated


_config = _load_config()

# WebP conversion settings (guaranteed valid)
WEBP_ENABLED = _config["webp"]["enabled"]
WEBP_QUALITY = _config["webp"]["quality"]
WEBP_METHOD = _config["webp"]["method"]

# Server settings (guaranteed valid)
SERVER_CLOSE_ON_PAGE_CLOSE = _config["server"]["closeOnPageClose"]
