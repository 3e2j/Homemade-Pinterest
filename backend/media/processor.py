"""Media processing orchestrator: download, clean, and transform tweets."""

import json
from typing import Any, Dict, List

# from backend.media.cleaner import cleanup
from backend.settings import (
    AVATAR_DIR,
    DOWNLOAD_IMAGES,
    LIKED_TWEETS_FILE,
    MAX_MEDIA_PER_TWEET,
    PROCESSED_JSON,
)
from backend.media.downloader import download_bulk_media, get_media_folder_dir
from backend.media.transformer import (
    convert_media_files,
    prepare_tweets_data,
)
from backend.media.utils import (
    load_json_file,
)


def _filter_tweets_with_media(tweets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter tweets to only those with media (tweet_media_urls).

    Avatar URLs are not considered in this check.
    """
    return [
        tweet
        for tweet in tweets
        if tweet.get("tweet_media_urls") and len(tweet.get("tweet_media_urls", [])) > 0
    ]


def _get_url_folder_pairs(
    tweets: List[Dict[str, Any]],
) -> List[tuple]:
    """Collect URLs to download from tweets.

    Returns list of (url, folder) tuples to download.
    """
    url_folder_pairs = []

    for tweet in tweets:
        avatar_url = tweet.get("user_avatar_url", "")
        if avatar_url:
            url_folder_pairs.append((avatar_url, AVATAR_DIR))

        media_urls = tweet.get("tweet_media_urls", [])[:MAX_MEDIA_PER_TWEET]
        for media_url in media_urls:
            if not media_url:
                continue
            folder = get_media_folder_dir(media_url)
            url_folder_pairs.append((media_url, folder))

    return url_folder_pairs


def _filter_existing_tweets(tweets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter out tweets whose IDs already exist in data.json."""
    existing_ids = set()
    if PROCESSED_JSON.exists():
        try:
            existing_data = load_json_file(PROCESSED_JSON, [])
            existing_ids = {
                str(tweet.get("id")) for tweet in existing_data if tweet.get("id")
            }
        except Exception as e:
            print(f"[Processor] Failed to load existing IDs from data.json: {e}")

    new_tweets = [
        tweet for tweet in tweets if str(tweet.get("tweet_id")) not in existing_ids
    ]
    return new_tweets


def main() -> None:
    """Orchestrate media processing: download, cleanup, and transform."""
    raw_tweets = load_json_file(LIKED_TWEETS_FILE, [])
    if not isinstance(raw_tweets, list):
        raise ValueError("liked_tweets.json must contain a JSON array")

    print("[Processor] Filtering tweets...")
    filtered_tweets = _filter_tweets_with_media(raw_tweets)
    if not filtered_tweets:
        print("[Processor] No tweets with media found. Exiting.")
        return

    filtered_tweets = _filter_existing_tweets(filtered_tweets)
    if not filtered_tweets:
        print("[Processor] All tweets already exist in data.json. Exiting.")
        return

    print(
        f"[Processor] Kept {len(filtered_tweets)} tweets (out of {len(raw_tweets)} total"
    )

    if DOWNLOAD_IMAGES:
        print("[Processor] Collecting media URLs...")
        url_folder_pairs = _get_url_folder_pairs(filtered_tweets)
        if not url_folder_pairs:
            print("[Processor] No URLs to download. Exiting.")
            return

        print(
            f"[Processor] Downloading media files ({len(url_folder_pairs)} to download)..."
        )
        url_file_pairs = download_bulk_media(url_folder_pairs)
        if not url_file_pairs:
            print("[Processor] Failed to download media files. Exiting.")
            return

        print("[Processor] Converting images to WebP format...")
        url_to_hashed = convert_media_files(url_file_pairs)
        if not url_to_hashed:
            print("[Processor] Failed to convert media files. Exiting.")
            return
        print("[Processor] Successfully converted images")
    else:
        print("[Processor] Using remote URLs (DOWNLOAD_IMAGES=false)")
        url_to_hashed = {url: url for tweet in filtered_tweets for url in [tweet.get("user_avatar_url", "")] + tweet.get("tweet_media_urls", []) if url}

    print("[Processor] Preparing tweet data for export...")
    processed_tweets = prepare_tweets_data(filtered_tweets, url_to_hashed)
    if not processed_tweets:
        print("[Processor] No tweets prepared for export. Exiting.")
        return

    with open(PROCESSED_JSON, "w", encoding="utf8") as f:
        json.dump(processed_tweets, f)

    print(f"[Processor] Tweets processed and saved to {PROCESSED_JSON}")


if __name__ == "__main__":
    main()
