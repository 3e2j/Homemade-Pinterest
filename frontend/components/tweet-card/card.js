import {
  SAME_ASPECT_TOLERANCE,
  WIDE_IMAGE_THRESHOLD,
} from "../../store/store.js";
import { createAvatarElement } from "./avatar.js";
import { getMediaSrc, isVideoMedia, createMediaElement } from "./media.js";

function createSimpleMediaWrap(src) {
  const wrap = document.createElement("a");
  wrap.href = getMediaSrc(src);
  wrap.className = "media-wrap crop-to-ratio";
  wrap.target = "_blank";
  wrap.appendChild(createMediaElement(src));
  return wrap;
}

function createSensitiveMediaWrap(src, card, hideBtn) {
  const wrap = document.createElement("a");
  wrap.href = getMediaSrc(src);
  wrap.className = "media-wrap crop-to-ratio";
  wrap.target = "_blank";

  const mediaEl = createMediaElement(src);
  mediaEl.classList.add("blurred");
  wrap.appendChild(mediaEl);

  // Eye icon overlay
  const eyeIcon = document.createElement("div");
  eyeIcon.className = "blurred-icon";
  eyeIcon.innerHTML = `
    <svg viewBox="0 0 1000 1000" xmlns="http://www.w3.org/2000/svg">
      <path d="M499 270q57 0 104.5 28t75.5 76 28 104q0 39-15 76l122 122q97-81 142-198-36-91-104-162T694 206q-93-40-195-40-86 0-166 29l90 90q38-15 76-15zM83 157l95 94 19 20q-52 40-91.5 93T42 478q36 91 104.5 162T304 750q93 40 195 40 95 0 183-35l139 139 53-53-738-737zm230 230l65 64q-4 15-4 27 0 34 17 62.5t45.5 45.5 62.5 17q14 0 27-3l65 64q-45 22-92 22-56 0-104-28t-76-76-28-104q0-47 22-91zm180-33l131 131v-6q0-34-16.5-63t-45-45.5T500 354h-7z"/>
    </svg>`;
  wrap.appendChild(eyeIcon);

  // Track state for unblur on click
  let wasBlurredAtMouseDown = false;
  wrap.addEventListener("mousedown", () => {
    wasBlurredAtMouseDown = mediaEl.classList.contains("blurred");
  });
  wrap.addEventListener("click", (e) => {
    if (wasBlurredAtMouseDown) {
      e.preventDefault();
      card
        .querySelectorAll(".media-wrap .media-content")
        .forEach((i) => i.classList.remove("blurred"));
      card
        .querySelectorAll(".blurred-icon")
        .forEach((icon) => (icon.style.display = "none"));
      if (hideBtn) hideBtn.style.display = "block";
    }
  });

  // Show hide button on hover if media is unblurred
  card.addEventListener("mouseenter", () => {
    const anyUnblurred = [
      ...card.querySelectorAll(".media-wrap .media-content"),
    ].some((i) => !i.classList.contains("blurred"));
    if (anyUnblurred && hideBtn) hideBtn.style.display = "block";
  });
  card.addEventListener("mouseleave", () => {
    if (hideBtn) hideBtn.style.display = "none";
  });

  return wrap;
}

function buildMediaGrid(tweet, imageRatios, allSameAspectRatio, addMediaWrap) {
  const grid = document.createElement("div");
  grid.className = "media-grid";

  if (tweet.media.length === 3) {
    const firstIsWide = imageRatios[0] && imageRatios[0] > WIDE_IMAGE_THRESHOLD;

    if (firstIsWide) {
      grid.classList.add("three-wide-top");
      const topWrap = addMediaWrap(tweet.media[0]);
      topWrap.classList.add("top-image");
      grid.appendChild(topWrap);

      const bottomRow = document.createElement("div");
      bottomRow.className = "bottom-row";
      bottomRow.appendChild(addMediaWrap(tweet.media[1]));
      bottomRow.appendChild(addMediaWrap(tweet.media[2]));
      grid.appendChild(bottomRow);
    } else {
      grid.classList.add("three-grid");
      tweet.media.forEach((media) => {
        const wrap = addMediaWrap(media);
        if (!allSameAspectRatio) {
          wrap.classList.add("crop-to-ratio");
        }
        grid.appendChild(wrap);
      });
    }
  } else {
    // 2 or 4 media
    grid.style.gridTemplateColumns = "repeat(2, 1fr)";
    tweet.media.forEach((media) => {
      const wrap = addMediaWrap(media);
      if (!allSameAspectRatio) {
        wrap.classList.add("crop-to-ratio");
      }
      grid.appendChild(wrap);
    });
  }

  return grid;
}

export async function createCard(tweet) {
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

  // Header row: avatar + stacked username/handle
  const header = document.createElement("div");
  header.className = "info-header";

  const avatarEl = createAvatarElement(tweet);
  if (avatarEl) {
    header.appendChild(avatarEl);
  }

  // Stack username and handle vertically
  const textStack = document.createElement("div");
  textStack.className = "text-stack";

  const name = document.createElement("span");
  name.className = "username";
  name.textContent = tweet.username;
  textStack.appendChild(name);

  const handle = document.createElement("span");
  handle.className = "handle";
  handle.textContent = "@" + tweet.handle;
  textStack.appendChild(handle);

  header.appendChild(textStack);
  info.appendChild(header);

  const content = document.createElement("div");
  content.className = "content";
  content.textContent = tweet.content.replace(/https?:\/\/\S+$/, "").trim();
  if (content.textContent) info.appendChild(content);

  link.appendChild(info);
  card.appendChild(link);

  // Setup sensitive content controls if needed
  let hideBtn = null;
  if (isSensitive) {
    hideBtn = document.createElement("button");
    hideBtn.className = "hide-button";
    hideBtn.textContent = "Hide";
    hideBtn.style.display = "none";
    hideBtn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      card
        .querySelectorAll(".media-wrap .media-content")
        .forEach((el) => el.classList.add("blurred"));
      card
        .querySelectorAll(".blurred-icon")
        .forEach((icon) => (icon.style.display = "block"));
      hideBtn.style.display = "none";
    });
    card.appendChild(hideBtn);
  }

  // Media wrap factory
  const addMediaWrap = (src) => {
    if (!isSensitive) {
      return createSimpleMediaWrap(src);
    }
    return createSensitiveMediaWrap(src, card, hideBtn);
  };

  // Add media to card - handle single image, 2-4 image grid, or nothing
  if (tweet.media.length === 1) {
    card.appendChild(addMediaWrap(tweet.media[0]));
  } else if ([2, 3, 4].includes(tweet.media.length)) {
    let imageRatios = [];
    let allSameAspectRatio = true;

    // Load all image dimensions
    imageRatios = await Promise.all(
      tweet.media.map((src) => {
        return new Promise((resolve) => {
          if (isVideoMedia(src)) {
            const video = document.createElement("video");
            video.preload = "metadata";
            video.onloadedmetadata = () =>
              resolve(video.videoWidth / video.videoHeight);
            video.onerror = () => resolve(null);
            video.src = getMediaSrc(src);
            return;
          }
          const img = new Image();
          img.onload = () => resolve(img.naturalWidth / img.naturalHeight);
          img.onerror = () => resolve(null);
          img.src = getMediaSrc(src);
        });
      }),
    );

    // Check if all images have same aspect ratio
    const validRatios = imageRatios.filter((r) => r !== null);
    const firstRatio = validRatios[0];
    allSameAspectRatio = validRatios.every(
      (r) => Math.abs(r - firstRatio) < SAME_ASPECT_TOLERANCE,
    );

    card.appendChild(
      buildMediaGrid(tweet, imageRatios, allSameAspectRatio, addMediaWrap),
    );
  }

  return card;
}

export async function waitForMediaLoad(cards) {
  const mediaElements = cards.flatMap((card) =>
    Array.from(card.querySelectorAll(".media-content")),
  );

  if (!mediaElements.length) {
    return true;
  }

  return new Promise((resolve) => {
    let done = 0;
    const check = () => {
      if (++done === mediaElements.length) resolve(true);
    };
    mediaElements.forEach((el) => {
      if (el.tagName === "VIDEO") {
        if (el.readyState >= 2) check();
        else el.onloadeddata = el.onerror = check;
      } else if (el.complete) {
        check();
      } else {
        el.onload = el.onerror = check;
      }
    });
  });
}
