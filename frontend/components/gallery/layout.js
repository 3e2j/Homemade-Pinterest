/** Masonry layout engine for tweet cards. */

import { CARD_WIDTH, COLUMN_GUTTER } from "../../store/store.js";

const PADDING = 8; // matches #grid padding in CSS
const MIN_COLUMNS = 2;

// Cached state from the last layout pass, so appending a new batch only
// positions the newly added cards instead of re-measuring everything.
let layoutState = null;

function computeColumns(containerWidth) {
  const innerWidth = Math.max(0, containerWidth - PADDING * 2);

  let columns = MIN_COLUMNS;
  for (let c = MIN_COLUMNS; c <= Math.floor(innerWidth / CARD_WIDTH); c++) {
    const requiredWidth = c * CARD_WIDTH + (c - 1) * COLUMN_GUTTER;
    if (requiredWidth <= innerWidth) {
      columns = c;
    } else {
      break;
    }
  }

  const totalGutterWidth = COLUMN_GUTTER * (columns - 1);
  const dynamicCardWidth = (innerWidth - totalGutterWidth) / columns;

  return { columns, dynamicCardWidth };
}

export function layoutMasonry(container, { reset = false } = {}) {
  if (!container) return;

  const containerWidth = container.clientWidth;
  const { columns, dynamicCardWidth } = computeColumns(containerWidth);
  const cards = Array.from(container.children);

  const needsFullRelayout =
    reset ||
    !layoutState ||
    layoutState.columns !== columns ||
    layoutState.containerWidth !== containerWidth ||
    cards.length < layoutState.positionedCount;

  const startIndex = needsFullRelayout ? 0 : layoutState.positionedCount;
  const heights = needsFullRelayout
    ? new Array(columns).fill(0)
    : layoutState.heights;

  const newCards = cards.slice(startIndex);

  if (newCards.length) {
    // Phase 1: writes only. Widths must land before we measure heights.
    const spans = newCards.map((card) =>
      card.classList.contains("multiple-media") ? Math.min(2, columns) : 1,
    );
    newCards.forEach((card, i) => {
      const span = spans[i];
      const width = dynamicCardWidth * span + COLUMN_GUTTER * (span - 1);
      card.style.position = "absolute";
      card.style.width = `${width}px`;
    });

    // Phase 2: reads only. One forced reflow for the whole batch instead
    // of one per card.
    const cardHeights = newCards.map((card) => card.offsetHeight);

    // Phase 3: writes only, driven purely by in-memory numbers.
    newCards.forEach((card, i) => {
      const span = spans[i];
      let minY = Infinity;
      let minX = 0;
      for (let c = 0; c <= columns - span; c++) {
        const sliceHeight = Math.max(...heights.slice(c, c + span));
        if (sliceHeight < minY) {
          minY = sliceHeight;
          minX = c;
        }
      }

      const x = PADDING + minX * (dynamicCardWidth + COLUMN_GUTTER);
      card.style.transform = `translate(${x}px, ${minY}px)`;

      const newHeight = minY + cardHeights[i] + COLUMN_GUTTER;
      for (let c = 0; c < span; c++) {
        heights[minX + c] = newHeight;
      }
    });
  }

  container.style.height = `${Math.max(...heights)}px`;

  layoutState = {
    containerWidth,
    columns,
    heights,
    positionedCount: cards.length,
  };
}

export function setupResizeListener() {
  window.addEventListener("resize", () => {
    const grid = document.getElementById("grid");
    if (grid) layoutMasonry(grid, { reset: true });
  });
}
