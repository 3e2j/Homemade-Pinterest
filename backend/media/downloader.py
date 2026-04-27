"""Media file downloader: Fetch and cache media files from URLs."""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

import requests

from backend.logger import error, info
from backend.settings import (
    AVATAR_DIR,
    DOWNLOAD_MAX_RETRIES,
    IMAGE_DIR,
    VIDEO_DIR,
    VIDEO_EXTS,
)

for folder in (IMAGE_DIR, VIDEO_DIR, AVATAR_DIR):
    folder.mkdir(parents=True, exist_ok=True)

REQUEST_TIMEOUT_SECONDS = 10
MAX_THREADPOOL_WORKERS = 32
THREADS_PER_CORE = 4
MIN_THREADS = 4
DOWNLOAD_STREAM_CHUNK = 8192


def get_media_folder_dir(url: str) -> Path:
    """Determine media type folder (images/videos) from URL extension."""
    ext = Path(urlparse(url).path).suffix.lower()
    return VIDEO_DIR if ext in VIDEO_EXTS else IMAGE_DIR


def _is_transient_error(exc: Exception) -> bool:
    """Check if error is transient (should retry)."""
    if isinstance(
        exc, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)
    ):
        return True
    if isinstance(exc, requests.exceptions.HTTPError):
        status = exc.response.status_code if exc.response else None
        return status in (429, 500, 502, 503, 504)
    return False


def download_single_file(url: str, folder: Path) -> Optional[str]:
    """Download `url` into `folder` and return the stored relative path or None.

    Saves file using URL stem naming: {url_stem}.{ext}
    Returns relative path like 'folder/filename.jpg'
    Retries on transient network errors.
    Cleans up partial files on failure to avoid corruption.
    """
    if not url or not isinstance(url, str):
        return None

    path = Path(urlparse(url).path)
    url_stem = path.stem
    ext = path.suffix

    if not url_stem or not ext:
        return None

    file_path = folder / f"{url_stem}{ext}"

    for attempt in range(DOWNLOAD_MAX_RETRIES):
        try:
            resp = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS, stream=True)
            resp.raise_for_status()

            with file_path.open("wb") as out_f:
                for chunk in resp.iter_content(chunk_size=DOWNLOAD_STREAM_CHUNK):
                    if chunk:
                        out_f.write(chunk)

            return f"{folder.name}/{file_path.name}"
        except Exception as e:
            file_path.unlink(missing_ok=True)

            if not _is_transient_error(e):
                status = ""
                if isinstance(e, requests.exceptions.HTTPError) and e.response:
                    status = f" {e.response.status_code}"
                error(f"Download failed{status}: {url}")
                return None

            if attempt == DOWNLOAD_MAX_RETRIES - 1:
                error(f"Download failed after {DOWNLOAD_MAX_RETRIES} attempts: {url}")
                return None

    return None


def download_bulk_media(
    url_folder_pairs: List[tuple],
    max_workers: Optional[int] = None,
) -> Dict[str, Optional[str]]:
    """Download unique URLs from `url_folder_pairs` using a thread pool.

    Returns a dict of (url->filename map).
    Each unique URL is downloaded at most once.
    """
    if not url_folder_pairs:
        return {}

    if max_workers is None:
        cpu = os.cpu_count() or MIN_THREADS
        max_workers = min(MAX_THREADPOOL_WORKERS, cpu * THREADS_PER_CORE)

    # Deduplicate input; only download one URL once.
    unique_pairs: Dict[str, Path] = {}
    for url, folder in url_folder_pairs:
        if url and isinstance(url, str):
            unique_pairs.setdefault(url, folder)

    # url -> saved filepath
    results: Dict[str, Optional[str]] = {}
    failed_urls = 0

    with ThreadPoolExecutor(
        max_workers=min(max_workers, max(1, len(unique_pairs)))
    ) as executor:
        futures = {
            executor.submit(download_single_file, url, folder): url
            for url, folder in unique_pairs.items()
        }
        for future in as_completed(futures):
            url = futures[future]
            try:
                result = future.result()
                results[url] = result
                if result is None:
                    failed_urls += 1
            except Exception as e:
                error(f"Unexpected error downloading {url}: {e}")
                results[url] = None
                failed_urls += 1

    succeeded = len(results) - failed_urls
    info(f"Media download complete ({succeeded}/{len(results)} succeeded)")
    return results
