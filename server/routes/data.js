/** GET /data.json endpoint handler. */

import { join } from "path";
import { fileURLToPath } from "url";
import { dirname, resolve } from "path";
import { readFileSync, existsSync } from "fs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(join(__dirname, "../../"));

/**
 * Serve data.json endpoint
 */
export function dataEndpoint(req, res) {
  const dataPath = join(projectRoot, "output/data.json");

  if (!existsSync(dataPath)) {
    console.log("[Routes] data.json not found, returning empty array");
    return res.json([]);
  }

  try {
    const data = JSON.parse(readFileSync(dataPath, "utf8"));
    res.json(data);
  } catch (err) {
    console.error("[Routes] Error reading data.json:", err.message);
    res.status(500).json({ error: "Failed to read data.json" });
  }
}
