import { AVATAR_DIR } from "../data/store.js";

export function getAvatarSrc(avatar) {
  if (typeof avatar === "string" && avatar.startsWith("http")) {
    return avatar;
  }
  if (typeof avatar === "string" && avatar.includes("/")) {
    return avatar;
  }
  return `${AVATAR_DIR}/${avatar}`;
}

export function createAvatarElement(tweet) {
  if (!tweet.avatar) return null;

  const avatar = document.createElement("img");
  avatar.className = "avatar";
  avatar.src = getAvatarSrc(tweet.avatar);
  return avatar;
}
