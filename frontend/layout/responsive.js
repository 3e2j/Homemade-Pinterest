import { layoutMasonry } from "./masonry.js";

export function setupResizeListener() {
  window.addEventListener("resize", () =>
    layoutMasonry(document.getElementById("grid")),
  );
}
