import { DATA_FILE } from "./store.js";

export async function fetchTweetsData() {
  const url = `${DATA_FILE}?_=${Date.now()}`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load data.json");
  return res.json();
}

export async function prependNewTweets(newTweets, insertTweetsFunc) {
  if (!newTweets || !newTweets.length) return;
  await insertTweetsFunc(newTweets, { prepend: true });
}
