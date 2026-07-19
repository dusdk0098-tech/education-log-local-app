"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const {
  reportStartupFailure,
  startupErrorCode,
  withStartupTimeout,
} = require("../../electron/startup-boundary.cjs");

test("startup diagnostics expose only an allowlisted code", () => {
  assert.equal(startupErrorCode({ code: "BUSINESS_WINDOW_LOAD_FAILED" }), "BUSINESS_WINDOW_LOAD_FAILED");
  assert.equal(startupErrorCode(new Error("token=must-not-leak")), "APP_START_FAILED");
});

test("startup timeout is finite and normalized", async () => {
  await assert.rejects(
    withStartupTimeout(new Promise(() => {}), 5, "BUSINESS_WINDOW_LOAD_FAILED"),
    (error) => error.code === "BUSINESS_WINDOW_LOAD_FAILED",
  );
});

test("connected startup failure reports a sanitized app error before fail-closed", async () => {
  const calls = [];
  const runtime = {
    status: { mode: "connected" },
    connection: {
      reportError: async (...args) => calls.push(["report", ...args]),
    },
  };
  const failClosed = { fail: async (code) => calls.push(["fail", code]) };

  await reportStartupFailure(runtime, failClosed, new Error("secret internal detail"));
  assert.deepEqual(calls, [
    ["report", "APP-001", "APP_START_FAILED", false],
    ["fail", "APP_START_FAILED"],
  ]);
});
