import { getTweets, setTweets, getLoadedCount, setLoadedCount, fetchTweetsData, prependNewTweets } from "../store/store.js";
import { layoutMasonry } from "../components/gallery/layout.js";

export function setupRefreshButton(insertTweetsFunc) {
  document.getElementById("refresh-btn").addEventListener("click", async () => {
    const btn = document.getElementById("refresh-btn");
    btn.disabled = true;
    btn.textContent = "Refreshing...";
    try {
      const res = await fetch("/refresh", { method: "POST" });
      const data = await res.json();
      if (data.updated) {
        try {
          const fresh = await fetchTweetsData();
          const tweets = getTweets();
          const existingIds = new Set(tweets.map((t) => t.id || t.tweet_id));
          const freshIds = new Set(fresh.map((t) => t.id || t.tweet_id));
          const newOnes = fresh.filter(
            (t) => !existingIds.has(t.id || t.tweet_id),
          );
          const removedIds = [...existingIds].filter((id) => !freshIds.has(id));

          if (removedIds.length) {
            const grid = document.getElementById("grid");
            removedIds.forEach((id) => {
              const el = grid.querySelector(`.card[data-tweet-id="${id}"]`);
              if (el) el.remove();
            });
          }

          setTweets(fresh);

          if (newOnes.length) {
            await prependNewTweets(newOnes, insertTweetsFunc);
          } else if (removedIds.length) {
            const grid = document.getElementById("grid");
            layoutMasonry(grid);
          }

          const grid = document.getElementById("grid");
          setLoadedCount(grid ? grid.children.length : fresh.length);

          if (newOnes.length || removedIds.length) {
            btn.textContent = "Updated";
            setTimeout(() => {
              btn.textContent = "🔄 Refresh";
              btn.disabled = false;
            }, 1500);
          } else {
            btn.textContent = "No changes";
            setTimeout(() => {
              btn.textContent = "🔄 Refresh";
              btn.disabled = false;
            }, 1500);
          }
        } catch (e) {
          console.error("Failed to fetch updated data.json:", e);
          location.reload();
        }
      } else {
        btn.textContent = "No changes";
        setTimeout(() => {
          btn.textContent = "🔄 Refresh";
          btn.disabled = false;
        }, 1500);
      }
    } catch (e) {
      btn.textContent = "Error!";
      setTimeout(() => {
        btn.textContent = "🔄 Refresh";
        btn.disabled = false;
      }, 2000);
    }
  });
}
