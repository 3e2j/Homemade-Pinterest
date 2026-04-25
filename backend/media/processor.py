"""Media processing orchestrator: download, clean, and transform tweets."""

import json

from backend.media.cleaner import cleanup
from backend.media.config import (
    DOWNLOAD_IMAGES,
    JSON_FILE,
    PROCESSED_JSON,
)
from backend.media.downloader import update_tweets_with_downloaded_media
from backend.media.transformer import transform_tweets
from backend.media.utils import load_json_file


def main() -> None:
    """Orchestrate media processing: cleanup, download, and transform."""
    # Step 1: Clean up orphaned files and duplicates
    if DOWNLOAD_IMAGES:
        cleanup()

    # Step 2: Load raw tweet data
    raw_tweets = load_json_file(JSON_FILE, [])
    if not isinstance(raw_tweets, list):
        raise ValueError("liked_tweets.json must contain a JSON array")

    # Step 3: Download media files and update tweet records
    print("[Processor] Downloading media files...")
    update_tweets_with_downloaded_media(raw_tweets)
    print("[Processor] Media files downloaded")

    # Step 4: Transform to display format with media optimization
    print("[Processor] Converting images to a WebP format...")
    processed_tweets = transform_tweets(raw_tweets)
    print("[Processor] Successfully converted images")

    # Step 5: Write final data
    with open(PROCESSED_JSON, "w", encoding="utf8") as f:
        json.dump(processed_tweets, f)

    print(f"[Processor] Tweets processed and saved to {PROCESSED_JSON}")


if __name__ == "__main__":
    main()
