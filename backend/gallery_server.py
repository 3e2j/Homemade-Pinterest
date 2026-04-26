"""Main gallery server orchestration."""

import asyncio
import logging
import threading

from backend.settings import OUTPUT_DIR
from backend.server import http_server, ws_handler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
LOG = logging.getLogger("gallery_server")


def main() -> None:
    """Start HTTP and WebSocket servers."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Register the broadcast function so HTTP server can notify clients
    http_server.set_broadcast_function(ws_handler.broadcast_update)
    
    http_thread = threading.Thread(
        target=http_server.start_http_server, daemon=True
    )
    http_thread.start()
    try:
        asyncio.run(ws_handler.start_ws())
    except KeyboardInterrupt:
        LOG.info("Interrupted. Exiting.")


if __name__ == "__main__":
    main()
