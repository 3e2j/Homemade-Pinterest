import { MEDIA_IMAGES_DIR, VIDEO_EXTENSIONS } from "../../store/store.js";

export function getMediaSrc(media) {
  if (typeof media === "string" && media.includes("://")) {
    return media;
  }
  if (typeof media === "string" && media.includes("/")) {
    return media;
  }
  return `${MEDIA_IMAGES_DIR}/${media}`;
}

export function isVideoMedia(media) {
  if (typeof media !== "string") return false;
  const lower = media.toLowerCase();
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
