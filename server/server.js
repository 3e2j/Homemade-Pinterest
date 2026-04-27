/** Express server with API endpoints and static file serving. */

import express from "express";
import { fileURLToPath } from "url";
import { dirname, join } from "path";
import { readFile, writeFile } from "fs/promises";
import { dataEndpoint } from "./routes/data.js";
import { refreshEndpoint, statusEndpoint } from "./routes/refresh.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const app = express();
const PORT = 8000;

// Directory paths
const frontendDir = join(__dirname, "../frontend");
const outputDir = join(__dirname, "../output");
const configPath = join(__dirname, "../config.json");

// Middleware
app.use(express.json());

/**
 * Validate configuration object structure
 */
function validateConfig(config) {
  if (!config || typeof config !== "object") {
    return false;
  }

  if (config.server) {
    if (typeof config.server !== "object") return false;
    if ("closeOnPageClose" in config.server && typeof config.server.closeOnPageClose !== "boolean") {
      return false;
    }
  }

  if (config.webp_conversion) {
    if (typeof config.webp_conversion !== "object") return false;
    if ("enabled" in config.webp_conversion && typeof config.webp_conversion.enabled !== "boolean") {
      return false;
    }
    if ("quality" in config.webp_conversion) {
      const quality = config.webp_conversion.quality;
      if (typeof quality !== "number" || quality < 1 || quality > 100) {
        return false;
      }
    }
    if ("method" in config.webp_conversion) {
      const method = config.webp_conversion.method;
      if (typeof method !== "number" || method < 0 || method > 6) {
        return false;
      }
    }
  }

  return true;
}

async function loadConfig() {
  try {
    const content = await readFile(configPath, "utf-8");
    const config = JSON.parse(content);
    if (!validateConfig(config)) {
      console.warn("Config validation failed, returning empty config");
      return {};
    }
    return config;
  } catch (e) {
    console.warn("Failed to load config.json:", e.message);
    return {};
  }
}

async function saveConfig(config) {
  try {
    if (!validateConfig(config)) {
      console.warn("Refusing to save invalid config");
      return false;
    }
    await writeFile(configPath, JSON.stringify(config, null, 2));
    return true;
  } catch (e) {
    console.warn("Failed to save config.json:", e.message);
    return false;
  }
}

// Routes (BEFORE static middleware)
app.get("/data.json", dataEndpoint);
app.post("/refresh", refreshEndpoint);
app.get("/status", statusEndpoint);

app.get("/config", async (req, res) => {
  const config = await loadConfig();
  res.json(config);
});

app.post("/config", async (req, res) => {
  const config = await loadConfig();
  const updates = req.body;

  if (!updates || typeof updates !== "object") {
    return res.status(400).json({ error: "Invalid request body" });
  }

  if (updates.server) {
    if (typeof updates.server !== "object") {
      return res.status(400).json({ error: "server must be an object" });
    }
    config.server = { ...config.server, ...updates.server };
  }

  const saved = await saveConfig(config);
  if (!saved) {
    return res.status(500).json({ error: "Failed to save config" });
  }

  res.json(config);
});

app.post("/shutdown", (req, res) => {
  res.json({ success: true, message: "Server shutting down" });
  console.log("[Server] Shutdown requested from client");
  setTimeout(() => {
    process.exit(0);
  }, 100);
});

// Static files (AFTER API routes)
app.use(express.static(frontendDir));
app.use(express.static(outputDir));

// Serve index.html for all other routes (SPA fallback)
app.use((req, res) => {
  res.sendFile(join(frontendDir, "index.html"));
});

// Start server
const server = app.listen(PORT, () => {
  console.log(`[Server] Listening at http://localhost:${PORT}`);
  console.log("[Server] Press Ctrl+C to stop");
});

// Graceful shutdown
process.on("SIGINT", () => {
  console.log("\n[Server] Shutting down...");
  server.close(() => {
    console.log("[Server] Stopped");
    process.exit(0);
  });
});
