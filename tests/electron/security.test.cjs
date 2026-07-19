const assert = require("node:assert/strict");
const test = require("node:test");

const {
  backendCsp,
  browserWindowOptions,
  isAllowedExternalUrl,
  isExactBackendNavigation
} = require("../../electron/security.cjs");

test("business BrowserWindow uses the hardened Electron boundary", () => {
  const options = browserWindowOptions("C:\\PEDIT\\preload.cjs");
  assert.equal(options.webPreferences.contextIsolation, true);
  assert.equal(options.webPreferences.nodeIntegration, false);
  assert.equal(options.webPreferences.sandbox, true);
  assert.equal(options.webPreferences.preload, "C:\\PEDIT\\preload.cjs");
});

test("navigation permits only the exact backend origin", () => {
  const origin = "http://127.0.0.1:49152";
  assert.equal(isExactBackendNavigation(`${origin}/`, origin), true);
  assert.equal(isExactBackendNavigation(`${origin}/static/app.js`, origin), true);
  assert.equal(isExactBackendNavigation("http://localhost:49152/", origin), false);
  assert.equal(isExactBackendNavigation("http://127.0.0.1:49153/", origin), false);
  assert.equal(isExactBackendNavigation("https://attacker.invalid/", origin), false);
});

test("external browser navigation is deny-by-default with an explicit allowlist", () => {
  assert.equal(isAllowedExternalUrl("https://pedit.kr/help", ["https://pedit.kr"]), true);
  assert.equal(isAllowedExternalUrl("https://pedit.kr.attacker.invalid/", ["https://pedit.kr"]), false);
  assert.equal(isAllowedExternalUrl("http://pedit.kr/help", ["https://pedit.kr"]), false);
});

test("CSP blocks remote code and framing", () => {
  const csp = backendCsp("http://127.0.0.1:49152");
  assert.match(csp, /default-src 'self'/);
  assert.match(csp, /connect-src 'self' http:\/\/127\.0\.0\.1:49152/);
  assert.match(csp, /frame-ancestors 'none'/);
  assert.doesNotMatch(csp, /https:\/\/*/);
});
