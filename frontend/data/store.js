export const BATCH_SIZE = 100;
export const WS_PORT = 8765;
export const WS_PING_INTERVAL_MS = 5000;
export const DATA_FILE = "data.json";
export const MEDIA_IMAGES_DIR = "media/images";
export const AVATAR_DIR = "media/avatars";
export const MEDIA_MARGIN = 10;
export const HALF_MARGIN = MEDIA_MARGIN / 2;
export const CARD_WIDTH = 300;
export const COLUMN_GUTTER = 8;
export const SCROLL_ROOT_MARGIN = "1000px";
export const SAME_ASPECT_TOLERANCE = 0.01;
export const WIDE_IMAGE_THRESHOLD = 1.2;
export const VIDEO_EXTENSIONS = [".mp4", ".webm", ".mov"];

export let tweets = [];
export let loadedCount = 0;

export function setTweets(newTweets) {
  tweets = newTweets;
}

export function setLoadedCount(count) {
  loadedCount = count;
}

export function addLoadedCount(count) {
  loadedCount += count;
}

export function getTweets() {
  return tweets;
}

export function getLoadedCount() {
  return loadedCount;
}
