const assert = require("node:assert/strict");
const test = require("node:test");

test("Electron launcher runtime module can be loaded", () => {
  assert.doesNotThrow(() => require("../../electron/launcher-runtime.cjs"));
});

test("Electron backend host module can be loaded", () => {
  assert.doesNotThrow(() => require("../../electron/backend-host.cjs"));
});
