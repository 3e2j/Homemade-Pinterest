/** POST /refresh endpoint with SSE streaming. */

import { downloadTweets, processMedia } from "../utils/python-runner.js";
import { STATUS } from "../constants/status.js";

// Use a Promise-based lock to prevent concurrent refreshes
let refreshPromise = null;

/**
 * Send SSE message to client
 */
function sendSSEMessage(res, status, message) {
  res.write(`data: ${JSON.stringify({ status, message })}\n\n`);
}

/**
 * Handle refresh endpoint
 * Downloads tweets and processes media, streaming updates via SSE
 */
export async function refreshEndpoint(req, res) {
  // If refresh is already in progress, return 429 (Too Many Requests)
  if (refreshPromise) {
    return res.status(429).json({ error: "Refresh already in progress" });
  }

  // Setup SSE response
  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  res.setHeader("Connection", "keep-alive");

  // Create a new refresh operation
  refreshPromise = (async () => {
    try {
      // Download tweets
      sendSSEMessage(res, STATUS.DOWNLOADING, "Downloading tweets...");
      await downloadTweets();

      // Process media
      sendSSEMessage(res, STATUS.PROCESSING, "Processing media...");
      await processMedia();

      // Complete
      sendSSEMessage(res, STATUS.COMPLETE, "Refresh complete");
      res.end();
    } catch (err) {
      console.error("[Routes] Refresh error:", err.message);
      sendSSEMessage(res, STATUS.ERROR, err.message);
      res.end();
    } finally {
      // Always clear the lock when done
      refreshPromise = null;
    }
  })();
}

/**
 * Get refresh status
 */
export function statusEndpoint(req, res) {
  res.json({ isRefreshing: refreshPromise !== null });
}
