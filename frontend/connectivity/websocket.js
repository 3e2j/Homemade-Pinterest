import { WS_PORT, WS_PING_INTERVAL_MS } from "../store/store.js";

const MESSAGE_TYPES = {
  PING: "ping",
  PONG: "pong",
  CLOSE: "close",
  UPDATE: "update",
};

function createPingMessage() {
  return MESSAGE_TYPES.PING;
}

function createCloseMessage() {
  return MESSAGE_TYPES.CLOSE;
}

export function setupWebSocketPing() {
  const socket = new WebSocket(`ws://${location.hostname}:${WS_PORT}`);

  socket.onopen = () => {
    setInterval(() => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(createPingMessage());
      }
    }, WS_PING_INTERVAL_MS);
  };

  socket.onmessage = (event) => {
    if (event.data === MESSAGE_TYPES.UPDATE) {
      window.dispatchEvent(new CustomEvent("data-updated", { detail: { source: "broadcast" } }));
    } else {
      console.log("[WebSocket] Message received:", event.data);
    }
  };

  socket.onerror = (error) => {
    console.error("[WebSocket] Error:", error);
  };

  socket.onclose = () => {
    console.log("[WebSocket] Connection closed");
  };

  window.addEventListener("beforeunload", () => {
    if (socket.readyState === WebSocket.OPEN) {
      socket.send(createCloseMessage());
    }
  });
}
