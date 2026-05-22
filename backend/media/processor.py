"""Media processing orchestrator: download, clean, and transform tweets."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.logger import error, info
from backend.media.downloader import download_bulk_media, get_media_folder_dir
from backend.media.transformer import (
    convert_media_files,
    prepare_tweets_data,
)
from backend.media.utils import (
    load_json_file,
    resolve_mapped_path,
    save_json_file,
)
from backend.settings import (
    AVATAR_DIR,
    COMPATIBLE_WEBP_EXTS,
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
        if avatar_url and isinstance(avatar_url, str):
            url_folder_pairs.append((avatar_url, AVATAR_DIR))

        media_urls = tweet.get("tweet_media_urls", [])[:MAX_MEDIA_PER_TWEET]
        for media_url in media_urls:
            if media_url:
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


def _summarize_media_counts(url_file_pairs: Dict[str, Optional[str]]) -> Dict[str, int]:
    """Summarize media counts for processing."""
    total = 0
    images = 0
    avatars = 0
    videos = 0
    webp_candidates = 0

    for rel_filename in url_file_pairs.values():
        if not rel_filename:
            continue
        total += 1
        parts = str(rel_filename).split("/", 1)
        folder = parts[0] if parts else ""
        ext = Path(rel_filename).suffix.lower()

        if folder == "videos":
            videos += 1
        else:
            images += 1
            if folder == "avatars":
                avatars += 1
            if WEBP_ENABLED and ext in COMPATIBLE_WEBP_EXTS:
                webp_candidates += 1

    return {
        "total": total,
        "images": images,
        "avatars": avatars,
        "videos": videos,
        "webp_candidates": webp_candidates,
    }


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
            error(f"Failed to delete orphaned file {resolved}: {e}")
            failed += 1

    shared = len(removed_paths) - len(orphaned_paths)
    msg = f"Removed {len(removed_tweets)} stale tweets, deleted {deleted} orphaned media files"
    if shared:
        msg += f", {shared} shared files kept"
    if failed:
        msg += f", {failed} deletions failed"
    info(msg)

    return surviving_tweets, len(removed_tweets)


def _order_processed_tweets(
    raw_tweets: List[Dict[str, Any]],
    processed_by_id: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Order processed tweets to match raw liked tweets order."""
    ordered = []
    for raw_tweet in raw_tweets:
        tweet_id = raw_tweet.get("tweet_id")
        if not tweet_id:
            continue
        processed = processed_by_id.get(str(tweet_id))
        if processed:
            ordered.append(processed)
    return ordered


def main() -> None:
    """Orchestrate media processing: download, cleanup, and transform."""
    raw_tweets = load_json_file(LIKED_TWEETS_FILE, [])
    if not isinstance(raw_tweets, list):
        error("liked_tweets.json must contain a JSON array")
        return

    info("Filtering tweets with media...")
    tweets_with_media = _filter_tweets_with_media(raw_tweets)
    if not tweets_with_media:
        info("No tweets with media found.")
        return

    # Load existing processed data once; reuse throughout
    existing_tweets = load_json_file(PROCESSED_JSON, [])
    if not isinstance(existing_tweets, list):
        existing_tweets = []

    # Remove unliked tweets
    existing_tweets, removal_count = _remove_tweets_and_orphaned_media(
        existing_tweets, tweets_with_media
    )
    existing_by_id = {
        str(tweet.get("id")): tweet for tweet in existing_tweets if tweet.get("id")
    }

    filtered_tweets = _filter_existing_tweets(tweets_with_media, existing_tweets)

    if not filtered_tweets:
        ordered_existing = _order_processed_tweets(
            tweets_with_media, existing_by_id
        )
        existing_order = [
            str(tweet.get("id")) for tweet in existing_tweets if tweet.get("id")
        ]
        ordered_ids = [
            str(tweet.get("id")) for tweet in ordered_existing if tweet.get("id")
        ]
        if removal_count or existing_order != ordered_ids:
            save_json_file(PROCESSED_JSON, ordered_existing)
            info("No new tweets to add. Synced data.json order.")
        else:
            info("All tweets already exist in data.json.")
        return

    info("Collecting media URLs...")
    url_folder_pairs = _get_url_folder_pairs(filtered_tweets)
    if not url_folder_pairs:
        info("No URLs to download.")
        return

    info(f"Downloading media files ({len(url_folder_pairs)} to download)...")
    url_file_pairs = download_bulk_media(url_folder_pairs)
    if not url_file_pairs:
        error("Failed to download media files.")
        return

    counts = _summarize_media_counts(url_file_pairs)
    info(
        "Processing media files: "
        f"{counts['images']} images ({counts['avatars']} avatars), "
        f"{counts['videos']} videos ({counts['total']} total)"
    )
    if WEBP_ENABLED:
        info(
            "WebP candidates: "
            f"{counts['webp_candidates']}/{counts['images']} images"
        )

    if WEBP_ENABLED:
        info("Converting images to WebP format...")
    else:
        info("Hashing image names...")

    url_to_hashed = convert_media_files(url_file_pairs)
    if not url_to_hashed:
        error("Failed to convert media files.")
        return

    info("Successfully converted/hashed media files.")
    info("Preparing tweet data for export...")
    processed_tweets = prepare_tweets_data(filtered_tweets, url_to_hashed)
    if not processed_tweets:
        error("No tweets prepared for export.")
        return

    # Merge new tweets with surviving existing tweets, preserving raw order
    existing_ids = set(existing_by_id.keys())
    new_tweets = [t for t in processed_tweets if str(t["id"]) not in existing_ids]
    combined_by_id = {
        **existing_by_id,
        **{str(tweet["id"]): tweet for tweet in processed_tweets},
    }
    merged_tweets = _order_processed_tweets(tweets_with_media, combined_by_id)

    with open(PROCESSED_JSON, "w", encoding="utf8") as f:
        json.dump(merged_tweets, f, indent=2)

    info(
        f"Added {len(new_tweets)} new tweets, removed {removal_count} stale tweets ({len(merged_tweets)} total)"
    )


if __name__ == "__main__":
    main()
