"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const { shutdownApplication } = require("../../electron/app-shutdown.cjs");

test("launcher shutdown waits for backend stop and returns before the SDK completion event", async () => {
  const calls = [];
  let releaseBackend;
  const backendStopped = new Promise((resolve) => {
    releaseBackend = resolve;
  });

  const shutdown = shutdownApplication({
    closeBusinessSurface: async () => calls.push("surface.closed"),
    stopBackend: async () => {
      calls.push("backend.stop.started");
      await backendStopped;
      calls.push("backend.stop.completed");
    },
  });

  await new Promise((resolve) => setImmediate(resolve));
  assert.deepEqual(calls, ["surface.closed", "backend.stop.started"]);

  releaseBackend();
  await shutdown;
  assert.deepEqual(calls, [
    "surface.closed",
    "backend.stop.started",
    "backend.stop.completed",
  ]);
});

test("launcher shutdown rejects when backend stop cannot be confirmed", async () => {
  await assert.rejects(
    shutdownApplication({
      closeBusinessSurface: async () => {},
      stopBackend: async () => {
        throw new Error("BACKEND_STOP_TIMEOUT");
      },
    }),
    /BACKEND_STOP_TIMEOUT/,
  );
});
