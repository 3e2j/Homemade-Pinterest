import { WS_PORT, WS_PING_INTERVAL_MS } from "../data/store.js";
import { createPingMessage, createCloseMessage } from "./protocol.js";

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
    console.log("[WebSocket] Message received:", event.data);
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
