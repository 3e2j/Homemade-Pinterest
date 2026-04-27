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

async function loadConfig() {
  try {
    const content = await readFile(configPath, "utf-8");
    return JSON.parse(content);
  } catch (e) {
    console.warn("Failed to load config.json:", e);
    return { server: { closeOnPageClose: false } };
  }
}

async function saveConfig(config) {
  try {
    await writeFile(configPath, JSON.stringify(config, null, 2));
  } catch (e) {
    console.warn("Failed to save config.json:", e);
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
  
  if (updates.server) {
    config.server = { ...config.server, ...updates.server };
  }
  
  await saveConfig(config);
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
