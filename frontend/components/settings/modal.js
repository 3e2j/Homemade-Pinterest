/** Settings modal UI with deferred config save. */

import { strings } from "../../i18n/en.js";

const t = strings;
let config = {};
let originalConfig = {};
let hasChanges = false;
let closeBtn = null;

async function loadConfig() {
  try {
    const res = await fetch("/config");
    config = await res.json();
    originalConfig = JSON.parse(JSON.stringify(config));
  } catch (e) {
    console.warn("Failed to load config:", e);
    config = {
      server: { closeOnPageClose: false },
      webp_conversion: { enabled: true, quality: 80, method: 6 },
    };
    originalConfig = JSON.parse(JSON.stringify(config));
  }
}

export async function initSettings() {
  await loadConfig();
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
  } catch (err) {
    console.error("Failed to save config:", err);
  }
}
