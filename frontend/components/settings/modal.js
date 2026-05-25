/** Settings modal UI with deferred config save. */

import { strings } from "../../i18n/en.js";
import { layoutMasonry } from "../gallery/layout.js";

const t = strings;
let config = {};
let originalConfig = {};
let hasChanges = false;
let closeBtn = null;
let refreshAllHandler = null;
const HOLD_CONFIRM_MS = 1200;

function normalizeConfig() {
  config.server = config.server || { closeOnPageClose: false };
  config.webp_conversion = config.webp_conversion || {
    enabled: true,
    quality: 80,
    method: 6,
  };
  config.ui = {
    compact: false,
    edgeMedia: false,
    ...(config.ui || {}),
  };
}

function refreshLayout() {
  const grid = document.getElementById("grid");
  if (!grid) return;
  requestAnimationFrame(() => {
    layoutMasonry(grid);
  });
}

function applyUiSettings() {
  if (!document.body) return;
  document.body.classList.toggle("compact-mode", !!config.ui?.compact);
  document.body.classList.toggle("edge-media", !!config.ui?.edgeMedia);
  refreshLayout();
}

async function loadConfig() {
  try {
    const res = await fetch("/config");
    config = await res.json();
  } catch (e) {
    console.warn("Failed to load config:", e);
    config = {};
  }
  normalizeConfig();
  originalConfig = JSON.parse(JSON.stringify(config));
  applyUiSettings();
}

export async function initSettings() {
  await loadConfig();
}

export function setRefreshAllHandler(handler) {
  refreshAllHandler = handler;
}

export function setupSettingsButton() {
  const btn = document.getElementById("settings-btn");
  if (btn) {
    btn.addEventListener("click", openSettingsModal);
  }
}

export function createSettingsButton() {
  const btn = document.createElement("button");
  btn.id = "settings-btn";
  btn.textContent = t.buttons.settings;
  btn.addEventListener("click", openSettingsModal);
  return btn;
}

function checkIfChanged() {
  return JSON.stringify(config) !== JSON.stringify(originalConfig);
}

function updateButtonState() {
  if (checkIfChanged()) {
    hasChanges = true;
    closeBtn.textContent = t.buttons.closeAndApply;
    closeBtn.classList.add("has-changes");
  } else {
    hasChanges = false;
    closeBtn.textContent = t.buttons.close;
    closeBtn.classList.remove("has-changes");
  }
}

function createCheckboxSetting(label, getter, setter) {
  const container = document.createElement("label");
  container.className = "settings-option";

  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.checked = getter() || false;
  checkbox.addEventListener("change", (e) => {
    setter(e.target.checked);
    updateButtonState();
  });

  const text = document.createElement("span");
  text.textContent = label;

  container.appendChild(checkbox);
  container.appendChild(text);
  return container;
}

function createNumberInputSetting(label, getter, setter, min, max) {
  const container = document.createElement("label");
  container.className = "settings-option";

  const text = document.createElement("span");
  text.textContent = label;
  container.appendChild(text);

  const input = document.createElement("input");
  input.type = "number";
  input.min = min;
  input.max = max;
  input.value = getter() || 0;
  input.addEventListener("change", (e) => {
    setter(parseInt(e.target.value));
    updateButtonState();
  });
  container.appendChild(input);

  return container;
}

function createSection(title) {
  const section = document.createElement("div");
  section.className = "settings-section";

  const heading = document.createElement("h3");
  heading.textContent = title;
  section.appendChild(heading);

  return section;
}

function createActionButton(label, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "settings-action-btn";
  button.textContent = label;
  button.addEventListener("click", onClick);
  return button;
}

function setupHoldToConfirm(button, onConfirm) {
  let rafId = null;
  let startTime = 0;
  let holding = false;
  let triggered = false;
  let activePointerId = null;

  const setProgress = (value) => {
    button.style.setProperty("--hold-progress", `${value}%`);
  };

  const reset = () => {
    holding = false;
    startTime = 0;
    if (rafId) cancelAnimationFrame(rafId);
    rafId = null;
    if (!triggered) setProgress(0);
  };

  const tick = (time) => {
    if (!holding) return;
    if (!startTime) startTime = time;
    const progress = Math.min((time - startTime) / HOLD_CONFIRM_MS, 1);
    setProgress(progress * 100);
    if (progress >= 1) {
      holding = false;
      triggered = true;
      setProgress(100);
      if (activePointerId !== null) {
        button.releasePointerCapture?.(activePointerId);
        activePointerId = null;
      }
      onConfirm();
      return;
    }
    rafId = requestAnimationFrame(tick);
  };

  button.addEventListener("pointerdown", (e) => {
    if (button.disabled) return;
    triggered = false;
    holding = true;
    activePointerId = e.pointerId;
    button.setPointerCapture?.(e.pointerId);
    rafId = requestAnimationFrame(tick);
  });

  const cancel = (e) => {
    if (!holding) return;
    if (activePointerId !== null) {
      button.releasePointerCapture?.(activePointerId);
      activePointerId = null;
    }
    reset();
  };

  button.addEventListener("pointerup", cancel);
  button.addEventListener("pointerleave", cancel);
  button.addEventListener("pointercancel", cancel);
}

async function openSettingsModal() {
  await loadConfig();
  hasChanges = false;

  const modal = document.createElement("div");
  modal.id = "settings-modal";

  const content = document.createElement("div");

  const title = document.createElement("h2");
  title.textContent = t.settings.title;
  content.appendChild(title);

  // Server settings section
  const serverSection = createSection(t.settings.server.title);
  serverSection.appendChild(
    createCheckboxSetting(
      t.settings.server.closeOnPageClose,
      () => config.server?.closeOnPageClose,
      (value) => {
        config.server = config.server || {};
        config.server.closeOnPageClose = value;
      },
    ),
  );
  content.appendChild(serverSection);

  // WebP settings section
  const webpSection = createSection(t.settings.webp.title);
  webpSection.appendChild(
    createCheckboxSetting(
      t.settings.webp.enabled,
      () => config.webp_conversion?.enabled,
      (value) => {
        config.webp_conversion = config.webp_conversion || {};
        config.webp_conversion.enabled = value;
      },
    ),
  );
  webpSection.appendChild(
    createNumberInputSetting(
      t.settings.webp.quality,
      () => config.webp_conversion?.quality,
      (value) => {
        config.webp_conversion = config.webp_conversion || {};
        config.webp_conversion.quality = value;
      },
      1,
      100,
    ),
  );
  webpSection.appendChild(
    createNumberInputSetting(
      t.settings.webp.method,
      () => config.webp_conversion?.method,
      (value) => {
        config.webp_conversion = config.webp_conversion || {};
        config.webp_conversion.method = value;
      },
      0,
      6,
    ),
  );
  content.appendChild(webpSection);

  // Display settings section
  const displaySection = createSection(t.settings.display.title);
  displaySection.appendChild(
    createCheckboxSetting(
      t.settings.display.compact,
      () => config.ui?.compact,
      (value) => {
        config.ui = config.ui || {};
        config.ui.compact = value;
      },
    ),
  );
  displaySection.appendChild(
    createCheckboxSetting(
      t.settings.display.edgeMedia,
      () => config.ui?.edgeMedia,
      (value) => {
        config.ui = config.ui || {};
        config.ui.edgeMedia = value;
      },
    ),
  );
  content.appendChild(displaySection);

  if (refreshAllHandler) {
    const dataSection = createSection(t.settings.data.title);
    const refreshAllButton = createActionButton(
      t.settings.data.refreshAll,
      () => {},
    );
    refreshAllButton.classList.add("hold-confirm");
    refreshAllButton.style.setProperty("--hold-progress", "0%");
    setupHoldToConfirm(refreshAllButton, async () => {
      const originalText = refreshAllButton.textContent;
      refreshAllButton.disabled = true;
      refreshAllButton.textContent = t.refresh.refreshing;

      try {
        await refreshAllHandler();
        refreshAllButton.textContent = t.refresh.updated;
      } catch (e) {
        refreshAllButton.textContent = t.refresh.error;
      } finally {
        setTimeout(() => {
          refreshAllButton.textContent = originalText;
          refreshAllButton.disabled = false;
          refreshAllButton.style.setProperty("--hold-progress", "0%");
        }, 1500);
      }
    });
    dataSection.appendChild(refreshAllButton);
    content.appendChild(dataSection);
  }

  closeBtn = document.createElement("button");
  closeBtn.textContent = t.buttons.close;
  closeBtn.className = "close-settings-btn";
  closeBtn.addEventListener("click", async () => {
    if (hasChanges) {
      await saveConfig();
    }
    modal.remove();
  });
  content.appendChild(closeBtn);

  modal.appendChild(content);

  modal.addEventListener("click", (e) => {
    if (e.target === modal) modal.remove();
  });

  document.body.appendChild(modal);
}

async function saveConfig() {
  try {
    await fetch("/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    });
    originalConfig = JSON.parse(JSON.stringify(config));
    hasChanges = false;
    applyUiSettings();
  } catch (err) {
    console.error("Failed to save config:", err);
  }
}
