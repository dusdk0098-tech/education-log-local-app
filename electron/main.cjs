"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { app, BrowserWindow, ipcMain, session, shell } = require("electron");
const { createBackendHost } = require("./backend-host.cjs");
const { shutdownApplication } = require("./app-shutdown.cjs");
const { createFailClosedController } = require("./fail-closed.cjs");
const { establishLauncherRuntime, prepareLaunchEnvironment } = require("./launcher-runtime.cjs");
const { browserWindowOptions, isAllowedExternalUrl, isExactBackendNavigation } = require("./security.cjs");
const { reportStartupFailure, startupError, withStartupTimeout } = require("./startup-boundary.cjs");

const EXTERNAL_ORIGINS = ["https://pedit.kr"];
const requiresLauncher = app.isPackaged
  && fs.existsSync(path.join(process.resourcesPath, "launcher-required.json"));
const bootstrap = prepareLaunchEnvironment({ argv: process.argv, requiresLauncher });
let runtime = bootstrap;
let backend = null;
let businessWindow = null;
let restrictedWindow = null;
let quitting = false;

async function closeBusinessSurface() {
  if (businessWindow && !businessWindow.isDestroyed()) businessWindow.destroy();
  businessWindow = null;
}

async function stopBackend() {
  if (backend) await backend.stop();
  backend = null;
}

function createRestrictedWindow() {
  if (restrictedWindow && !restrictedWindow.isDestroyed()) {
    restrictedWindow.show();
    restrictedWindow.focus();
    return restrictedWindow;
  }
  const file = path.join(__dirname, "restricted.html");
  const allowedUrl = pathToFileURL(file).href;
  restrictedWindow = new BrowserWindow({
    width: 720,
    height: 480,
    minWidth: 640,
    minHeight: 420,
    show: false,
    title: "PEDIT EDU",
    icon: path.join(__dirname, "..", "static", "app.ico"),
    autoHideMenuBar: true,
    backgroundColor: "#0b1218",
    webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true }
  });
  restrictedWindow.setMenuBarVisibility(false);
  restrictedWindow.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  restrictedWindow.webContents.on("will-navigate", (event, target) => {
    if (target !== allowedUrl) event.preventDefault();
  });
  restrictedWindow.once("ready-to-show", () => restrictedWindow?.show());
  restrictedWindow.once("closed", () => {
    restrictedWindow = null;
  });
  void restrictedWindow.loadFile(file);
  return restrictedWindow;
}

async function showRestriction() {
  await closeBusinessSurface();
  createRestrictedWindow();
}

const failClosed = createFailClosedController({ closeBusinessSurface, stopBackend, showRestriction });

function installRequestBoundary(targetSession, backendHost) {
  const filter = { urls: [`${backendHost.origin}/*`] };
  targetSession.setPermissionRequestHandler((_webContents, _permission, callback) => callback(false));
  targetSession.webRequest.onBeforeSendHeaders(filter, (details, callback) => {
    const headers = { ...details.requestHeaders };
    for (const name of Object.keys(headers)) {
      if (name.toLowerCase() === "x-pedit-backend-session") delete headers[name];
    }
    headers["X-Pedit-Backend-Session"] = backendHost.secret;
    callback({ requestHeaders: headers });
  });
}

async function createBusinessWindow(backendHost) {
  const preload = path.join(__dirname, "preload.cjs");
  try {
    businessWindow = new BrowserWindow({
      ...browserWindowOptions(preload),
      icon: path.join(__dirname, "..", "static", "app.ico")
    });
  } catch {
    throw startupError("BUSINESS_WINDOW_CREATE_FAILED");
  }
  const window = businessWindow;
  window.setMenuBarVisibility(false);
  try {
    installRequestBoundary(window.webContents.session, backendHost);
  } catch {
    throw startupError("BUSINESS_WINDOW_BOUNDARY_FAILED");
  }
  window.webContents.setWindowOpenHandler(({ url }) => {
    if (isAllowedExternalUrl(url, EXTERNAL_ORIGINS)) void shell.openExternal(url);
    return { action: "deny" };
  });
  const guardNavigation = (event, target) => {
    if (!isExactBackendNavigation(target, backendHost.origin)) event.preventDefault();
  };
  window.webContents.on("will-navigate", guardNavigation);
  window.webContents.on("will-redirect", guardNavigation);
  window.webContents.on("will-attach-webview", (event) => event.preventDefault());
  window.webContents.on("render-process-gone", () => void failClosed.fail("RENDERER_EXITED"));
  window.once("closed", () => {
    if (businessWindow === window) businessWindow = null;
  });
  await withStartupTimeout(
    window.loadURL(`${backendHost.origin}/`),
    8_000,
    "BUSINESS_WINDOW_LOAD_FAILED",
  );
  await withStartupTimeout(
    runtime.connection.reportReady(),
    3_000,
    "APP_READY_REPORT_FAILED",
  );
  window.show();
  window.focus();
}

async function shutdownFromLauncher() {
  if (quitting) return;
  quitting = true;
  await shutdownApplication({ closeBusinessSurface, stopBackend });
}

function backendExecutablePath() {
  if (app.isPackaged) return path.join(process.resourcesPath, "backend", "PeditEduBackend.exe");
  return path.join(__dirname, "..", "dist-backend", "PeditEduBackend.exe");
}

async function start() {
  if (bootstrap.status.mode !== "pending") {
    createRestrictedWindow();
    return;
  }
  runtime = await establishLauncherRuntime({
    bootstrap,
    appVersion: app.getVersion(),
    dataSchemaVersion: 1,
    onShutdown: shutdownFromLauncher,
    onShutdownComplete: () => app.quit(),
    onFailClosed: (reason) => failClosed.fail(reason),
    onSessionRenewed: async (sessionContext) => {
      if (!backend) throw Object.assign(new Error("BACKEND_NOT_READY"), { code: "BACKEND_NOT_READY" });
      await backend.renewSession(sessionContext);
    }
  });
  if (runtime.status.mode !== "connected") {
    createRestrictedWindow();
    return;
  }
  backend = await createBackendHost({
    executablePath: backendExecutablePath(),
    dataDirectory: runtime.dataDirectory,
    sessionContext: runtime.connection.sessionContext,
    onUnexpectedExit: (reason) => failClosed.fail(reason)
  });
  await createBusinessWindow(backend);
}

ipcMain.handle("launcher:status", (event) => {
  if (!businessWindow || businessWindow.isDestroyed() || event.sender !== businessWindow.webContents) {
    throw new Error("IPC_SENDER_NOT_ALLOWED");
  }
  return { mode: runtime.status.mode, appId: "pedit-edu", version: app.getVersion() };
});

app.whenReady().then(start).catch((error) => void reportStartupFailure(runtime, failClosed, error));
app.on("window-all-closed", () => {
  if (!quitting && failClosed.shouldQuitOnWindowAllClosed()) app.quit();
});
app.on("before-quit", (event) => {
  if (quitting) return;
  event.preventDefault();
  quitting = true;
  Promise.resolve(runtime.status.mode === "connected" ? runtime.connection.close("app-quit") : undefined)
    .catch(() => {})
    .then(stopBackend)
    .finally(() => app.quit());
});
