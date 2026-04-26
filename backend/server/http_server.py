"""HTTP server for serving gallery and handling refresh requests."""

import hashlib
import json
import logging
import shutil
import socketserver
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, Optional, Set, Tuple
from urllib.parse import unquote, urlparse

import backend.download_tweets as download_tweets
import backend.media.processor as media_processor
from backend.settings import LIKED_TWEETS_FILE, PROCESSED_JSON
from backend.settings import FRONTEND_DIR, OUTPUT_DIR
from backend.server.config import DATA_ENDPOINT, OPEN_BROWSER, PORT, REFRESH_PATH

LOG = logging.getLogger("http_server")

STATIC_DIR = FRONTEND_DIR
DATA_FILE = PROCESSED_JSON

# Lock to serialize refresh operations across clients
_refresh_lock = threading.Lock()
# Broadcast function will be set by ws_handler
_broadcast_update = None


def set_broadcast_function(func):
    """Register the broadcast function from ws_handler."""
    global _broadcast_update
    _broadcast_update = func


def file_fingerprint(path: Path) -> Optional[Tuple[int, int, str]]:
    try:
        with open(path, "rb") as f:
            data = f.read()
        stat = path.stat()
        return stat.st_mtime_ns, stat.st_size, hashlib.md5(data).hexdigest()
    except FileNotFoundError:
        return None
    except Exception as e:
        LOG.error("fingerprint error for %s: %s", path, e)
        return None


def safe_path(root: Path, rel: str) -> Optional[Path]:
    try:
        candidate = (root / rel).resolve()
        root_base = root.resolve()
        if (candidate == root_base) or (root_base in candidate.parents):
            return candidate if candidate.exists() else None
    except Exception as e:
        LOG.error("safe_path error (%s / %s): %s", root, rel, e)
    return None


def read_json(path: Path, default):
    try:
        with open(path, encoding="utf8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except Exception as e:
        LOG.error("Failed to read %s: %s", path, e)
        return default


def write_json_response(
    handler: SimpleHTTPRequestHandler, payload: Dict[str, Any], status: int = 200
) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.end_headers()
    try:
        handler.wfile.write(json.dumps(payload).encode())
    except BrokenPipeError:
        LOG.debug("BrokenPipe writing JSON response")
        handler.close_connection = True


class GalleryRequestHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path: str) -> str:  # type: ignore[override]
        try:
            parsed = urlparse(path)
            req_path = unquote(parsed.path.lstrip("/"))

            if req_path == "" or req_path == "index.html":
                return str(STATIC_DIR / "index.html")

            static_hit = safe_path(STATIC_DIR, req_path)
            if static_hit:
                return str(static_hit)

            output_hit = safe_path(OUTPUT_DIR, req_path)
            if output_hit:
                return str(output_hit)

            if req_path == DATA_ENDPOINT:
                return str(DATA_FILE)

            return str(STATIC_DIR / "index.html")
        except Exception as e:
            LOG.error("translate_path failure for %s: %s", path, e)
            return str(STATIC_DIR / "index.html")

    # Only suppress routine 200 GET noise; keep errors.
    def log_message(self, fmt, *args):  # type: ignore[override]
        message = fmt % args
        if " 200 " in message and "GET" in message:
            LOG.debug(message)
        else:
            # Log non-200 or non-GET at info (errors surfaced elsewhere too)
            if any(code in message for code in (" 404 ", " 500 ")):
                LOG.warning(message)
            else:
                LOG.info(message)

    def do_POST(self):  # type: ignore[override]
        if self.path == REFRESH_PATH:
            self.handle_refresh()
        else:
            write_json_response(self, {"error": "not_found"}, 404)

    def _get_new_tweet_list(self, new_ids: Set[str]) -> list:
        """Extract new tweets from the cache that match new_ids."""
        if not new_ids:
            return []

        all_tweets = read_json(LIKED_TWEETS_FILE, [])
        if not isinstance(all_tweets, list):
            return []

        return [t for t in all_tweets if t.get("tweet_id") in new_ids]

    def handle_refresh(self) -> None:
        global _refresh_lock, _broadcast_update

        # Acquire lock to prevent concurrent refreshes from multiple clients
        with _refresh_lock:
            try:
                before_ids = self.get_tweet_ids()
                before_fp = file_fingerprint(LIKED_TWEETS_FILE)
                download_tweets.main()
                after_fp = file_fingerprint(LIKED_TWEETS_FILE)
                file_updated = before_fp != after_fp
                new_ids: Set[str] = set()

                if file_updated:
                    after_ids = self.get_tweet_ids()
                    new_ids = after_ids - before_ids
                    self.process_media(new_ids)

                new_tweets_list = self._get_new_tweet_list(new_ids)

                # Broadcast update to all other connected clients
                if _broadcast_update and file_updated:
                    _broadcast_update()

                write_json_response(
                    self,
                    {
                        "new_found": bool(new_ids),
                        "new_tweets": new_tweets_list,
                        "updated": bool(file_updated),
                        "new_count": len(new_tweets_list),
                    },
                )
            except Exception as e:
                LOG.exception("Refresh failed")
                write_json_response(self, {"error": "internal", "detail": str(e)}, 500)

    def process_media(self, new_ids: Set[str]) -> None:
        if not new_ids:
            LOG.info(
                "Tweets file changed (no new tweets, likely removals); re-processing media..."
            )
        else:
            LOG.info("Found %d new tweet(s); processing media...", len(new_ids))
        try:
            media_processor.main()
        except Exception as e:
            LOG.error("Media processing failed: %s", e)

    def get_tweet_ids(self) -> Set[str]:
        data = read_json(LIKED_TWEETS_FILE, [])
        if not isinstance(data, list):
            return set()
        ids: Set[str] = set()
        for item in data:
            if not isinstance(item, dict):
                continue
            tid = item.get("tweet_id")
            if tid:
                ids.add(str(tid))
        return ids

    # Harden against broken pipes
    def send_response(self, code, message=None):  # type: ignore[override]
        try:
            super().send_response(code, message)
        except BrokenPipeError:
            LOG.warning("BrokenPipe while sending response header")
            self.close_connection = True

    def send_header(self, key, value):  # type: ignore[override]
        try:
            super().send_header(key, value)
        except BrokenPipeError:
            LOG.debug("BrokenPipe while sending header %s", key)
            self.close_connection = True

    def end_headers(self):  # type: ignore[override]
        if self.path.startswith("/data.json"):
            self.send_header(
                "Cache-Control", "no-store, no-cache, must-revalidate, max-age=0"
            )
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        try:
            super().end_headers()
        except BrokenPipeError:
            LOG.debug("BrokenPipe in end_headers")
            self.close_connection = True

    def copyfile(self, source, outputfile):  # type: ignore[override]
        try:
            shutil.copyfileobj(source, outputfile)
        except BrokenPipeError:
            LOG.debug("BrokenPipe during body copy")
            self.close_connection = True
        except Exception as e:
            LOG.error("copyfile error: %s", e)
            self.close_connection = True


class ThreadedHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True


def start_http_server():
    with ThreadedHTTPServer(("0.0.0.0", PORT), GalleryRequestHandler) as httpd:
        LOG.info("[HTTP] Serving at http://localhost:%d", PORT)
        if OPEN_BROWSER and (STATIC_DIR / "index.html").exists():
            try:
                webbrowser.open(f"http://localhost:{PORT}/")
            except Exception as e:
                LOG.debug("Browser open failed: %s", e)
        httpd.serve_forever()
