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
const outputRoot = process.env.MEDIA_OUTPUT_DIR
  ? path.resolve(process.env.MEDIA_OUTPUT_DIR)
  : path.join(os.homedir(), ".media-information-download", "output");
const isWindows = process.platform === "win32";
const venvPython = isWindows
  ? path.join(venvRoot, "Scripts", "python.exe")
  : path.join(venvRoot, "bin", "python");
const desktopAliasArgs = new Set(["--desktop-output-alias", "--create-desktop-output-alias"]);

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: packageRoot,
    stdio: options.stdio || "inherit",
    env: {
      ...process.env,
      MEDIA_OUTPUT_DIR: outputRoot,
      MEDIA_INFORMATION_DOWNLOAD_VENV: venvRoot,
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

function splitWrapperArgs(args) {
  return {
    createDesktopOutputAlias: args.some((arg) => desktopAliasArgs.has(arg)),
    appArgs: args.filter((arg) => !desktopAliasArgs.has(arg)),
  };
}

function pathToFileUrl(value) {
  return `file:///${value.replace(/\\/g, "/").replace(/^\/+/, "")}`;
}

function createDesktopOutputAlias() {
  const desktopPath = path.join(os.homedir(), "Desktop");
  const aliasName = "Media Information Download Output";
  const aliasPath = path.join(desktopPath, aliasName);

  fs.mkdirSync(outputRoot, { recursive: true });
  fs.mkdirSync(desktopPath, { recursive: true });
  if (fs.existsSync(aliasPath)) {
    console.log(`Output alias already exists: ${aliasPath}`);
    return;
  }

  if (isWindows) {
    const command = `mklink /J "${aliasPath}" "${outputRoot}"`;
    const result = spawnSync("cmd", ["/d", "/s", "/c", command], { stdio: "ignore" });
    if (result.status === 0) {
      console.log(`Created output alias: ${aliasPath}`);
      return;
    }

    const shortcutPath = `${aliasPath}.url`;
    fs.writeFileSync(shortcutPath, `[InternetShortcut]\nURL=${pathToFileUrl(outputRoot)}\n`, "utf8");
    console.log(`Created output shortcut: ${shortcutPath}`);
    return;
  }

  fs.symlinkSync(outputRoot, aliasPath, "dir");
  console.log(`Created output alias: ${aliasPath}`);
}

const wrapperArgs = splitWrapperArgs(process.argv.slice(2));

ensureVenv();
ensureDependencies();
warnIfFfmpegMissing();
if (wrapperArgs.createDesktopOutputAlias) {
  createDesktopOutputAlias();
}

const child = run(venvPython, [path.join(packageRoot, "media_tui.py"), ...wrapperArgs.appArgs]);
if (child.signal) {
  process.kill(process.pid, child.signal);
}
process.exit(child.status || 0);
