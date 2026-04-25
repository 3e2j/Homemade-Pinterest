import {
  BATCH_SIZE,
  setTweets,
  setLoadedCount,
  addLoadedCount,
  getTweets,
  getLoadedCount,
} from "./data/store.js";
import { fetchTweetsData, prependNewTweets } from "./data/loader.js";
import { createCard, waitForMediaLoad } from "./components/card.js";
import { layoutMasonry } from "./layout/masonry.js";
import { setupResizeListener } from "./layout/responsive.js";
import { setupLazyLoad } from "./ui/lazy-load.js";
import { setupRefreshButton } from "./ui/events.js";
import { setupWebSocketPing } from "./ws/client.js";

export async function insertTweets(tweetsToInsert, { prepend = false } = {}) {
  if (!tweetsToInsert || !tweetsToInsert.length) return [];
  const grid = document.getElementById("grid");
  if (!grid) return [];

  const fragment = document.createDocumentFragment();
  const cards = [];

  // For prepend we build in natural order but will insert reversed to keep visual order
  if (prepend) {
    for (const t of tweetsToInsert) {
      const card = await createCard(t);
      card.style.visibility = "hidden";
      cards.push(card);
    }
    // Insert in reverse so first tweet becomes first DOM child
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
  const end = Math.min(loadedCount + BATCH_SIZE, tweets.length);
  const slice = tweets.slice(loadedCount, end);
  await insertTweets(slice, { prepend: false });
  addLoadedCount(end - loadedCount);
}

window.addEventListener("DOMContentLoaded", async () => {
  // Start WebSocket connection immediately so server knows client is active
  setupWebSocketPing();

  try {
    const data = await fetchTweetsData();
    setTweets(data);
  } catch (e) {
    console.warn("data.json missing/unreadable, attempting refresh...", e);
  }

  let tweets = getTweets();
  if (!tweets.length) {
    try {
      await fetch("/refresh", { method: "POST" });
      const data = await fetchTweetsData();
      setTweets(data);
      tweets = getTweets();
    } catch (e) {
      console.error("Failed to refresh tweets:", e);
      const grid = document.getElementById("grid");
      if (grid)
        grid.innerHTML = "<p>Error loading tweets. Please try again later.</p>";
      return;
    }
  }

  // Setup UI components
  setupResizeListener();
  setupLazyLoad(loadMoreTweets);
  setupRefreshButton(insertTweets);
});
