export const MESSAGE_TYPES = {
  PING: "ping",
  PONG: "pong",
  CLOSE: "close",
};

export function createPingMessage() {
  return MESSAGE_TYPES.PING;
}

export function createCloseMessage() {
  return MESSAGE_TYPES.CLOSE;
}
