#!/usr/bin/env node
"use strict";

const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const packageRoot = path.resolve(__dirname, "..");
const venvRoot = process.env.MEDIA_INFORMATION_DOWNLOAD_VENV
  ? path.resolve(process.env.MEDIA_INFORMATION_DOWNLOAD_VENV)
  : path.join(os.homedir(), ".media-information-download", "venv");
const isWindows = process.platform === "win32";
const venvPython = isWindows
  ? path.join(venvRoot, "Scripts", "python.exe")
  : path.join(venvRoot, "bin", "python");

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: packageRoot,
    stdio: options.stdio || "inherit",
    env: {
      ...process.env,
      PYTHONPATH: packageRoot,
    },
  });
  return result;
}

function commandExists(command, args = ["--version"]) {
  const result = spawnSync(command, args, { stdio: "ignore" });
  return result.status === 0;
}

function pythonCommand() {
  if (process.env.PYTHON) {
    return { command: process.env.PYTHON, args: [] };
  }
  if (isWindows && commandExists("py", ["-3", "--version"])) {
    return { command: "py", args: ["-3"] };
  }
  if (commandExists("python3")) {
    return { command: "python3", args: [] };
  }
  if (commandExists("python")) {
    return { command: "python", args: [] };
  }
  return null;
}

function ensureVenv() {
  if (fs.existsSync(venvPython)) {
    return;
  }

  fs.mkdirSync(path.dirname(venvRoot), { recursive: true });
  const python = pythonCommand();
  if (!python) {
    console.error("Python 3.10+ is required. Install Python and rerun this command.");
    process.exit(1);
  }

  const result = run(python.command, [...python.args, "-m", "venv", venvRoot]);
  if (result.status !== 0) {
    process.exit(result.status || 1);
  }
}

function ensureDependencies() {
  const check = run(venvPython, ["-c", "import yt_dlp, whisper, torch"], { stdio: "ignore" });
  if (check.status === 0) {
    return;
  }

  const pip = run(venvPython, [
    "-m",
    "pip",
    "install",
    "-r",
    path.join(packageRoot, "requirements-transcribe.txt"),
  ]);
  if (pip.status !== 0) {
    process.exit(pip.status || 1);
  }
}

function warnIfFfmpegMissing() {
  const command = isWindows ? "where" : "which";
  if (!commandExists(command, ["ffmpeg"])) {
    console.warn("Warning: ffmpeg is not available on PATH. Downloads may fail during MP3 conversion.");
  }
}

ensureVenv();
ensureDependencies();
warnIfFfmpegMissing();

const child = run(venvPython, [path.join(packageRoot, "media_tui.py"), ...process.argv.slice(2)]);
if (child.signal) {
  process.kill(process.pid, child.signal);
}
process.exit(child.status || 0);
