"""Tweet caching: Manage tweet data persistence."""

import json
from pathlib import Path
from typing import Any, Dict, List

from backend.settings import JSON_INDENT

UTF8 = "utf8"
TWEET_ID_KEY = "tweet_id"


class TweetCache:
    """Manages tweet data persistence to JSON cache."""

    def __init__(self, cache_path: Path):
        self.cache_path = cache_path

    def load(self) -> List[Dict[str, Any]]:
        """Loads tweets from cache file."""
        if not self.cache_path.exists():
            return []
        try:
            with open(self.cache_path, "r", encoding=UTF8) as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            print("Invalid or missing JSON. Starting fresh.")
            return []

    def save(self, tweets: List[Dict[str, Any]]) -> None:
        """Saves tweets to cache file."""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, "w", encoding=UTF8) as f:
            json.dump(tweets, f, indent=JSON_INDENT)

    def build_tweet_map(
        self, tweets: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """Builds a map of tweet_id -> tweet for quick lookups."""
        return {t[TWEET_ID_KEY]: t for t in tweets if t.get(TWEET_ID_KEY)}

    def deduplicate(self, tweets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Removes duplicate tweets by ID, preserving order."""
        seen: set[str] = set()
        deduped: List[Dict[str, Any]] = []
        for t in tweets:
            tid = t.get(TWEET_ID_KEY)
            if tid and tid not in seen:
                seen.add(tid)
                deduped.append(t)
        return deduped
