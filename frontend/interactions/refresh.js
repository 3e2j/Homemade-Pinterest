/** Pull-to-refresh button logic and data synchronization. */

import {
  getTweets,
  setTweets,
  getLoadedCount,
  setLoadedCount,
  fetchTweetsData,
  prependNewTweets,
} from "../store/store.js";
import { STATUS, setStatus } from "../store/status.js";
import { layoutMasonry } from "../components/gallery/layout.js";
import { refreshAndFetchData } from "../connectivity/refresh-utils.js";
import { parseSSEStream } from "../connectivity/sse.js";
import { handleStatusMessage } from "../connectivity/status-handler.js";
import { strings } from "../i18n/en.js";

const t = strings;

function getRefreshButton() {
  return document.getElementById("refresh-btn");
}

function getGrid() {
  return document.getElementById("grid");
}

function setButtonState(text, disabled = false, temporary = false) {
  const btn = getRefreshButton();
  btn.textContent = text;
  btn.disabled = disabled;

  if (temporary) {
    setTimeout(() => {
      btn.textContent = t.buttons.refresh;
      btn.disabled = false;
    }, 1500);
  }
}

function removeDeletedCards(removedIds) {
  if (!removedIds.length) return;

  const grid = getGrid();
  if (!grid) return;

  removedIds.forEach((id) => {
    const el = grid.querySelector(`.card[data-tweet-id="${id}"]`);
    if (el) el.remove();
  });
}

function getNewAndRemovedTweets(fresh) {
  const tweets = getTweets();
  const existingIds = new Set(tweets.map((t) => t.id || t.tweet_id));
  const freshIds = new Set(fresh.map((t) => t.id || t.tweet_id));

  const newOnes = fresh.filter((t) => !existingIds.has(t.id || t.tweet_id));
  const removedIds = [...existingIds].filter((id) => !freshIds.has(id));

  return { newOnes, removedIds };
}

async function performRefresh(insertTweetsFunc, isBroadcast = false) {
  try {
    const fresh = await fetchTweetsData();
    const { newOnes, removedIds } = getNewAndRemovedTweets(fresh);

    removeDeletedCards(removedIds);
    setTweets(fresh);

    if (newOnes.length) {
      await prependNewTweets(newOnes, insertTweetsFunc);
    } else if (removedIds.length) {
      layoutMasonry(getGrid());
    }

    const grid = getGrid();
    setLoadedCount(grid ? grid.children.length : fresh.length);

    if (!isBroadcast) {
      const message =
        newOnes.length || removedIds.length
          ? t.refresh.updated
          : t.refresh.noChanges;
      setButtonState(message, false, true);
    }
  } catch (e) {
    console.error("Failed to fetch updated data.json:", e);
    if (!isBroadcast) {
      location.reload();
    }
  }
}

export function setupRefreshButton(insertTweetsFunc) {
  const btn = getRefreshButton();

  btn.addEventListener("click", async () => {
    setButtonState(t.refresh.refreshing, true);
    setStatus(STATUS.REFRESHING, t.status.downloadingNewTweets);

    try {
      const res = await fetch("/refresh", { method: "POST" });
      await parseSSEStream(res, (data) =>
        handleStatusMessage(data, { isInitial: false }),
      );

      await performRefresh(insertTweetsFunc, false);
      setStatus(STATUS.IDLE);
    } catch (e) {
      console.error("Refresh error:", e);
      setButtonState(t.refresh.error, false, true);
      setStatus(STATUS.ERROR, t.status.error);
      setTimeout(() => {
        setStatus(STATUS.IDLE);
      }, 2000);
    }
  });
}
