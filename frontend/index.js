/** Main application orchestrator and entry point. */

import {
  BATCH_SIZE,
  setTweets,
  setLoadedCount,
  addLoadedCount,
  getTweets,
  getLoadedCount,
  DATA_FILE,
  fetchTweetsData,
  prependNewTweets,
} from "./store/store.js";
import { STATUS, setStatus, onStatusChange } from "./store/status.js";
import { createCard, waitForMediaLoad } from "./components/tweet-card/card.js";
import {
  setupResizeListener,
  layoutMasonry,
} from "./components/gallery/layout.js";
import { setupLazyLoad } from "./interactions/scroll.js";
import { setupRefreshButton } from "./interactions/refresh.js";
import { refreshAndFetchData } from "./connectivity/refresh-utils.js";
import {
  initSettings,
  setupSettingsButton,
} from "./components/settings/modal.js";
import { strings } from "./i18n/en.js";

const t = strings;

let statusUnsubscribe = null;

export async function insertTweets(tweetsToInsert, { prepend = false } = {}) {
  if (!tweetsToInsert || !tweetsToInsert.length) return [];
  const grid = document.getElementById("grid");
  if (!grid) return [];

  const fragment = document.createDocumentFragment();
  const cards = [];

  if (prepend) {
    for (const t of tweetsToInsert) {
      const card = await createCard(t);
      card.style.visibility = "hidden";
      cards.push(card);
    }
    for (let i = cards.length - 1; i >= 0; i--) {
      grid.insertBefore(cards[i], grid.firstChild);
    }
  } else {
    for (const t of tweetsToInsert) {
      const card = await createCard(t);
      card.style.visibility = "hidden";
      fragment.appendChild(card);
      cards.push(card);
    }
    grid.appendChild(fragment);
  }

  const reveal = async () => {
    await waitForMediaLoad(cards);
    requestAnimationFrame(() => {
      layoutMasonry(grid);
      cards.forEach((card) => {
        card.style.visibility = "visible";
      });
    });
  };

  reveal();
  return cards;
}

async function loadMoreTweets() {
  const tweets = getTweets();
  let loadedCount = getLoadedCount();

  if (loadedCount >= tweets.length) {
    return;
  }

  setStatus(STATUS.LOADING_MORE, t.status.loadingMore);

  const end = Math.min(loadedCount + BATCH_SIZE, tweets.length);
  const slice = tweets.slice(loadedCount, end);
  await insertTweets(slice, { prepend: false });
  addLoadedCount(end - loadedCount);

  setStatus(STATUS.IDLE);
}

function createStatusIndicator() {
  const indicator = document.createElement("div");
  indicator.id = "status-indicator";
  indicator.style.cssText = `
    position: fixed;
    bottom: 20px;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(0, 0, 0, 0.8);
    color: white;
    padding: 12px 24px;
    border-radius: 24px;
    font-size: 14px;
    z-index: 999;
    display: none;
    opacity: 0;
    transition: opacity 0.3s ease;
  `;
  document.body.appendChild(indicator);
  return indicator;
}

function updateStatusDisplay(indicator, { status, message }) {
  if (status === STATUS.IDLE) {
    indicator.style.opacity = "0";
    setTimeout(() => {
      indicator.style.display = "none";
    }, 300);
  } else {
    indicator.style.display = "block";
    indicator.textContent = message;
    setTimeout(() => {
      indicator.style.opacity = "1";
    }, 10);
  }
}

window.addEventListener("DOMContentLoaded", async () => {
  const statusIndicator = createStatusIndicator();

  statusUnsubscribe = onStatusChange((statusUpdate) => {
    updateStatusDisplay(statusIndicator, statusUpdate);
  });

  // Initialize settings
  await initSettings();
  setupSettingsButton();

  // Handle server shutdown on page close
  window.addEventListener("beforeunload", async (e) => {
    if (statusUnsubscribe) statusUnsubscribe();

    try {
      const configRes = await fetch("/config");
      const config = await configRes.json();
      if (config.server?.closeOnPageClose) {
        await fetch("/shutdown", { method: "POST" });
      }
    } catch (err) {
      console.warn("Could not check shutdown setting:", err);
    }
  });

  setStatus(STATUS.LOADING_INITIAL, t.status.loadingInitial);

  try {
    const data = await fetchTweetsData();
    setTweets(data);
  } catch (e) {
    console.warn("data.json missing/unreadable, attempting refresh...", e);
  }

  let tweets = getTweets();
  if (!tweets.length) {
    setStatus(STATUS.LOADING_INITIAL, t.status.downloadingTweets);
    try {
      await refreshAndFetchData(true);
      tweets = getTweets();
    } catch (e) {
      console.error("Failed to refresh tweets:", e);
      setStatus(STATUS.ERROR, t.status.error);
      const grid = document.getElementById("grid");
      if (grid) {
        grid.innerHTML = `<p style='padding: 20px; text-align: center;'>${t.status.errorRetry}</p>`;
      }
      return;
    }
  }

  setupResizeListener();
  setupLazyLoad(loadMoreTweets);
  setupRefreshButton(insertTweets);

  if (tweets.length > 0) {
    const initialSlice = tweets.slice(0, BATCH_SIZE);
    await insertTweets(initialSlice, { prepend: false });
    setLoadedCount(initialSlice.length);
  }

  setStatus(STATUS.IDLE);
});
