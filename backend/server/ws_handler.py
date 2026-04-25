"""WebSocket server for client connections and heartbeat monitoring."""

import asyncio
import logging
import os
import time
from typing import Any, Dict

import websockets

from backend.server.config import WS_PORT, CLIENT_TIMEOUT, SHUTDOWN_WAIT

LOG = logging.getLogger("ws_handler")

clients: Dict[Any, float] = {}


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
