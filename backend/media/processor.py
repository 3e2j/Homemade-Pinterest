"""Media processing orchestrator: download, clean, and transform tweets."""

import json
from typing import Any, Dict, List

from backend.media.cleaner import cleanup
from backend.media.config import (
    AVATAR_DIR,
    DOWNLOAD_IMAGES,
    JSON_FILE,
    MAX_MEDIA_PER_TWEET,
    PROCESSED_JSON,
)
from backend.media.downloader import download_bulk_media, media_target_folder
from backend.media.transformer import transform_tweets
from backend.media.utils import load_json_file


def _download_media(tweets: List[Dict[str, Any]]) -> None:
    """Download media files from URLs and update tweet records in-place."""
    if not DOWNLOAD_IMAGES:
        return

    url_folder_pairs: List[tuple] = []

    # Collect all URLs to download
    for tweet in tweets:
        avatar_url = tweet.get("user_avatar_url", "")
        if avatar_url:
            url_folder_pairs.append((avatar_url, AVATAR_DIR))

        for media_url in tweet.get("tweet_media_urls", [])[:MAX_MEDIA_PER_TWEET]:
            if media_url:
                url_folder_pairs.append((media_url, media_target_folder(media_url)))

    # Download and map URLs to local files
    download_results = download_bulk_media(url_folder_pairs)

    # Update tweet records with local file paths
    for tweet in tweets:
        avatar_url = tweet.get("user_avatar_url", "")
        if avatar_url and avatar_url in download_results:
            tweet["user_avatar_url"] = download_results[avatar_url]

        media_urls = tweet.get("tweet_media_urls", [])
        tweet["tweet_media_urls"] = [
            download_results.get(url, url) for url in media_urls if url
        ]


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
    _download_media(raw_tweets)
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
