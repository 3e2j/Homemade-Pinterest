/** Infinite scroll loader for pagination. */

import {
  SCROLL_ROOT_MARGIN,
  getTweets,
  getLoadedCount,
} from "../store/store.js";

export function setupLazyLoad(loadMoreCallback) {
  const sentinel = document.createElement("div");
  sentinel.style.height = "1px";
  document.body.appendChild(sentinel);

  const observer = new IntersectionObserver(
    (entries) => {
      const tweets = getTweets();
      const loadedCount = getLoadedCount();
      if (
        entries.some((e) => e.isIntersecting) &&
        loadedCount < tweets.length
      ) {
        loadMoreCallback();
      }
    },
    { rootMargin: SCROLL_ROOT_MARGIN },
  );

  observer.observe(sentinel);
}
