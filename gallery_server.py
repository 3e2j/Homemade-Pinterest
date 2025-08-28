import os
import time
import shutil
import threading
import asyncio
import socketserver
import webbrowser
import websockets
import json
import logging
import hashlib
from pathlib import Path
from http.server import SimpleHTTPRequestHandler
from urllib.parse import urlparse, unquote
from typing import Optional, Set, Dict, Any, Tuple

import download_tweets
import parse_media

# ==== Logging ====
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
LOG = logging.getLogger("gallery_server")

# ==== Constants ====
PORT = 8000
WS_PORT = 8765
CLIENT_TIMEOUT = 10          # seconds since last ping before a client is stale
SHUTDOWN_WAIT = 1            # grace period before shutdown when no clients
REFRESH_PATH = "/refresh"
DATA_ENDPOINT = "data.json"
OPEN_BROWSER = True

STATIC_DIR = Path("src")
OUTPUT_DIR = Path("output")
LIKED_TWEETS_FILE = OUTPUT_DIR / "liked_tweets.json"
DATA_FILE = OUTPUT_DIR / "data.json"
IMAGES_DIR = OUTPUT_DIR / "images"

clients: Dict[Any, float] = {}

# ==== File Change Detection ====
def file_fingerprint(path: Path) -> Optional[Tuple[int, int, str]]:
    try:
        with open(path, 'rb') as f:
            data = f.read()
        stat = path.stat()
        return stat.st_mtime_ns, stat.st_size, hashlib.md5(data).hexdigest()
    except FileNotFoundError:
        return None
    except Exception as e:
        LOG.error("fingerprint error for %s: %s", path, e)
        return None

# ==== Helper ====
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

def write_json_response(handler: SimpleHTTPRequestHandler, payload: Dict[str, Any], status: int = 200) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.end_headers()
    try:
        handler.wfile.write(json.dumps(payload).encode())
    except BrokenPipeError:
        LOG.debug("BrokenPipe writing JSON response")
        handler.close_connection = True

# ==== HTTP Handler ====
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
            self._handle_refresh()
        else:
            write_json_response(self, {"error": "not_found"}, 404)

    # --- Refresh Logic ---
    def _handle_refresh(self) -> None:
        try:
            before_ids = self._get_tweet_ids()
            before_fp = file_fingerprint(LIKED_TWEETS_FILE)
            download_tweets.main()
            after_fp = file_fingerprint(LIKED_TWEETS_FILE)
            file_updated = before_fp != after_fp
            new_tweets_list = []
            new_ids: Set[str] = set()
            if file_updated:
                after_ids = self._get_tweet_ids()
                new_ids = after_ids - before_ids
                self._process_media(new_ids)
                if new_ids:
                    all_tweets = read_json(LIKED_TWEETS_FILE, [])
                    if isinstance(all_tweets, list):
                        new_tweets_list = [t for t in all_tweets if t.get("tweet_id") in new_ids]
            write_json_response(self, {
                "new_found": bool(new_ids),
                "new_tweets": new_tweets_list,
                "updated": bool(file_updated),
                "new_count": len(new_tweets_list)
            })
        except Exception as e:
            LOG.exception("Refresh failed")
            write_json_response(self, {"error": "internal", "detail": str(e)}, 500)

    def _process_media(self, new_ids: Set[str]) -> None:
        if not new_ids:
            LOG.info("Tweets file changed (no new tweets, likely removals); re-processing media...")
        else:
            LOG.info("Found %d new tweet(s); processing media...", len(new_ids))
        try:
            parse_media.main()
        except Exception as e:
            LOG.error("Media parsing failed: %s", e)

    def _get_tweet_ids(self) -> Set[str]:
        data = read_json(LIKED_TWEETS_FILE, [])
        if not isinstance(data, list):
            return set()
        return {t.get("tweet_id") for t in data if isinstance(t, dict) and t.get("tweet_id")}

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
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
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

# ==== Threaded HTTP Server ====
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

# ==== WebSocket Client Monitoring ====
async def check_clients() -> None:
    now = time.time()
    stale = [ws for ws, last in clients.items() if now - last > CLIENT_TIMEOUT]
    for ws in stale:
        clients.pop(ws, None)
        LOG.info("Removed inactive client")
    if not clients:
        LOG.info("No active clients. Waiting %ss before shutdown...", SHUTDOWN_WAIT)
        await asyncio.sleep(SHUTDOWN_WAIT)
        if not clients:
            LOG.info("Shutting down (no clients).")
            os._exit(0)

async def monitor_clients() -> None:
    while True:
        await asyncio.sleep(CLIENT_TIMEOUT)
        await check_clients()

async def ws_handler(websocket):
    LOG.info("[WebSocket] Client connected")
    clients[websocket] = time.time()
    try:
        async for msg in websocket:
            if msg == "ping":
                clients[websocket] = time.time()
            elif msg == "close":
                LOG.info("[WebSocket] Client requested close")
                break
    except websockets.ConnectionClosed:
        LOG.info("[WebSocket] Client disconnected")
    except Exception as e:
        LOG.error("WebSocket error: %s", e)
    finally:
        clients.pop(websocket, None)
        await check_clients()

async def start_ws() -> None:
    LOG.info("[WebSocket] ws://localhost:%d", WS_PORT)
    async with websockets.serve(ws_handler, "0.0.0.0", WS_PORT):
        await monitor_clients()

def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()
    try:
        asyncio.run(start_ws())
    except KeyboardInterrupt:
        LOG.info("Interrupted. Exiting.")

if __name__ == "__main__":
    main()

