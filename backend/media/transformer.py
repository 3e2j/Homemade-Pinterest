"""Transform raw tweets to processed format with media optimization."""

import multiprocessing as mp
import os
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

from backend.logger import error, info, warning
from backend.media.utils import (
    compute_file_hash,
    path_to_output_rel,
    resolve_mapped_path,
)
from backend.settings import (
    COMPATIBLE_WEBP_EXTS,
    MAX_MEDIA_PER_TWEET,
    VIDEO_EXTS,
    WEBP_ENABLED,
    WEBP_METHOD,
    WEBP_QUALITY,
)

MAX_CONVERT_WORKERS = 8
WORKERS_PER_CORE = 1
MIN_CONVERT_WORKERS = 2


def _get_hashed_path(filepath: Path) -> Optional[Path]:
    """Return a new Path in the same directory with a hashed filename.

    Uses the content hash as the filename, keeping the original extension
    """
    content_hash = compute_file_hash(filepath)
    if not content_hash:
        return None
    ext = filepath.suffix.lower()
    return filepath.parent / f"{content_hash}{ext}"


def convert_to_webp(
    filepath: Path, webp_path: Path, quality: int = WEBP_QUALITY
) -> Path:
    """Convert `filepath` to WebP with content hash naming.

    Saves the WebP file as {content_hash}.webp and removes the original.
    Returns the path to the WebP file, or the original path on failure.
    """

    try:
        with Image.open(filepath) as img:
            img.save(webp_path, "webp", quality=quality, method=WEBP_METHOD)
        filepath.unlink()
        return webp_path
    except Exception as e:
        error(f"Failed to convert {filepath} to webp: {e}")
        return filepath


def _process_media_item(url: str, rel_filename: str) -> Tuple[str, Optional[str], str]:
    if not rel_filename:
        warning("Missing rel_filename in url_file_pair")
        return url, None, "skipped"

    filepath = resolve_mapped_path(rel_filename)
    if not filepath or not filepath.exists():
        warning(f"Media filepath not found or inaccessible: {rel_filename}")
        return url, None, "skipped"

    hashed_path = _get_hashed_path(filepath)
    if hashed_path is None:
        warning(f"Could not compute hash for media: {filepath}")
        return url, None, "skipped"

    # Check if file can be converted to WebP
    if WEBP_ENABLED and filepath.suffix.lower() in COMPATIBLE_WEBP_EXTS:
        converted_path = convert_to_webp(filepath, hashed_path.with_suffix(".webp"))
        hashed_filename = path_to_output_rel(converted_path)
        status = "converted" if converted_path.suffix.lower() == ".webp" else "hashed"
    else:
        # Duplicate hash, use the one thats already on disk
        if hashed_path.exists():
            try:
                filepath.unlink()
            except Exception as e:
                error(f"Failed to delete duplicate file {filepath}: {e}")
        else:
            try:
                filepath.rename(hashed_path)
            except Exception as e:
                error(f"Failed to rename {filepath} to {hashed_path}: {e}")
                return url, None, "skipped"
        hashed_filename = path_to_output_rel(hashed_path)
        status = "hashed"

    if hashed_filename:
        return url, hashed_filename, status

    return url, None, "skipped"


def _resolve_convert_workers(max_workers: Optional[int], task_count: int) -> int:
    if max_workers is None:
        cpu = os.cpu_count() or MIN_CONVERT_WORKERS
        max_workers = min(
            MAX_CONVERT_WORKERS, max(MIN_CONVERT_WORKERS, cpu * WORKERS_PER_CORE)
        )
    return max(1, min(max_workers, task_count))


def convert_media_files(
    url_file_pairs: Dict[str, Optional[str]],
    max_workers: Optional[int] = None,
) -> Dict[str, str]:
    """Convert media files and return mapping of URLs to hashed filenames.

    Takes url->filename mapping from downloader and:
    1. Converts compatible images to WebP with hash naming
    2. Renames non-converted files to hash naming
    3. Returns Dict[url] -> hashed_filename for use in prepare_tweets_data

    Example:
        Input: {'https://example.com/pic.jpg': 'images/pic.jpg'}
        Output: {'https://example.com/pic.jpg': 'images/abc123def.webp'}
    """
    url_to_hashed: Dict[str, str] = {}
    tasks = []
    skipped = 0
    for url, rel_filename in url_file_pairs.items():
        if not rel_filename:
            warning("Missing rel_filename in url_file_pair")
            skipped += 1
            continue
        tasks.append((url, rel_filename))

    if not tasks:
        if skipped:
            info(f"Media processing complete: 0 webp, 0 hashed, {skipped} skipped")
        return url_to_hashed

    worker_count = _resolve_convert_workers(max_workers, len(tasks))
    if WEBP_ENABLED:
        info(f"Converting media with {worker_count} worker(s)...")

    converted = 0
    hashed = 0

    if worker_count == 1:
        for url, rel_filename in tasks:
            url, hashed_filename, status = _process_media_item(url, rel_filename)
            if hashed_filename:
                url_to_hashed[url] = hashed_filename
            if status == "converted":
                converted += 1
            elif status == "hashed":
                hashed += 1
            else:
                skipped += 1
    else:
        if WEBP_ENABLED:
            if os.name == "posix":
                context = mp.get_context("fork")
                executor = ProcessPoolExecutor(
                    max_workers=worker_count, mp_context=context
                )
            else:
                executor = ProcessPoolExecutor(max_workers=worker_count)
        else:
            executor = ThreadPoolExecutor(max_workers=worker_count)

        with executor:
            futures = {
                executor.submit(_process_media_item, url, rel_filename): url
                for url, rel_filename in tasks
            }
            for future in as_completed(futures):
                try:
                    url, hashed_filename, status = future.result()
                except Exception as e:
                    error(f"Unexpected error converting media: {e}")
                    skipped += 1
                    continue

                if hashed_filename:
                    url_to_hashed[url] = hashed_filename
                if status == "converted":
                    converted += 1
                elif status == "hashed":
                    hashed += 1
                else:
                    skipped += 1

    info(
        "Media processing complete: "
        f"{converted} webp, {hashed} hashed, {skipped} skipped"
    )
    return url_to_hashed


def _is_video(media_names: List[str]) -> bool:
    """Check if any media is a video."""
    return any(
        Path(str(name)).suffix.lower() in VIDEO_EXTS for name in media_names if name
    )


def prepare_tweets_data(
    filtered_tweets: List[Dict[str, Any]], url_to_converted: Dict[str, str]
) -> List[Dict[str, Any]]:
    """Prepare tweets (with media) for data.json using converted media filenames.

    Takes tweets and URL->converted_filename mapping and returns processed tweet objects
    ready for serialization. Maps each media URL to its converted filename/path.
    """
    processed = []

    for idx, tweet in enumerate(filtered_tweets):
        media_urls = tweet.get("tweet_media_urls", [])[:MAX_MEDIA_PER_TWEET]

        avatar_url = tweet.get("user_avatar_url", "")
        avatar_filepath = url_to_converted.get(avatar_url, "")

        # Map each URL to its converted filename using the url_to_converted mapping
        converted_media: List[Dict[str, str]] = []
        converted_media_filepaths: List[str] = []
        for url in media_urls:
            if url:
                hashed = url_to_converted.get(url)
                if hashed:
                    converted_media.append({"url": url, "path": hashed})
                    converted_media_filepaths.append(hashed)

        processed.append(
            {
                "id": str(tweet.get("tweet_id") or idx),
                "avatar": avatar_filepath,
                "username": tweet.get("user_name", ""),
                "handle": tweet.get("user_handle", ""),
                "content": tweet.get("tweet_content", ""),
                "media": converted_media,
                "is_video": _is_video(converted_media_filepaths),
                "possibly_sensitive": tweet.get("possibly_sensitive", ""),
            }
        )

    return processed
