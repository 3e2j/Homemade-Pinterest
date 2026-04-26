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

export function createMediaElement(src) {
  const mediaSrc = getMediaSrc(src);
  const mediaEl = isVideoMedia(src)
    ? document.createElement("video")
    : document.createElement("img");
  mediaEl.className = "media-content";
  mediaEl.src = mediaSrc;
  if (mediaEl.tagName === "VIDEO") {
    mediaEl.autoplay = true;
    mediaEl.loop = true;
    mediaEl.muted = true;
    mediaEl.playsInline = true;
  }
  return mediaEl;
}
