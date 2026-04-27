/** Python subprocess spawner with error handling. */

import { spawn } from "child_process";
import { join } from "path";
import { fileURLToPath } from "url";
import { dirname } from "path";

const __dirname = dirname(fileURLToPath(import.meta.url));

/**
 * Validate that a script path is safe (prevent command injection)
 * @param {string} scriptPath - Path to Python script
 * @returns {boolean} - Whether the path is safe
 */
function isSafeScriptPath(scriptPath) {
  if (!scriptPath || typeof scriptPath !== "string") {
    return false;
  }
  // Only allow paths within backend/ folder
  return scriptPath.includes("backend/") && !scriptPath.includes("..") && !scriptPath.includes(";");
}

/**
 * Run Python script and return promise with output
 * @param {string} scriptPath - Path to Python script (relative to project root)
 * @param {string[]} args - Arguments to pass to script
 * @returns {Promise<string>} - Stdout from Python process
 */
export function runPythonScript(scriptPath, args = []) {
  if (!isSafeScriptPath(scriptPath)) {
    return Promise.reject(new Error(`Invalid script path: ${scriptPath}`));
  }

  if (!Array.isArray(args)) {
    return Promise.reject(new Error("Arguments must be an array"));
  }

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
      console.log("[Python]", data.toString().trim());
    });

    pythonProcess.stderr.on("data", (data) => {
      stderr += data.toString();
      console.error("[Python Error]", data.toString().trim());
    });

    pythonProcess.on("close", (code) => {
      if (code === 0) {
        resolve(stdout);
      } else {
        reject(
          new Error(
            `Python script exited with code ${code}: ${stderr || "No error output"}`
          )
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
