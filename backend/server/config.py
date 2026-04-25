"""Server configuration and constants."""

PORT = 8000
OPEN_BROWSER = True

# WebSocket Server settings
WS_PORT = 8765
CLIENT_TIMEOUT = 10  # seconds since last ping before a client is stale
SHUTDOWN_WAIT = 1  # grace period before shutdown when no clients

REFRESH_PATH = "/refresh"
DATA_ENDPOINT = "data.json"
