"use strict";

const assert = require("node:assert/strict");
const { EventEmitter } = require("node:events");
const test = require("node:test");

test("unexpected launcher pipe close fails closed immediately", async () => {
  const { LauncherConnection } = await import("../../packages/electron-app-sdk/dist/launcher-connection.js");
  const socket = new EventEmitter();
  socket.write = (_message, callback) => callback(new Error("PIPE_CLOSED"));
  socket.destroy = () => {};
  const events = [];
  const context = {
    appId: "pedit-edu",
    launcherPipe: "\\\\.\\pipe\\PlatformLauncher-test",
    launchSessionId: "11111111-1111-4111-8111-111111111111",
    instanceId: "22222222-2222-4222-8222-222222222222",
    dataDirectory: "C:\\PEDIT\\data\\pedit-edu",
    packageHash: "a".repeat(64)
  };
  const session = {
    payload: {
      appSessionToken: "in-memory-test-value",
      userId: "test-user",
      workspaceId: "test-workspace",
      roles: [],
      scopes: ["app:pedit-edu:run"],
      expiresAt: "2026-07-21T12:00:00.000Z"
    }
  };
  const connection = new LauncherConnection(
    socket,
    context,
    session,
    { onShutdown: async () => {} },
    { validate: () => {} },
    { error: (name, fields) => events.push({ name, fields }) }
  );

  connection.listenForRuntimeMessages();
  socket.emit("close");
  assert.deepEqual(events, [{ name: "app.fail_closed", fields: { code: "LAUNCHER_PIPE_CLOSED" } }]);
});
