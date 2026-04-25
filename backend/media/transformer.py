"""Transform raw tweets to processed format with media optimization."""

from pathlib import Path
from typing import Any, Dict, List

from backend.media.config import CONVERT_EXTS, MAX_MEDIA_PER_TWEET, VIDEO_EXTS
from backend.media.converter import convert_to_webp
from backend.media.utils import path_to_output_rel, resolve_mapped_path


def _convert_avatar(avatar_url: str) -> str:
    """Apply WebP conversion to local avatar file if needed."""
    if not avatar_url:
        return avatar_url

    avatar_path = resolve_mapped_path(avatar_url)
    if not avatar_path or avatar_path.suffix.lower() not in CONVERT_EXTS:
        return avatar_url

    converted_path = convert_to_webp(avatar_path)
    return path_to_output_rel(converted_path)


def _convert_media_files(media_urls: List[str]) -> List[str]:
    """Apply WebP conversion to local media files if needed."""
    converted = []
    for url in media_urls:
        media_path = resolve_mapped_path(url)
        if media_path and media_path.suffix.lower() in CONVERT_EXTS:
            converted_path = convert_to_webp(media_path)
            converted.append(path_to_output_rel(converted_path))
        else:
            converted.append(url)
    return converted


def _is_video(media_names: List[str]) -> bool:
    """Check if any media is a video."""
    return any(Path(str(name)).suffix.lower() in VIDEO_EXTS for name in media_names)


def transform_tweets(tweets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Transform raw tweets to display format with media optimization.

    Applies WebP conversion to image files and creates simplified tweet objects.
    Skips tweets with no media.
    """
    processed = []

    for idx, tweet in enumerate(tweets):
        media_urls = tweet.get("tweet_media_urls", [])[:MAX_MEDIA_PER_TWEET]
        if not media_urls:
            continue

        avatar_name = _convert_avatar(tweet.get("user_avatar_url", ""))
        media_names = _convert_media_files(media_urls)

        processed.append(
            {
                "id": str(tweet.get("tweet_id") or idx),
                "avatar": avatar_name,
                "username": tweet.get("user_name", ""),
                "handle": tweet.get("user_handle", ""),
                "content": tweet.get("tweet_content", ""),
                "media": media_names,
                "is_video": _is_video(media_names),
                "possibly_sensitive": tweet.get("possibly_sensitive", ""),
            }
        )

    return processed
