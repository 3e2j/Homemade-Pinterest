/** POST /refresh endpoint with SSE streaming. */

import { downloadTweets, processMedia } from "../utils/python-runner.js";
import { STATUS } from "../constants/status.js";

// Track if refresh is in progress
let isRefreshing = false;

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
  if (isRefreshing) {
    return res.status(429).json({ error: "Refresh already in progress" });
  }

  isRefreshing = true;

  // Setup SSE response
  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  res.setHeader("Connection", "keep-alive");

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
    isRefreshing = false;
  }
}

/**
 * Get refresh status
 */
export function statusEndpoint(req, res) {
  res.json({ isRefreshing });
}
