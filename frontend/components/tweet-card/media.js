/** Media (image/video) rendering component. */

import { MEDIA_IMAGES_DIR, VIDEO_EXTENSIONS } from "../../store/store.js";

export function getMediaSrc(media) {
  const path = typeof media === "object" ? media.path : media;
  if (typeof path === "string" && path.includes("://")) {
    return path;
  }
  if (typeof path === "string" && path.includes("/")) {
    return path;
  }
  return `${MEDIA_IMAGES_DIR}/${path}`;
}

export function isVideoMedia(media) {
  const path = typeof media === "object" ? media.path : media;
  if (typeof path !== "string") return false;
  const lower = path.toLowerCase();
  return VIDEO_EXTENSIONS.some((ext) => lower.includes(ext));
}

// Shared across all video cards: pauses decoding/playback once a video
// scrolls out of view so an unbounded feed doesn't keep every video ever
// loaded running in the background.
let videoVisibilityObserver = null;

function getVideoVisibilityObserver() {
  if (!videoVisibilityObserver) {
    videoVisibilityObserver = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const video = entry.target;
          if (entry.isIntersecting) {
            video.play().catch(() => {});
          } else {
            video.pause();
          }
        }
      },
      { rootMargin: "200px" },
    );
  }
  return videoVisibilityObserver;
}

export function createMediaElement(src) {
  const mediaSrc = getMediaSrc(src);
  const mediaEl = isVideoMedia(src)
    ? document.createElement("video")
    : document.createElement("img");
  mediaEl.className = "media-content";
  mediaEl.src = mediaSrc;
  if (mediaEl.tagName === "VIDEO") {
    mediaEl.loop = true;
    mediaEl.muted = true;
    mediaEl.playsInline = true;
    getVideoVisibilityObserver().observe(mediaEl);
  }
  return mediaEl;
}
