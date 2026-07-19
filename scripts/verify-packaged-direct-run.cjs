"use strict";

const { execFile } = require("node:child_process");
const { mkdtemp, rm } = require("node:fs/promises");
const { tmpdir } = require("node:os");
const path = require("node:path");
const { promisify } = require("node:util");
const { _electron } = require("playwright");

const execFileAsync = promisify(execFile);

async function countBackends(executablePath) {
  const { stdout } = await execFileAsync(
    "powershell.exe",
    [
      "-NoProfile",
      "-Command",
      "$target=$env:PEDIT_E2E_BACKEND; @(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'PeditEduBackend.exe' -and $_.ExecutablePath -eq $target }).Count"
    ],
    { env: { ...process.env, PEDIT_E2E_BACKEND: executablePath }, windowsHide: true }
  );
  return Number(stdout.trim());
}

async function main() {
  const executablePath = path.resolve(
    process.env.PEDIT_EDU_EXE || "release/win-unpacked/PeditEdu.exe"
  );
  const backendPath = path.join(path.dirname(executablePath), "resources", "backend", "PeditEduBackend.exe");
  const userData = await mkdtemp(path.join(tmpdir(), "pedit-edu-direct-run-"));
  let electronApp;
  try {
    electronApp = await _electron.launch({
      executablePath,
      args: [`--user-data-dir=${userData}`]
    });
    const window = await electronApp.firstWindow();
    await window.waitForLoadState("domcontentloaded");
    const text = await window.locator("body").innerText();
    if (!text.includes("PEDIT Launcher")) throw new Error("DIRECT_RUN_RESTRICTION_NOT_SHOWN");
    if (await countBackends(backendPath) !== 0) throw new Error("DIRECT_RUN_BACKEND_STARTED");
    console.log(JSON.stringify({
      status: "ready",
      restrictedSurface: true,
      backendStarted: false,
      tokenExposed: false
    }));
  } finally {
    await electronApp?.close().catch(() => undefined);
    const resolved = path.resolve(userData);
    if (!resolved.startsWith(path.resolve(tmpdir()) + path.sep)) throw new Error("E2E_CLEANUP_GUARD_FAILED");
    await rm(resolved, { recursive: true, force: true });
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : "DIRECT_RUN_E2E_FAILED");
  process.exitCode = 1;
});
