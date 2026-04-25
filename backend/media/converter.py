"""WebP image format conversion."""

from pathlib import Path

from PIL import Image

from backend.media.config import WEBP_QUALITY, WEBP_METHOD


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
