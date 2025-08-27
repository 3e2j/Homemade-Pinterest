// ==== Constants ====
const BATCH_SIZE = 100;
const MEDIA_DIR = "images/media";
const AVATAR_DIR = "images/avatars";
const DATA_FILE = "data.json";  // keep name
const STYLE_FILE = "style.css";
const WS_PORT = 8765;
const MEDIA_MARGIN = 10;
const HALF_MARGIN = MEDIA_MARGIN / 2;

// ==== State ====
let tweets = [];
let loadedCount = 0;

// ==== Utility Functions ====
function getMediaSrc(media) {
  if (typeof media === "string" && media.includes("://")) {
    return media;
  }
  return `${MEDIA_DIR}/${media}`;
}

function getAvatarSrc(avatar) {
  if (typeof avatar === "string" && avatar.startsWith("http")) {
    return avatar;
  }
  return `${AVATAR_DIR}/${avatar}`;
}

// ==== Masonry Layout ====
function layoutMasonry(container) {
  const cardWidth = 220;
  const gutter = 8;
  const columns = Math.floor(container.clientWidth / (cardWidth + gutter));
  if (columns < 1) return;

  const heights = new Array(columns).fill(0);
  const cards = Array.from(container.children);

  for (const card of cards) {
    const span = card.classList.contains("multiple-media") ? Math.min(2, columns) : 1;
    const width = cardWidth * span + gutter * (span - 1);

    let minY = Infinity;
    let minX = 0;
    for (let i = 0; i <= columns - span; i++) {
      const sliceHeight = Math.max(...heights.slice(i, i + span));
      if (sliceHeight < minY) {
        minY = sliceHeight;
        minX = i;
      }
    }

    const x = minX * (cardWidth + gutter);
    card.style.position = "absolute";
    card.style.width = `${width}px`;
    card.style.transform = `translate(${x}px, ${minY}px)`;

    const newHeight = minY + card.offsetHeight + gutter;
    for (let i = 0; i < span; i++) {
      heights[minX + i] = newHeight;
    }
  }

  container.style.height = `${Math.max(...heights)}px`;
}

// ==== Card Creation ====
async function createCard(tweet) {
  const card = document.createElement("div");
  const hasMultipleMedia = tweet.media.length > 1;
  const isSensitive = tweet.possibly_sensitive;
  card.className = "card" + (hasMultipleMedia ? " multiple-media" : "");
  card.dataset.tweetId = tweet.id || tweet.tweet_id;

  // Info section
  const link = document.createElement("a");
  const urlMatch = tweet.content.match(/https?:\/\/\S+$/);
  link.href = urlMatch ? urlMatch[0] : "#";
  link.className = "info-link";
  link.target = "_blank";

  const info = document.createElement("div");
  info.className = "info";

  if (tweet.avatar) {
    const avatar = document.createElement("img");
    avatar.className = "avatar";
    avatar.src = getAvatarSrc(tweet.avatar);
    info.appendChild(avatar);
  }

  const name = document.createElement("span");
  name.className = "username";
  name.textContent = tweet.username;
  info.appendChild(name);

  const handle = document.createElement("span");
  handle.className = "handle";
  handle.textContent = "@" + tweet.handle;
  info.appendChild(handle);

  const content = document.createElement("div");
  content.className = "content";
  content.textContent = tweet.content.replace(/https?:\/\/\S+$/, '').trim();
  if (content.textContent) info.appendChild(content);

  link.appendChild(info);
  card.appendChild(link);

  // Sensitive content handling
  let hideBtn = null;
  if (isSensitive) {
    hideBtn = document.createElement("button");
    hideBtn.className = "hide-button";
    hideBtn.textContent = "Hide";
    hideBtn.style.display = "none";
    hideBtn.addEventListener("click", e => {
      e.preventDefault();
      e.stopPropagation();
      card.querySelectorAll(".media-wrap img").forEach(img => img.classList.add("blurred"));
      card.querySelectorAll(".blurred-icon").forEach(icon => icon.style.display = "block");
      hideBtn.style.display = "none";
    });
    card.appendChild(hideBtn);
  }

  // Media wrap helper
  const addMediaWrap = (src) => {
    const wrap = document.createElement("a");
    wrap.href = getMediaSrc(src);
    wrap.className = "media-wrap crop-to-ratio";
    wrap.target = "_blank";

    const img = document.createElement("img");
    img.src = getMediaSrc(src);
    if (isSensitive) img.classList.add("blurred");
    wrap.appendChild(img);

    if (tweet.is_video) {
      const icon = document.createElement("div");
      icon.className = "video-indicator";
      icon.innerHTML = `
        <svg width="24" height="24" viewBox="0 0 16 16" fill="white">
          <path d="M10 3H0V13H10V3Z"/>
          <path d="M15 3L12 6V10L15 13H16V3H15Z"/>
        </svg>`;
      wrap.appendChild(icon);
    }

    if (isSensitive) {
      const eyeIcon = document.createElement("div");
      eyeIcon.className = "blurred-icon";
      eyeIcon.innerHTML = `
        <svg viewBox="0 0 1000 1000" xmlns="http://www.w3.org/2000/svg">
          <path d="M499 270q57 0 104.5 28t75.5 76 28 104q0 39-15 76l122 122q97-81 142-198-36-91-104-162T694 206q-93-40-195-40-86 0-166 29l90 90q38-15 76-15zM83 157l95 94 19 20q-52 40-91.5 93T42 478q36 91 104.5 162T304 750q93 40 195 40 95 0 183-35l139 139 53-53-738-737zm230 230l65 64q-4 15-4 27 0 34 17 62.5t45.5 45.5 62.5 17q14 0 27-3l65 64q-45 22-92 22-56 0-104-28t-76-76-28-104q0-47 22-91zm180-33l131 131v-6q0-34-16.5-63t-45-45.5T500 354h-7z"/>
        </svg>`;
      wrap.appendChild(eyeIcon);

      let wasBlurredAtMouseDown = false;
      wrap.addEventListener("mousedown", () => {
        wasBlurredAtMouseDown = img.classList.contains("blurred");
      });
      wrap.addEventListener("click", (e) => {
        if (wasBlurredAtMouseDown) {
          e.preventDefault();
          card.querySelectorAll(".media-wrap img").forEach(i => i.classList.remove("blurred"));
          card.querySelectorAll(".blurred-icon").forEach(icon => icon.style.display = "none");
          if (hideBtn) hideBtn.style.display = "block";
        }
      });
    }
    if (isSensitive) {
      card.addEventListener("mouseenter", () => {
        const anyUnblurred = [...card.querySelectorAll(".media-wrap img")].some(i => !i.classList.contains("blurred"));
        if (anyUnblurred && hideBtn) hideBtn.style.display = "block";
      });

      card.addEventListener("mouseleave", () => {
        if (hideBtn) hideBtn.style.display = "none";
      });
    }
    return wrap;
  };

  // Preload media and get aspect ratios
  let imageRatios = [];
  let allSameAspectRatio = true;

  if (tweet.media.length > 1) {
    imageRatios = await Promise.all(tweet.media.map(src => {
      return new Promise(resolve => {
        const img = new Image();
        img.onload = () => resolve(img.naturalWidth / img.naturalHeight);
        img.onerror = () => resolve(null);
        img.src = getMediaSrc(src);
      });
    }));

    const validRatios = imageRatios.filter(r => r !== null);
    const firstRatio = validRatios[0];
    allSameAspectRatio = validRatios.every(r => Math.abs(r - firstRatio) < 0.01);
  }

  // Media rendering
  if (tweet.media.length === 1) {
    card.appendChild(addMediaWrap(tweet.media[0]));
  } else if ([2, 3, 4].includes(tweet.media.length)) {
    const grid = document.createElement("div");
    grid.className = "media-grid";

    if (tweet.media.length === 3) {
      const firstIsWide = imageRatios[0] && imageRatios[0] > 1.2;

      if (firstIsWide) {
        grid.classList.add("three-wide-top");

        const topWrap = addMediaWrap(tweet.media[0]);
        topWrap.classList.add("top-image");

        const bottomRow = document.createElement("div");
        bottomRow.className = "bottom-row";

        const secondWrap = addMediaWrap(tweet.media[1]);
        const thirdWrap = addMediaWrap(tweet.media[2]);

        bottomRow.appendChild(secondWrap);
        bottomRow.appendChild(thirdWrap);

        grid.appendChild(topWrap);
        grid.appendChild(bottomRow);
      } else {
        grid.classList.add("three-grid");
        tweet.media.forEach((media, index) => {
          const wrap = addMediaWrap(media);
          if (!allSameAspectRatio) {
            wrap.classList.add("crop-to-ratio");
          }
          grid.appendChild(wrap);
        });
      }
    } else {
      // 2 or 4 media
      grid.style.gridTemplateColumns = `repeat(2, 1fr)`;
      tweet.media.forEach((media, index) => {
        const wrap = addMediaWrap(media);
        if (!allSameAspectRatio) {
          wrap.classList.add("crop-to-ratio");
        }
        grid.appendChild(wrap);
      });
    }

    card.appendChild(grid);
  }
  return card;
}

// ==== Tweet Loading and Lazy Load ====
// Common insertion & reveal logic used by both append and prepend operations
async function insertTweets(tweetsToInsert, { prepend = false } = {}) {
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

  const images = cards.flatMap(card => Array.from(card.querySelectorAll("img")));
  const reveal = () => {
    requestAnimationFrame(() => {
      layoutMasonry(grid);
      cards.forEach(card => { card.style.visibility = "visible"; });
    });
  };
  if (!images.length) {
    reveal();
  } else {
    let done = 0;
    const check = () => { if (++done === images.length) reveal(); };
    images.forEach(img => (img.complete ? check() : (img.onload = img.onerror = check)));
  }
  return cards;
}

async function loadMoreTweets() {
  const end = Math.min(loadedCount + BATCH_SIZE, tweets.length);
  const slice = tweets.slice(loadedCount, end);
  await insertTweets(slice, { prepend: false });
  loadedCount = end;
}

function setupLazyLoad() {
  const sentinel = document.createElement("div");
  sentinel.style.height = "1px";
  document.body.appendChild(sentinel);

  const observer = new IntersectionObserver(entries => {
    if (entries.some(e => e.isIntersecting) && loadedCount < tweets.length) {
      loadMoreTweets();
    }
  }, { rootMargin: "1000px" });

  observer.observe(sentinel);
}

// ==== WebSocket Ping ====
function setupWebSocketPing() {
  const socket = new WebSocket(`ws://${location.hostname}:${WS_PORT}`);

  socket.onopen = () => {
    setInterval(() => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send("ping");
      }
    }, 5000);
  };

  socket.onmessage = (event) => {
    console.log("[WebSocket] Message received:", event.data);
  };

  socket.onerror = (error) => {
    console.error("[WebSocket] Error:", error);
  };

  socket.onclose = () => {
    console.log("[WebSocket] Connection closed");
  };

  window.addEventListener("beforeunload", () => {
    if (socket.readyState === WebSocket.OPEN) {
      socket.send("close");
    }
  });
}

// ==== Fetch Tweets Data ====
async function fetchTweetsData() {
  const url = `${DATA_FILE}?_=${Date.now()}`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load data.json");
  return res.json();
}

// ==== Prepend Newly Fetched Tweets ====
async function prependNewTweets(newTweets) {
  if (!newTweets || !newTweets.length) return;
  await insertTweets(newTweets, { prepend: true });
  // Adjust loadedCount so infinite scroll continues after the currently rendered set
  loadedCount += newTweets.length;
}

// ==== Event Listeners ====
window.addEventListener("resize", () => layoutMasonry(document.getElementById("grid")));

window.addEventListener("DOMContentLoaded", async () => {
  try {
    tweets = await fetchTweetsData();
  } catch (e) {
    console.warn("data.json missing/unreadable, attempting refresh...", e);
  }

  if (!tweets.length) {
    try {
      await fetch("/refresh", { method: "POST" });
      tweets = await fetchTweetsData(); // re-fetch fresh
    } catch (e) {
      console.error("Failed to refresh tweets:", e);
      const grid = document.getElementById("grid");
      if (grid) grid.innerHTML = "<p>Error loading tweets. Please try again later.</p>";
      return;
    }
  }

  setupLazyLoad();
  setupWebSocketPing();
});

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
        const existingIds = new Set(tweets.map(t => t.id || t.tweet_id));
        const freshIds = new Set(fresh.map(t => t.id || t.tweet_id));
        const newOnes = fresh.filter(t => !existingIds.has(t.id || t.tweet_id));
        const removedIds = [...existingIds].filter(id => !freshIds.has(id));

        // Remove deleted tweets' cards
        if (removedIds.length) {
          const grid = document.getElementById("grid");
          removedIds.forEach(id => {
            const el = grid.querySelector(`.card[data-tweet-id="${id}"]`);
            if (el) el.remove();
          });
        }

        tweets = fresh; // replace full list

        if (newOnes.length) {
          await prependNewTweets(newOnes);
        } else if (removedIds.length) {
          // Re-layout after removals only
            const grid = document.getElementById("grid");
            layoutMasonry(grid);
        }

        // Recompute loadedCount based on number of cards currently rendered
        const grid = document.getElementById("grid");
        loadedCount = grid ? grid.children.length : tweets.length;

        if (newOnes.length || removedIds.length) {
          btn.textContent = "Updated";
          setTimeout(() => { btn.textContent = "🔄 Refresh"; btn.disabled = false; }, 1500);
        } else {
          btn.textContent = "No changes";
          setTimeout(() => { btn.textContent = "🔄 Refresh"; btn.disabled = false; }, 1500);
        }
      } catch (e) {
        console.error("Failed to fetch updated data.json:", e);
        location.reload(); // fallback
      }
    } else {
      btn.textContent = "No changes";
      setTimeout(() => { btn.textContent = "🔄 Refresh"; btn.disabled = false; }, 1500);
    }
  } catch (e) {
    btn.textContent = "Error!";
    setTimeout(() => { btn.textContent = "🔄 Refresh"; btn.disabled = false; }, 2000);
  }
});
