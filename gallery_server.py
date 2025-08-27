import os
import time
import shutil
import threading
import asyncio
import socketserver
import webbrowser
import websockets
from pathlib import Path
from http.server import SimpleHTTPRequestHandler
import json

import download_tweets
import parse_media

# ==== Constants ====
PORT = 8000
WS_PORT = 8765
CLIENT_TIMEOUT = 10  # seconds of client inactivity before shutdown
SHUTDOWN_WAIT = 1    # seconds to wait after last client disconnect before shutdown
SOURCE_DIR = Path("output")
LIKED_TWEETS_FILE = SOURCE_DIR / "liked_tweets.json"

clients = {}

# ==== HTTP Handler ====
class GalleryRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SOURCE_DIR), **kwargs)

    def send_response(self, code, message=None):
        try:
            super().send_response(code, message)
        except BrokenPipeError:
            self.close_connection = True

    def send_header(self, keyword, value):
        try:
            super().send_header(keyword, value)
        except BrokenPipeError:
            self.close_connection = True

    def end_headers(self):
        try:
            super().end_headers()
        except BrokenPipeError:
            self.close_connection = True

    def copyfile(self, source, outputfile):
        try:
            shutil.copyfileobj(source, outputfile)
        except (BrokenPipeError, Exception):
            self.close_connection = True

    def do_POST(self):
        if self.path == "/refresh":
            # Run download_tweets and check if new tweets were added
            tweets_before = self.get_tweet_ids()
            updated = download_tweets.main()  # Should return True if liked_tweets.json was updated
            tweets_after = self.get_tweet_ids()
            new_tweet_ids = tweets_after - tweets_before

            new_tweets = []
            if new_tweet_ids:
                # Only run parse_media if there are new tweets
                parse_media.main()
                # Load new tweets to send to client
                with open(LIKED_TWEETS_FILE, encoding="utf8") as f:
                    all_tweets = json.load(f)
                    new_tweets = [t for t in all_tweets if t.get("tweet_id") in new_tweet_ids]

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "new_found": bool(new_tweet_ids),
                "new_tweets": new_tweets
            }).encode())
        else:
            self.send_error(404)

    def get_tweet_ids(self):
        try:
            with open(LIKED_TWEETS_FILE, encoding="utf8") as f:
                return set(t.get("tweet_id") for t in json.load(f) if t.get("tweet_id"))
        except Exception:
            return set()

# ==== Threaded HTTP Server ====
class ThreadedHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True

def start_http_server():
    with ThreadedHTTPServer(("0.0.0.0", PORT), GalleryRequestHandler) as httpd:
        print(f"[HTTP] Serving at http://0.0.0.0:{PORT}")
        webbrowser.open(f"http://localhost:{PORT}/index.html")
        httpd.serve_forever()

# ==== WebSocket Client Monitoring ====
async def check_clients():
    now = time.time()
    inactive = [ws for ws, last_seen in clients.items() if now - last_seen > CLIENT_TIMEOUT]
    for ws in inactive:
        print("[Monitor] Removing inactive client")
        clients.pop(ws, None)
    if not clients:
        print("[Monitor] No active clients. Waiting before shutdown...")
        await asyncio.sleep(SHUTDOWN_WAIT)
        if not clients:
            print("[Monitor] Still no active clients after wait. Shutting down.")
            os._exit(0)

async def monitor_clients():
    while True:
        await asyncio.sleep(CLIENT_TIMEOUT)
        await check_clients()

async def ws_handler(websocket):
    print("[WebSocket] Client connected")
    clients[websocket] = time.time()
    try:
        async for message in websocket:
            if message == "ping":
                clients[websocket] = time.time()
            elif message == "close":
                print("[WebSocket] Received close signal from client.")
                break
    except websockets.ConnectionClosed:
        print("[WebSocket] Client disconnected")
    finally:
        clients.pop(websocket, None)
        await check_clients()

async def start_websocket_server():
    print(f"[WebSocket] Serving at ws://0.0.0.0:{WS_PORT}")
    async with websockets.serve(ws_handler, "0.0.0.0", WS_PORT):
        await monitor_clients()

# ==== Main Entrypoint ====
def main():
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()
    asyncio.run(start_websocket_server())

if __name__ == "__main__":
    main()

