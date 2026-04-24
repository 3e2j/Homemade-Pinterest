import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

from app.paths import OUTPUT_DIR
from app.tweet_parser import TweetParser

# Load environment variables from .env file
load_dotenv()

# ---- Constants ----
UTF8 = "utf8"
JSON_INDENT = 2
TWEET_ID_KEY = "tweet_id"

ENV_USER_ID = "USER_ID"
ENV_AUTHORIZATION = "HEADER_AUTHORIZATION"
ENV_COOKIES = "HEADER_COOKIES"
ENV_CSRF = "HEADER_CSRF"

OUTPUT_FILE = OUTPUT_DIR / "liked_tweets.json"
LIKES_REQUEST_PAGE_SIZE = 80
DEFAULT_CONSECUTIVE_SEEN_LIMIT = LIKES_REQUEST_PAGE_SIZE
REQUEST_TIMEOUT_SECONDS = 15

LIKES_URL = "https://x.com/i/api/graphql/QK8AVO3RpcnbLPKXLAiVog/Likes"

REQUEST_HEADERS_BASE = {
    "Content-Type": "application/json",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Host": "x.com",
    "Origin": "https://x.com",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15",
    "Referer": "https://x.com/",
    "Connection": "keep-alive",
}

LIKES_VARIABLES_BASE = {
    "count": LIKES_REQUEST_PAGE_SIZE,
    "includePromotedContent": False,
    "withSuperFollowsUserFields": False,
    "withDownvotePerspective": False,
    "withReactionsMetadata": False,
    "withReactionsPerspective": False,
    "withSuperFollowsTweetFields": False,
    "withClientEventToken": False,
    "withBirdwatchNotes": False,
    "withVoice": False,
    "withV2Timeline": False,
}

LIKES_FEATURE_FLAGS = {
    "verified_phone_label_enabled": False,
    "responsive_web_graphql_timeline_navigation_enabled": False,
    "view_counts_public_visibility_enabled": False,
    "view_counts_everywhere_api_enabled": False,
    "longform_notetweets_consumption_enabled": False,
    "tweetypie_unmention_optimization_enabled": False,
    "responsive_web_uc_gql_enabled": False,
    "vibe_api_enabled": False,
    "responsive_web_edit_tweet_api_enabled": False,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": False,
    "standardized_nudges_misinfo": False,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": False,
    "interactive_text_enabled": False,
    "responsive_web_text_conversations_enabled": False,
    "responsive_web_enhance_cards_enabled": False,
}


class TweetDownloader:
    """
    Downloads liked tweets for a user and saves them to a JSON file.
    """

    def __init__(self):
        self.load_config()

    def load_config(self):
        # Load secrets from environment variables
        self.x_user_id = os.getenv(ENV_USER_ID)
        self.header_authorization = os.getenv(ENV_AUTHORIZATION)
        self.header_cookie = os.getenv(ENV_COOKIES)
        self.header_csrf = os.getenv(ENV_CSRF)

    def retrieve_all_likes(
        self, consecutive_seen_limit: int = DEFAULT_CONSECUTIVE_SEEN_LIMIT
    ):
        """
        Fetches all liked tweets, deduplicates, and saves to OUTPUT_FILE.
        """
        existing_tweets: list[dict] = []
        existing_tweet_map: dict[str, dict] = {}
        first_run = not Path(OUTPUT_FILE).exists()
        existing_ids_before: set[str] = set()

        if not first_run:
            try:
                with open(OUTPUT_FILE, "r", encoding=UTF8) as f:
                    existing_tweets = json.load(f)
                    existing_tweet_map = {
                        t[TWEET_ID_KEY]: t
                        for t in existing_tweets
                        if t.get(TWEET_ID_KEY)
                    }
                    existing_ids_before = set(existing_tweet_map.keys())
            except (json.JSONDecodeError, FileNotFoundError):
                print("Invalid or missing JSON. Starting fresh.")
                first_run = True

        fetched_tweets: list[dict] = []
        seen_streak = 0
        cursor = None
        old_cursor = None
        current_page = 1

        while True:
            print(f"Fetching likes page {current_page}...")
            page = self.retrieve_likes_page(cursor)
            if not page:
                break

            for raw_tweet in page:
                tweet_parser = TweetParser(raw_tweet)
                if not tweet_parser.is_valid_tweet:
                    continue

                tweet = tweet_parser.tweet_as_json()
                tweet_id = tweet[TWEET_ID_KEY]

                if tweet_id in existing_tweet_map:
                    seen_streak += 1
                    if seen_streak >= consecutive_seen_limit:
                        print(
                            f"Hit {consecutive_seen_limit} consecutive known tweets. Stopping."
                        )
                        break
                else:
                    seen_streak = 0

                fetched_tweets.append(tweet)

            if seen_streak >= consecutive_seen_limit:
                break

            next_cursor = self.get_cursor(page)
            if not next_cursor or next_cursor == old_cursor:
                break

            old_cursor = cursor
            cursor = next_cursor
            current_page += 1

        if first_run:
            with open(OUTPUT_FILE, "w", encoding=UTF8) as f:
                json.dump(fetched_tweets, f, indent=JSON_INDENT)
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

        seen: set[str] = set()
        deduped: list[dict] = []
        for t in merged:
            tid = t[TWEET_ID_KEY]
            if tid not in seen:
                seen.add(tid)
                deduped.append(t)

        with open(OUTPUT_FILE, "w", encoding=UTF8) as f:
            json.dump(deduped, f, indent=JSON_INDENT)

        final_ids = {t[TWEET_ID_KEY] for t in deduped}
        new_ids = final_ids - existing_ids_before
        removed_ids = existing_ids_before - final_ids
        if len(new_ids) > 0:
            print(f"New tweets: {len(new_ids)}")
        if len(removed_ids) > 0:
            print(f"Tweets removed: {len(removed_ids)}")
        print(f"Total saved tweets: {len(deduped)}")

    def retrieve_likes_page(
        self, cursor: Optional[str] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Fetches a single page of likes.
        """
        variables_data_encoded = json.dumps(
            self.likes_request_variables_data(cursor=cursor)
        )
        features_data_encoded = json.dumps(self.likes_request_features_data())
        try:
            response = requests.get(
                LIKES_URL,
                params={
                    "variables": variables_data_encoded,
                    "features": features_data_encoded,
                },
                headers=self.likes_request_headers(),
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            return self.extract_likes_entries(response.json())
        except Exception as e:
            print(f"Failed to fetch likes page: {e}")
            return None

    def extract_likes_entries(
        self, raw_data: Dict[str, Any]
    ) -> Optional[List[Dict[str, Any]]]:
        try:
            user_result = raw_data["data"]["user"]["result"]
            timeline = user_result.get("timeline_v2", {}).get("timeline")
            if not isinstance(timeline, dict):
                # Fallback shape seen in some responses when V2 flags differ.
                timeline = user_result.get("timeline", {}).get("timeline")
            if not isinstance(timeline, dict):
                print("Failed to extract likes entries from response.")
                return None

            instructions = timeline.get("instructions", [])
            if not isinstance(instructions, list):
                print("Failed to extract likes entries from response.")
                return None

            entries: List[Dict[str, Any]] = []
            for instruction in instructions:
                if not isinstance(instruction, dict):
                    continue
                instruction_entries = instruction.get("entries", [])
                if isinstance(instruction_entries, list):
                    entries.extend(
                        entry
                        for entry in instruction_entries
                        if isinstance(entry, dict)
                    )

            if not entries:
                print("Failed to extract likes entries from response.")
                return None
            return entries
        except (KeyError, TypeError):
            print("Failed to extract likes entries from response.")
            return None

    def get_cursor(self, page_json: List[Dict[str, Any]]) -> Optional[str]:
        for entry in reversed(page_json):
            if not isinstance(entry, dict):
                continue
            content = entry.get("content", {})
            if not isinstance(content, dict):
                continue
            value = content.get("value")
            if isinstance(value, str) and value:
                return value
        return None

    def likes_request_variables_data(
        self, cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        variables_data = {"userId": self.x_user_id, **LIKES_VARIABLES_BASE}
        if cursor:
            variables_data["cursor"] = cursor
        return variables_data

    def likes_request_headers(self) -> Dict[str, str]:
        # os.getenv may return None, but headers must be strings.
        # Coerce possible None values to empty strings to satisfy the return type.
        authorization = self.header_authorization or ""
        cookie = self.header_cookie or ""
        csrf = self.header_csrf or ""

        return {
            **REQUEST_HEADERS_BASE,
            "Authorization": authorization,
            "Cookie": cookie,
            "x-csrf-token": csrf,
        }

    def likes_request_features_data(self) -> Dict[str, Any]:
        return LIKES_FEATURE_FLAGS.copy()


def main():
    downloader = TweetDownloader()
    print(f"Starting retrieval of likes for X user {downloader.x_user_id}...")
    downloader.retrieve_all_likes()
    print(f"Done. Likes JSON saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
