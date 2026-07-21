const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const root = path.resolve(__dirname, "../..");

test("package contract is pinned to PEDIT EDU 1.0.5 and canonical SDK 0.4.0", () => {
  const pkg = JSON.parse(fs.readFileSync(path.join(root, "package.json"), "utf8"));
  assert.equal(pkg.name, "pedit-edu");
  assert.equal(pkg.version, "1.0.5");
  assert.equal(pkg.main, "electron/main.cjs");
  assert.equal(pkg.dependencies["@pedit/electron-app-sdk"], "file:packages/electron-app-sdk");
  assert.equal(pkg.build.win.executableName, "PeditEdu");
  assert.equal(pkg.build.win.signtoolOptions.certificateSha1, "59CF023FA686F6B1FB7CFD35DD5BAAD53088181D");
  assert.match(pkg.scripts["build:backend"], /sign-backend\.ps1/);
  assert.match(pkg.scripts["package:launcher-release"], /sign-launcher-manifest\.ps1 -Verify/);
  assert.match(fs.readFileSync(path.join(root, "server.py"), "utf8"), /APP_VERSION = "1\.0\.5"/);
});

test("launcher manifest template uses Protocol v2 and beta.1 minimum launcher", () => {
  const manifestPath = path.join(root, "launcher", "app-manifest.template.json");
  assert.equal(fs.existsSync(manifestPath), true);
  const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
  assert.equal(manifest.appId, "pedit-edu");
  assert.equal(manifest.name, "PEDIT EDU");
  assert.equal(manifest.version, "1.0.5");
  assert.equal(manifest.protocolVersion, 2);
  assert.equal(manifest.minimumLauncherVersion, "0.1.0-beta.1");
  assert.equal(manifest.entryPoint, "PeditEdu.exe");
});

test("release builder emits the canonical immutable four-asset contract", () => {
  const builder = fs.readFileSync(path.join(root, "scripts", "build-launcher-release.cjs"), "utf8");
  const signer = fs.readFileSync(path.join(root, "scripts", "sign-launcher-manifest.ps1"), "utf8");
  assert.match(builder, /path\.join\(output, "app-manifest\.json"\)/);
  assert.match(signer, /app-manifest\.jws/);
  assert.match(signer, /SHA256SUMS\.txt/);
  assert.match(signer, /pedit-app-manifest\+jws/);
  assert.match(signer, /RELEASE_ASSET_SET_INVALID/);
});
