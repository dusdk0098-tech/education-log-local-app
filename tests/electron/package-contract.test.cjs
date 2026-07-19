const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const root = path.resolve(__dirname, "../..");

test("package contract is pinned to PEDIT EDU 1.0.4 and canonical SDK 0.4.0", () => {
  const pkg = JSON.parse(fs.readFileSync(path.join(root, "package.json"), "utf8"));
  assert.equal(pkg.name, "pedit-edu");
  assert.equal(pkg.version, "1.0.4");
  assert.equal(pkg.main, "electron/main.cjs");
  assert.equal(pkg.dependencies["@pedit/electron-app-sdk"], "file:packages/electron-app-sdk");
  assert.equal(pkg.build.win.executableName, "PeditEdu");
  assert.equal(pkg.build.win.signtoolOptions.certificateSha1, "B92BEC0B6370F10BC34CB27304921DE75B3073C6");
  assert.match(pkg.scripts["build:backend"], /sign-backend\.ps1/);
});

test("launcher manifest template uses Protocol v2 and beta.1 minimum launcher", () => {
  const manifestPath = path.join(root, "launcher", "app-manifest.template.json");
  assert.equal(fs.existsSync(manifestPath), true);
  const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
  assert.equal(manifest.appId, "pedit-edu");
  assert.equal(manifest.name, "PEDIT EDU");
  assert.equal(manifest.version, "1.0.4");
  assert.equal(manifest.protocolVersion, 2);
  assert.equal(manifest.minimumLauncherVersion, "0.1.0-beta.1");
  assert.equal(manifest.entryPoint, "PeditEdu.exe");
});
