/** Masonry layout engine for tweet cards. */

import { CARD_WIDTH, COLUMN_GUTTER } from "../../store/store.js";

export function layoutMasonry(container) {
  if (!container) return;

  const gutter = COLUMN_GUTTER;
  const padding = 8; // matches #grid padding in CSS
  const minColumns = 2;

  const containerWidth = container.clientWidth;
  const innerWidth = Math.max(0, containerWidth - padding * 2);

  // Find max columns that can fit without overflow
  let columns = minColumns;
  for (let c = minColumns; c <= Math.floor(innerWidth / CARD_WIDTH); c++) {
    // Check if c columns fit: c cards + (c-1) gutters
    const requiredWidth = c * CARD_WIDTH + (c - 1) * gutter;
    if (requiredWidth <= innerWidth) {
      columns = c;
    } else {
      break;
    }
  }

  // Scale card width to fill available space without gaps
  const totalGutterWidth = gutter * (columns - 1);
  const dynamicCardWidth = (innerWidth - totalGutterWidth) / columns;

  const heights = new Array(columns).fill(0);
  const cards = Array.from(container.children);

  for (const card of cards) {
    const span = card.classList.contains("multiple-media")
      ? Math.min(2, columns)
      : 1;
    const width = dynamicCardWidth * span + gutter * (span - 1);

    let minY = Infinity;
    let minX = 0;
    for (let i = 0; i <= columns - span; i++) {
      const sliceHeight = Math.max(...heights.slice(i, i + span));
      if (sliceHeight < minY) {
        minY = sliceHeight;
        minX = i;
      }
    }

    const x = padding + minX * (dynamicCardWidth + gutter);
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

export function setupResizeListener() {
  window.addEventListener("resize", () => {
    const grid = document.getElementById("grid");
    if (grid) layoutMasonry(grid);
  });
}
