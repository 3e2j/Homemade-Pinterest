"""X/Twitter API client: Fetch likes from X platform."""

import json
import os
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

from backend.logger import error, info, warning

load_dotenv()

ENV_USER_ID = "USER_ID"
ENV_AUTHORIZATION = "HEADER_AUTHORIZATION"
ENV_COOKIES = "HEADER_COOKIES"
ENV_CSRF = "HEADER_CSRF"

LIKES_URL = "https://x.com/i/api/graphql/QK8AVO3RpcnbLPKXLAiVog/Likes"
LIKES_REQUEST_PAGE_SIZE = 80
REQUEST_TIMEOUT_SECONDS = 15

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
    "withV2Timeline": True,
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


class XAPIClient:
    """X API client for fetching user likes."""

    def __init__(self):
        self.x_user_id = os.getenv(ENV_USER_ID)
        self.header_authorization = os.getenv(ENV_AUTHORIZATION)
        self.header_cookie = os.getenv(ENV_COOKIES)
        self.header_csrf = os.getenv(ENV_CSRF)
        
        # Validate credentials are present
        if not self.x_user_id:
            error(f"Missing {ENV_USER_ID} in environment")
        if not self.header_authorization:
            error(f"Missing {ENV_AUTHORIZATION} in environment")
        if not self.header_cookie:
            error(f"Missing {ENV_COOKIES} in environment")
        if not self.header_csrf:
            error(f"Missing {ENV_CSRF} in environment")

    def fetch_likes_page(
        self, cursor: Optional[str] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """Fetches a single page of likes from X API."""
        variables_data_encoded = json.dumps(self._build_variables(cursor=cursor))
        features_data_encoded = json.dumps(self._build_features())
        try:
            response = requests.get(
                LIKES_URL,
                params={
                    "variables": variables_data_encoded,
                    "features": features_data_encoded,
                },
                headers=self._build_headers(),
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            return self.extract_entries(response.json())
        except requests.exceptions.Timeout:
            error("API request timed out")
            return None
        except requests.exceptions.HTTPError as e:
            error(f"API HTTP error: {e.response.status_code} - {e.response.text[:200]}")
            return None
        except Exception as e:
            error(f"Failed to fetch likes page: {e}")
            return None

    def extract_entries(
        self, raw_data: Dict[str, Any]
    ) -> Optional[List[Dict[str, Any]]]:
        """Extracts tweet entries from X API response."""
        try:
            if not isinstance(raw_data, dict):
                error(f"API response must be dict, got {type(raw_data).__name__}")
                return None
            
            user_result = raw_data.get("data", {}).get("user", {}).get("result")
            if not isinstance(user_result, dict):
                error("Invalid API response: cannot find user result")
                return None
            
            timeline = user_result.get("timeline_v2", {}).get("timeline")
            if not isinstance(timeline, dict):
                timeline = user_result.get("timeline", {}).get("timeline")
            if not isinstance(timeline, dict):
                error("Invalid API response: cannot find timeline")
                return None

            instructions = timeline.get("instructions", [])
            if not isinstance(instructions, list):
                error("Invalid API response: instructions must be list")
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
                warning("API response contains no entries")
                return None
            return entries
        except (KeyError, TypeError) as e:
            error(f"Failed to parse API response: {e}")
            return None

    def get_cursor(self, page_json: List[Dict[str, Any]]) -> Optional[str]:
        """Extracts pagination cursor from page entries."""
        if not isinstance(page_json, list):
            return None
        
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

    def _build_variables(self, cursor: Optional[str] = None) -> Dict[str, Any]:
        """Builds request variables for likes API call."""
        variables_data = {"userId": self.x_user_id, **LIKES_VARIABLES_BASE}
        if cursor:
            if not isinstance(cursor, str):
                warning(f"Cursor must be string, got {type(cursor).__name__}")
            else:
                variables_data["cursor"] = cursor
        return variables_data

    def _build_headers(self) -> Dict[str, str]:
        """Builds HTTP headers for likes API call."""
        authorization = self.header_authorization or ""
        cookie = self.header_cookie or ""
        csrf = self.header_csrf or ""

        return {
            **REQUEST_HEADERS_BASE,
            "Authorization": authorization,
            "Cookie": cookie,
            "x-csrf-token": csrf,
        }

    def _build_features(self) -> Dict[str, Any]:
        """Builds feature flags for likes API call."""
        return LIKES_FEATURE_FLAGS.copy()
