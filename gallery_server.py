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
from pathlib import Path
from http.server import SimpleHTTPRequestHandler
from urllib.parse import urlparse, unquote

import download_tweets
import parse_media  # adjust if your media script has a different name
import hashlib

# ==== Logging ====
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
LOG = logging.getLogger("gallery_server")

# ==== Constants ====
PORT = 8000
WS_PORT = 8765
CLIENT_TIMEOUT = 10
SHUTDOWN_WAIT = 1

STATIC_DIR = Path("src")
OUTPUT_DIR = Path("output")
LIKED_TWEETS_FILE = OUTPUT_DIR / "liked_tweets.json"
DATA_FILE = OUTPUT_DIR / "data.json"
IMAGES_DIR = OUTPUT_DIR / "images"

clients: dict = {}

# ==== File Change Detection ====
def file_fingerprint(path: Path):
    try:
        stat = path.stat()
        with open(path, 'rb') as f:
            data = f.read()
        return (stat.st_mtime_ns, stat.st_size, hashlib.md5(data).hexdigest())
    except FileNotFoundError:
        return None
    except Exception as e:
        LOG.error("fingerprint error for %s: %s", path, e)
        return None

# ==== Helper ====
def safe_path(root: Path, rel: str) -> Path | None:
    try:
        candidate = (root / rel).resolve()
        root_resolved = root.resolve()
        if root_resolved in candidate.parents or candidate == root_resolved:
            if candidate.exists():
                return candidate
    except Exception as e:
        LOG.error("safe_path error (%s / %s): %s", root, rel, e)
    return None

# ==== HTTP Handler ====
class GalleryRequestHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path: str) -> str:
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

            if req_path == "data.json":
                return str(DATA_FILE)

            return str(STATIC_DIR / "index.html")
        except Exception as e:
            LOG.error("translate_path failure for %s: %s", path, e)
            return str(STATIC_DIR / "index.html")

    # Only suppress routine 200 GET noise; keep errors.
    def log_message(self, fmt, *args):
        message = fmt % args
        if " 200 " in message and "GET" in message:
            LOG.debug(message)
        else:
            # Log non-200 or non-GET at info (errors surfaced elsewhere too)
            if any(code in message for code in (" 404 ", " 500 ")):
                LOG.warning(message)
            else:
                LOG.info(message)

    def do_POST(self):
        if self.path != "/refresh":
            self.send_error(404, "Unsupported POST endpoint")
            return

        try:
            before_ids = self._get_tweet_ids()
            before_fp = file_fingerprint(LIKED_TWEETS_FILE)
            download_tweets.main()  # may or may not add new tweets
            after_fp = file_fingerprint(LIKED_TWEETS_FILE)
            file_updated = before_fp != after_fp
            after_ids = self._get_tweet_ids()
            new_ids = after_ids - before_ids
            new_tweets = []
            if file_updated:
                # Always (re)process media if file changed (additions or removals)
                if new_ids:
                    LOG.info("Found %d new tweet(s); processing media...", len(new_ids))
                else:
                    LOG.info("Tweets file changed (no new tweets, likely removals); re-processing media...")
                try:
                    parse_media.main()
                except Exception as e:
                    LOG.error("Media parsing failed: %s", e)
                # Only compile list of new tweet objects if there were additions
                if new_ids:
                    try:
                        with open(LIKED_TWEETS_FILE, encoding="utf8") as f:
                            all_tweets = json.load(f)
                        new_tweets = [t for t in all_tweets if t.get("tweet_id") in new_ids]
                    except Exception as e:
                        LOG.error("Failed loading new tweets after media parse: %s", e)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "new_found": bool(new_ids),
                "new_tweets": new_tweets,
                "updated": bool(file_updated),
                "new_count": len(new_tweets)
            }).encode())
        except Exception as e:
            LOG.exception("Unhandled error in /refresh")
            try:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "internal", "detail": str(e)}).encode())
            except Exception:
                pass  # socket already broken

    def _get_tweet_ids(self) -> set[str]:
        try:
            with open(LIKED_TWEETS_FILE, encoding="utf8") as f:
                return {t.get("tweet_id") for t in json.load(f) if t.get("tweet_id")}
        except FileNotFoundError:
            return set()
        except Exception as e:
            LOG.error("Failed reading tweet IDs: %s", e)
            return set()

    # Harden against broken pipes
    def send_response(self, code, message=None):
        try:
            super().send_response(code, message)
        except BrokenPipeError:
            LOG.warning("BrokenPipe while sending response header")
            self.close_connection = True

    def send_header(self, key, value):
        try:
            super().send_header(key, value)
        except BrokenPipeError:
            LOG.debug("BrokenPipe while sending header %s", key)
            self.close_connection = True

    def end_headers(self):
        if self.path.startswith("/data.json"):
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        try:
            super().end_headers()
        except BrokenPipeError:
            LOG.debug("BrokenPipe in end_headers")
            self.close_connection = True

    def copyfile(self, source, outputfile):
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
        if (STATIC_DIR / "index.html").exists():
            try:
                webbrowser.open(f"http://localhost:{PORT}/")
            except Exception as e:
                LOG.debug("Browser open failed: %s", e)
        httpd.serve_forever()

# ==== WebSocket Client Monitoring ====
async def check_clients():
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

async def monitor_clients():
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

async def start_ws():
    LOG.info("[WebSocket] ws://localhost:%d", WS_PORT)
    async with websockets.serve(ws_handler, "0.0.0.0", WS_PORT):
        await monitor_clients()

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()
    try:
        asyncio.run(start_ws())
    except KeyboardInterrupt:
        LOG.info("Interrupted. Exiting.")

if __name__ == "__main__":
    main()

