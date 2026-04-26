"""Entry point for downloading tweets from X/Twitter likes."""

from typing import Any, Dict, List, Set

from backend.settings import LIKED_TWEETS_FILE
from backend.tweets.cache import TweetCache
from backend.tweets.downloader import XAPIClient
from backend.tweets.parser import TweetParser

TWEET_ID_KEY = "tweet_id"
DEFAULT_CONSECUTIVE_SEEN_LIMIT = 0  # 80


class TweetDownloader:
    """Downloads liked tweets for a user and saves them to a JSON file.

    Uses modular components:
    - XAPIClient for API calls
    - TweetParser for tweet extraction
    - TweetCache for persistence
    """

    def __init__(self):
        self.api_client = XAPIClient()
        self.cache = TweetCache(LIKED_TWEETS_FILE)

    def retrieve_all_likes(
        self, consecutive_seen_limit: int = DEFAULT_CONSECUTIVE_SEEN_LIMIT
    ):
        """Fetches all liked tweets, deduplicates, and saves to cache."""
        existing_tweets = self.cache.load()
        existing_tweet_map = self.cache.build_tweet_map(existing_tweets)
        existing_ids_before: Set[str] = set(existing_tweet_map.keys())
        first_run = not LIKED_TWEETS_FILE.exists()

        fetched_tweets: List[Dict[str, Any]] = []
        seen_streak = 0
        cursor = None
        old_cursor = None
        current_page = 1

        while True:
            print(f"Fetching likes page {current_page}...")
            page = self.api_client.fetch_likes_page(cursor)
            if not page:
                break

            for raw_tweet in page:
                tweet_parser = TweetParser(raw_tweet)
                if not tweet_parser.is_valid_tweet:
                    continue

                tweet = tweet_parser.tweet_as_json()
                tweet_id = tweet[TWEET_ID_KEY]

                if tweet_id not in existing_tweet_map:
                    seen_streak = 0
                    fetched_tweets.append(tweet)
                    continue

                seen_streak += 1
                if seen_streak >= consecutive_seen_limit:
                    print(
                        f"Hit {consecutive_seen_limit} consecutive known tweets. Stopping."
                    )
                    break

                fetched_tweets.append(tweet)

            if seen_streak >= consecutive_seen_limit:
                break

            next_cursor = self.api_client.get_cursor(page)
            if not next_cursor or next_cursor == old_cursor:
                break

            old_cursor = cursor
            cursor = next_cursor
            current_page += 1

        if first_run:
            self.cache.save(fetched_tweets)
            print(f"New tweets: {len(fetched_tweets)}")
            print(f"Total saved tweets: {len(fetched_tweets)}")
            return

        # Merge: overwrite the recently fetched window with fresh data,
        # but preserve older tweets that lie beyond the consecutive-seen cutoff.
        if fetched_tweets:
            oldest_fetched_id = fetched_tweets[-1][TWEET_ID_KEY]
            # find index of that id in existing_tweets
            try:
                idx = next(
                    i
                    for i, t in enumerate(existing_tweets)
                    if t.get(TWEET_ID_KEY) == oldest_fetched_id
                )
            except StopIteration:
                idx = None
            if idx is None:
                # no overlap found; conservatively append all existing tweets
                merged = fetched_tweets + existing_tweets
            else:
                # preserve only tweets older than the oldest fetched one
                merged = fetched_tweets + existing_tweets[idx + 1 :]
        else:
            # nothing fetched; keep existing tweets as-is
            merged = existing_tweets

        deduped = self.cache.deduplicate(merged)
        self.cache.save(deduped)

        final_ids = {t[TWEET_ID_KEY] for t in deduped if t.get(TWEET_ID_KEY)}
        new_ids = final_ids - existing_ids_before
        removed_ids = existing_ids_before - final_ids
        if len(new_ids) > 0:
            print(f"New tweets: {len(new_ids)}")
        if len(removed_ids) > 0:
            print(f"Tweets removed: {len(removed_ids)}")
        print(f"Total saved tweets: {len(deduped)}")


def main():
    downloader = TweetDownloader()
    print(
        f"Starting retrieval of likes for X user {downloader.api_client.x_user_id}..."
    )
    downloader.retrieve_all_likes()
    print(f"Done. Likes JSON saved to: {LIKED_TWEETS_FILE}")


if __name__ == "__main__":
    main()
