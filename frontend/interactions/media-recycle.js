/** Frees decoded image/video memory for cards scrolled far out of view,
 * and restores it if the user scrolls back. Without this, a long enough
 * scroll session keeps every image and video ever loaded fully decoded in
 * memory forever, which eventually exhausts the tab.
 */

const UNLOAD_ROOT_MARGIN = "3000px";

let recycleObserver = null;

function freezeHeight(card) {
  if (card.dataset.heightFrozen) return;
  const height = card.offsetHeight;
  card.style.boxSizing = "border-box";
  card.style.height = `${height}px`;
  card.dataset.heightFrozen = "true";
}

function unloadCardMedia(card) {
  const mediaEls = card.querySelectorAll(".media-content");
  if (!mediaEls.length) return;

  // Freeze the card's box height before stripping media so the masonry
  // layout (computed once, from absolute transforms) never shifts under it.
  freezeHeight(card);

  mediaEls.forEach((el) => {
    const currentSrc = el.getAttribute("src");
    if (!currentSrc) return;
    el.dataset.recycledSrc = currentSrc;
    if (el.tagName === "VIDEO") {
      el.pause();
      el.removeAttribute("src");
      el.load();
    } else {
      el.removeAttribute("src");
    }
  });
}

function reloadCardMedia(card) {
  const mediaEls = card.querySelectorAll(".media-content");
  mediaEls.forEach((el) => {
    const savedSrc = el.dataset.recycledSrc;
    if (!savedSrc || el.getAttribute("src")) return;
    el.src = savedSrc;
    delete el.dataset.recycledSrc;
  });
}

function getRecycleObserver() {
  if (!recycleObserver) {
    recycleObserver = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            reloadCardMedia(entry.target);
          } else {
            unloadCardMedia(entry.target);
          }
        }
      },
      { rootMargin: UNLOAD_ROOT_MARGIN },
    );
  }
  return recycleObserver;
}

export function observeCardForRecycling(card) {
  getRecycleObserver().observe(card);
}
