/** Refresh orchestrator and data fetcher. */

import { fetchTweetsData, setTweets, setLoadedCount } from "../store/store.js";
import { parseSSEStream } from "../connectivity/sse.js";
import { handleStatusMessage } from "../connectivity/status-handler.js";

/**
 * Call /refresh endpoint and handle SSE stream updates
 * Automatically fetches new data after completion
 */
export async function refreshAndFetchData(isInitial = false) {
  const res = await fetch("/refresh", { method: "POST" });
  await parseSSEStream(res, (data) => handleStatusMessage(data, { isInitial }));

  // Fetch the updated data
  const data = await fetchTweetsData();
  setTweets(data);
  return data;
}
