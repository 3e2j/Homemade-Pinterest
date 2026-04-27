"""Tweet parsing: Extract structured data from X API responses."""

from backend.logger import warning

VIDEO_MEDIA_TYPES = {"video", "animated_gif"}
MP4_CONTENT_TYPE = "video/mp4"


class TweetParser:
    def __init__(self, raw_tweet_json):
        self.is_valid_tweet = True
        self.raw_tweet_json = raw_tweet_json
        self._media_urls = None
        self.key_data = {}

        if not isinstance(raw_tweet_json, dict):
            warning(f"Tweet must be dict, got {type(raw_tweet_json).__name__}")
            self.is_valid_tweet = False
            return

        content = raw_tweet_json.get("content", {})
        if not isinstance(content, dict):
            self.is_valid_tweet = False
            return
        
        item_content = content.get("itemContent", {})
        if not isinstance(item_content, dict):
            self.is_valid_tweet = False
            return

        result = item_content.get("tweet_results", {}).get("result")
        if not isinstance(result, dict):
            self.is_valid_tweet = False
            return

        # Some GraphQL responses wrap the tweet object under `result.tweet`.
        if isinstance(result.get("tweet"), dict):
            result = result["tweet"]

        legacy = result.get("legacy")
        if not isinstance(legacy, dict) or not legacy.get("id_str"):
            self.is_valid_tweet = False
            return

        self.key_data = result

    def tweet_as_json(self):
        return {
            "tweet_id": self.tweet_id,
            "user_handle": self.user_handle,
            "user_name": self.user_name,
            "user_avatar_url": self.user_avatar_url,
            "tweet_content": self.tweet_content,
            "tweet_media_urls": self.media_urls,
            "possibly_sensitive": self.possibly_sensitive,
        }

    @property
    def tweet_id(self):
        return self.key_data.get("legacy", {}).get("id_str", "")

    @property
    def tweet_content(self):
        return self.key_data.get("legacy", {}).get("full_text", "")

    @property
    def user_handle(self):
        return self.user_data.get("screen_name", "")

    @property
    def user_name(self):
        return self.user_data.get("name", "")

    @property
    def user_avatar_url(self):
        return self.user_data.get("profile_image_url_https", "")

    @property
    def user_data(self):
        core = self.key_data.get("core", {})
        user_results = core.get("user_results", {}) if isinstance(core, dict) else {}
        result = (
            user_results.get("result", {}) if isinstance(user_results, dict) else {}
        )
        legacy = result.get("legacy", {}) if isinstance(result, dict) else {}
        return legacy if isinstance(legacy, dict) else {}

    def _best_video_variant_url(self, media_entry):
        video_info = media_entry.get("video_info", {})
        variants = (
            video_info.get("variants", []) if isinstance(video_info, dict) else []
        )

        best_url = None
        best_bitrate = -1
        for variant in variants:
            if not isinstance(variant, dict):
                continue
            if variant.get("content_type") != MP4_CONTENT_TYPE:
                continue
            url = variant.get("url")
            if not isinstance(url, str) or not url:
                continue
            bitrate = variant.get("bitrate", 0)
            if isinstance(bitrate, int) and bitrate > best_bitrate:
                best_bitrate = bitrate
                best_url = url

        return best_url

    def _strip_query(self, url: str) -> str:
        """Remove query tags ("?" onwards)"""
        return url.split("?")[0]

    def _extract_media_url(self, media_entry):
        media_type = media_entry.get("type")
        if media_type in VIDEO_MEDIA_TYPES:
            video_url = self._best_video_variant_url(media_entry)
            if video_url:
                return self._strip_query(video_url)
        media_url = media_entry.get("media_url_https")
        if isinstance(media_url, str) and media_url:
            return self._strip_query(media_url)
        expanded_url = media_entry.get("expanded_url")
        if isinstance(expanded_url, str) and expanded_url:
            return self._strip_query(expanded_url)
        return None

    @property
    def media_urls(self):
        if self._media_urls is None:
            self._media_urls = []
            entities = self.key_data.get("legacy", {}).get("extended_entities", {})
            if not isinstance(entities, dict):
                entities = self.key_data.get("legacy", {}).get("entities", {})
            media_entries = (
                entities.get("media", []) if isinstance(entities, dict) else []
            )
            for entry in media_entries:
                if not isinstance(entry, dict):
                    continue
                media_url = self._extract_media_url(entry)
                if media_url:
                    self._media_urls.append(media_url)
        return self._media_urls

    @property
    def possibly_sensitive(self):
        legacy_sensitive = self.key_data.get("legacy", {}).get("possibly_sensitive")
        if isinstance(legacy_sensitive, bool):
            return legacy_sensitive
        user_sensitive = self.user_data.get("possibly_sensitive")
        return bool(user_sensitive) if user_sensitive is not None else False
