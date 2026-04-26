"""Media processing orchestrator: download, clean, and transform tweets."""

import json
from typing import Any, Dict, List

from backend.media.downloader import download_bulk_media, get_media_folder_dir
from backend.media.transformer import (
    convert_media_files,
    prepare_tweets_data,
)
from backend.media.utils import (
    load_json_file,
    resolve_mapped_path,
)

# from backend.media.cleaner import cleanup
from backend.settings import (
    AVATAR_DIR,
    LIKED_TWEETS_FILE,
    MAX_MEDIA_PER_TWEET,
    PROCESSED_JSON,
    WEBP_ENABLED,
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


def _filter_existing_tweets(
    tweets: List[Dict[str, Any]], existing_tweets: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Filter out tweets whose IDs already exist in data.json."""
    existing_ids = {
        str(tweet.get("id")) for tweet in existing_tweets if tweet.get("id")
    }
    return [tweet for tweet in tweets if str(tweet.get("tweet_id")) not in existing_ids]


def _get_referenced_paths(tweets: List[Dict[str, Any]]) -> set:
    """Return all local media paths referenced by a list of processed tweets."""
    paths = set()
    for tweet in tweets:
        if tweet.get("avatar"):
            paths.add(tweet["avatar"])
        for media in tweet.get("media", []):
            if media.get("path"):
                paths.add(media["path"])
    return paths


def _remove_tweets_and_orphaned_media(
    existing_tweets: List[Dict[str, Any]],
    raw_tweets: List[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], int]:
    """Remove processed tweets whose IDs are no longer in raw_tweets, and
    delete any media files they referenced that are not used by any remaining tweet.

    Returns (surviving_tweets, removal_count).
    """
    current_ids = {str(t.get("tweet_id")) for t in raw_tweets if t.get("tweet_id")}
    surviving_tweets = [t for t in existing_tweets if str(t.get("id")) in current_ids]
    removed_tweets = [t for t in existing_tweets if str(t.get("id")) not in current_ids]

    if not removed_tweets:
        return existing_tweets, 0

    surviving_paths = _get_referenced_paths(surviving_tweets)
    removed_paths = _get_referenced_paths(removed_tweets)
    orphaned_paths = removed_paths - surviving_paths

    deleted, failed = 0, 0
    for rel_path in orphaned_paths:
        resolved = resolve_mapped_path(rel_path)
        if not resolved:
            continue
        try:
            if resolved.exists():
                resolved.unlink()
                deleted += 1
        except Exception as e:
            print(f"[Processor] Failed to delete orphaned file {resolved}: {e}")
            failed += 1

    shared = len(removed_paths) - len(orphaned_paths)
    print(
        f"[Processor] Removed {len(removed_tweets)} stale tweets, "
        f"deleted {deleted} orphaned media files"
        + (f", {shared} shared files kept" if shared else "")
        + (f", {failed} deletions failed" if failed else "")
    )

    return surviving_tweets, len(removed_tweets)


def main() -> None:
    """Orchestrate media processing: download, cleanup, and transform."""
    raw_tweets = load_json_file(LIKED_TWEETS_FILE, [])
    if not isinstance(raw_tweets, list):
        raise ValueError("liked_tweets.json must contain a JSON array")

    print("[Processor] Filtering tweets...")
    tweets_with_media = _filter_tweets_with_media(raw_tweets)
    if not tweets_with_media:
        print("[Processor] No tweets with media found. Exiting.")
        return

    # Load existing processed data once; reuse throughout
    existing_tweets = []
    if PROCESSED_JSON.exists():
        with open(PROCESSED_JSON, "r", encoding="utf8") as f:
            try:
                existing_tweets = json.load(f)
            except json.JSONDecodeError:
                existing_tweets = []

    # Remove unliked tweets
    existing_tweets, removal_count = _remove_tweets_and_orphaned_media(
        existing_tweets, tweets_with_media
    )

    filtered_tweets = _filter_existing_tweets(tweets_with_media, existing_tweets)

    if not filtered_tweets:
        if removal_count:
            with open(PROCESSED_JSON, "w", encoding="utf8") as f:
                json.dump(existing_tweets, f)
            print("[Processor] No new tweets to add. Saved updated data.json.")
        else:
            print("[Processor] All tweets already exist in data.json. Exiting.")
        return

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

    if WEBP_ENABLED:
        print("[Processor] Converting images to WebP format...")
    else:
        print("[Processor] Hashing image names...")

    url_to_hashed = convert_media_files(url_file_pairs)
    if not url_to_hashed:
        print("[Processor] Failed to convert media files. Exiting.")
        return

    print("[Processor] Successfully converted images")
    print("[Processor] Preparing tweet data for export...")
    processed_tweets = prepare_tweets_data(filtered_tweets, url_to_hashed)
    if not processed_tweets:
        print("[Processor] No tweets prepared for export. Exiting.")
        return

    # Merge new tweets with surviving existing tweets, deduplicating by id
    existing_ids = {tweet["id"] for tweet in existing_tweets}
    new_tweets = [t for t in processed_tweets if t["id"] not in existing_ids]
    merged_tweets = new_tweets + existing_tweets

    with open(PROCESSED_JSON, "w", encoding="utf8") as f:
        json.dump(merged_tweets, f)

    print(
        f"[Processor] Added {len(new_tweets)} new tweets, "
        f"removed {removal_count} stale tweets "
        f"({len(merged_tweets)} total)"
    )


if __name__ == "__main__":
    main()
