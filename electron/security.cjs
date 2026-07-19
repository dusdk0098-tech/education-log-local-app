"use strict";

function browserWindowOptions(preload) {
  return {
    width: 1440,
    height: 900,
    minWidth: 1120,
    minHeight: 720,
    show: false,
    title: "PEDIT EDU",
    autoHideMenuBar: true,
    backgroundColor: "#0b1218",
    webPreferences: {
      preload,
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  };
}

function isExactBackendNavigation(target, origin) {
  try {
    const targetUrl = new URL(target);
    const allowed = new URL(origin);
    return allowed.protocol === "http:"
      && allowed.hostname === "127.0.0.1"
      && targetUrl.origin === allowed.origin;
  } catch {
    return false;
  }
}

function isAllowedExternalUrl(target, allowedOrigins) {
  try {
    const url = new URL(target);
    return url.protocol === "https:" && allowedOrigins.includes(url.origin);
  } catch {
    return false;
  }
}

function backendCsp(origin) {
  return [
    "default-src 'self'",
    "base-uri 'none'",
    "object-src 'none'",
    "frame-ancestors 'none'",
    "form-action 'self'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    "style-src 'self' 'unsafe-inline'",
    "script-src 'self'",
    `connect-src 'self' ${origin}`
  ].join("; ");
}

module.exports = { backendCsp, browserWindowOptions, isAllowedExternalUrl, isExactBackendNavigation };
