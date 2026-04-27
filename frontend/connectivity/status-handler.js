/** SSE status message processor. */

import { STATUS, setStatus } from "../store/status.js";

// Map server status messages to UI updates
const STATUS_HANDLERS = {
  downloading: (context) => {
    setStatus(
      context.isInitial ? STATUS.LOADING_INITIAL : STATUS.REFRESHING,
      "Downloading tweets...",
    );
  },
  processing: (context) => {
    setStatus(
      context.isInitial ? STATUS.LOADING_INITIAL : STATUS.REFRESHING,
      "Processing media...",
    );
  },
  complete: (context) => {
    setStatus(
      context.isInitial ? STATUS.LOADING_INITIAL : STATUS.REFRESHING,
      "Updating display...",
    );
  },
  error: (context, message) => {
    setStatus(STATUS.ERROR, message || "An error occurred");
  },
};

/**
 * Handle SSE status messages with context
 */
export function handleStatusMessage(data, context = {}) {
  const handler = STATUS_HANDLERS[data.status];
  if (handler) {
    handler(context, data.message);
  }
}
