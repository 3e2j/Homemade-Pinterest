/** Python subprocess spawner and SSE formatter. */

import { spawn } from "child_process";
import { join } from "path";
import { fileURLToPath } from "url";
import { dirname } from "path";

const __dirname = dirname(fileURLToPath(import.meta.url));

/**
 * Run Python script and return promise with output
 * @param {string} scriptPath - Path to Python script (relative to project root)
 * @param {string[]} args - Arguments to pass to script
 * @returns {Promise<string>} - Stdout from Python process
 */
export function runPythonScript(scriptPath, args = []) {
  const projectRoot = join(__dirname, "../../");
  const pythonPath = join(projectRoot, ".venv/bin/python");

  return new Promise((resolve, reject) => {
    const pythonProcess = spawn(pythonPath, [scriptPath, ...args], {
      cwd: projectRoot,
      env: {
        ...process.env,
        PYTHONPATH: projectRoot,
      },
    });

    let stdout = "";
    let stderr = "";

    pythonProcess.stdout.on("data", (data) => {
      stdout += data.toString();
      console.log("[Python]", data.toString());
    });

    pythonProcess.stderr.on("data", (data) => {
      stderr += data.toString();
      console.error("[Python Error]", data.toString());
    });

    pythonProcess.on("close", (code) => {
      if (code === 0) {
        resolve(stdout);
      } else {
        reject(
          new Error(
            `Python script failed with code ${code}: ${stderr || "No error message"}`,
          ),
        );
      }
    });

    pythonProcess.on("error", (err) => {
      reject(new Error(`Failed to start Python process: ${err.message}`));
    });
  });
}

/**
 * Download tweets using Python backend
 */
export async function downloadTweets() {
  console.log("[Server] Starting tweet download...");
  return runPythonScript("backend/tweets/download_tweets.py");
}

/**
 * Process media using Python backend
 */
export async function processMedia() {
  console.log("[Server] Starting media processing...");
  return runPythonScript("backend/media/processor.py");
}
