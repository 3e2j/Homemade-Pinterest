import json
import requests
from pathlib import Path
from typing import Optional, List, Dict, Any

from tweet_parser import TweetParser

CONFIG_FILE = Path("config.json")
OUTPUT_DIR = Path("output")
OUTPUT_FILE = OUTPUT_DIR / "liked_tweets.json"

# ---- Constants ----
DEFAULT_CONSECUTIVE_SEEN_LIMIT = 50
LIKES_REQUEST_PAGE_SIZE = 100
REQUEST_TIMEOUT_SECONDS = 15


class TweetDownloader:
    """
    Downloads liked tweets for a user and saves them to a JSON file.
    """

    def __init__(self):
        self._load_config()

    def _load_config(self):
        with open(CONFIG_FILE, encoding="utf8") as f:
            config = json.load(f)
        self.twitter_user_id = config.get('USER_ID')
        self.header_authorization = config.get('HEADER_AUTHORIZATION')
        self.header_cookie = config.get('HEADER_COOKIES')
        self.header_csrf = config.get('HEADER_CSRF')

    def retrieve_all_likes(self, consecutive_seen_limit: int = DEFAULT_CONSECUTIVE_SEEN_LIMIT):
        """
        Fetches all liked tweets, deduplicates, and saves to OUTPUT_FILE.
        """
        existing_tweets: list[dict] = []
        existing_tweet_map: dict[str, dict] = {}
        first_run = not Path(OUTPUT_FILE).exists()
        existing_ids_before: set[str] = set()

        if not first_run:
            try:
                with open(OUTPUT_FILE, 'r', encoding="utf8") as f:
                    existing_tweets = json.load(f)
                    existing_tweet_map = {t["tweet_id"]: t for t in existing_tweets if t.get("tweet_id")}
                    existing_ids_before = set(existing_tweet_map.keys())
            except (json.JSONDecodeError, FileNotFoundError):
                print("Invalid or missing JSON. Starting fresh.")
                first_run = True

        fetched_tweets: list[dict] = []
        fetched_ids: set[str] = set()
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
                tweet_id = tweet["tweet_id"]

                if tweet_id in existing_tweet_map:
                    seen_streak += 1
                    if seen_streak >= consecutive_seen_limit:
                        print(f"Hit {consecutive_seen_limit} consecutive known tweets. Stopping.")
                        break
                else:
                    seen_streak = 0

                fetched_ids.add(tweet_id)
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
            with open(OUTPUT_FILE, 'w', encoding="utf8") as f:
                json.dump(fetched_tweets, f, indent=2)
            print(f"New tweets: {len(fetched_tweets)}")
            print(f"Total saved tweets: {len(fetched_tweets)}")
            return

    # Merge: overwrite the recently fetched window with fresh data,
    # but preserve older tweets that lie beyond the consecutive-seen cutoff.
        if fetched_tweets:
            oldest_fetched_id = fetched_tweets[-1]["tweet_id"]
            # find index of that id in existing_tweets
            try:
                idx = next(i for i, t in enumerate(existing_tweets) if t.get("tweet_id") == oldest_fetched_id)
            except StopIteration:
                idx = None
            if idx is None:
                # no overlap found; conservatively append all existing tweets
                merged = fetched_tweets + existing_tweets
            else:
                # preserve only tweets older than the oldest fetched one
                merged = fetched_tweets + existing_tweets[idx + 1:]
        else:
            # nothing fetched; keep existing tweets as-is
            merged = existing_tweets

        seen: set[str] = set()
        deduped: list[dict] = []
        for t in merged:
            tid = t["tweet_id"]
            if tid not in seen:
                seen.add(tid)
                deduped.append(t)

        with open(OUTPUT_FILE, 'w', encoding="utf8") as f:
            json.dump(deduped, f, indent=2)

        final_ids = {t["tweet_id"] for t in deduped}
        new_ids = final_ids - existing_ids_before
        removed_ids = existing_ids_before - final_ids
        if len(new_ids) > 0:
            print(f"New tweets: {len(new_ids)}")
        if len(removed_ids) > 0:
            print(f"Tweets removed: {len(removed_ids)}")
        print(f"Total saved tweets: {len(deduped)}")

    def retrieve_likes_page(self, cursor: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """
        Fetches a single page of likes.
        """
        likes_url = 'https://api.twitter.com/graphql/QK8AVO3RpcnbLPKXLAiVog/Likes'
        variables_data_encoded = json.dumps(self.likes_request_variables_data(cursor=cursor))
        features_data_encoded = json.dumps(self.likes_request_features_data())
        try:
            response = requests.get(
                likes_url,
                params={"variables": variables_data_encoded, "features": features_data_encoded},
                headers=self.likes_request_headers(),
                timeout=REQUEST_TIMEOUT_SECONDS
            )
            response.raise_for_status()
            return self.extract_likes_entries(response.json())
        except Exception as e:
            print(f"Failed to fetch likes page: {e}")
            return None

    def extract_likes_entries(self, raw_data: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        try:
            return raw_data['data']['user']['result']['timeline_v2']['timeline']['instructions'][0]['entries']
        except (KeyError, IndexError, TypeError):
            print("Failed to extract likes entries from response.")
            return None

    def get_cursor(self, page_json: List[Dict[str, Any]]) -> Optional[str]:
        try:
            return page_json[-1]['content']['value']
        except (KeyError, IndexError, TypeError):
            return None

    def likes_request_variables_data(self, cursor: Optional[str] = None) -> Dict[str, Any]:
        variables_data = {
            "userId": self.twitter_user_id,
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
            "withV2Timeline": True
        }
        if cursor:
            variables_data["cursor"] = cursor
        return variables_data

    def likes_request_headers(self) -> Dict[str, str]:
        return {
            'Content-Type': 'application/json',
            'Accept': '*/*',
            'Authorization': self.header_authorization,
            'Accept-Language': 'en-US,en;q=0.9',
            'Host': 'api.twitter.com',
            'Origin': 'https://twitter.com',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15',
            'Referer': 'https://twitter.com/',
            'Connection': 'keep-alive',
            'Cookie': self.header_cookie,
            'x-twitter-active-user': 'yes',
            'x-twitter-client-language': 'en',
            'x-csrf-token': self.header_csrf,
            'x-twitter-auth-type': 'OAuth2Session'
        }

    def likes_request_features_data(self) -> Dict[str, Any]:
        return {
            "responsive_web_twitter_blue_verified_badge_is_enabled": True,
            "verified_phone_label_enabled": False,
            "responsive_web_graphql_timeline_navigation_enabled": True,
            "view_counts_public_visibility_enabled": True,
            "view_counts_everywhere_api_enabled": True,
            "longform_notetweets_consumption_enabled": False,
            "tweetypie_unmention_optimization_enabled": True,
            "responsive_web_uc_gql_enabled": True,
            "vibe_api_enabled": True,
            "responsive_web_edit_tweet_api_enabled": True,
            "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
            "standardized_nudges_misinfo": True,
            "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": False,
            "interactive_text_enabled": True,
            "responsive_web_text_conversations_enabled": False,
            "responsive_web_enhance_cards_enabled": False
        }


def main():
    downloader = TweetDownloader()
    print(f'Starting retrieval of likes for Twitter user {downloader.twitter_user_id}...')
    downloader.retrieve_all_likes()
    print(f'Done. Likes JSON saved to: {OUTPUT_FILE}')

if __name__ == "__main__":
    main()