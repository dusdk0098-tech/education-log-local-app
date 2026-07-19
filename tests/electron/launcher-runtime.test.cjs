const assert = require("node:assert/strict");
const test = require("node:test");

const {
  APP_ID,
  RUN_SCOPE,
  establishLauncherRuntime,
  prepareLaunchEnvironment
} = require("../../electron/launcher-runtime.cjs");

const UUID_A = "11111111-1111-4111-8111-111111111111";
const UUID_B = "22222222-2222-4222-8222-222222222222";

function validArgs() {
  return [
    "PeditEdu.exe",
    "--app-id", "pedit-edu",
    "--launcher-pipe", "\\\\.\\pipe\\PlatformLauncher-session",
    "--launch-session-id", UUID_A,
    "--instance-id", UUID_B,
    "--data-dir", "C:\\PEDIT\\data\\pedit-edu",
    "--package-hash", "a".repeat(64),
    "--environment", "production",
    "--protocol-version", "2"
  ];
}

test("packaged direct run is fail-closed", () => {
  const result = prepareLaunchEnvironment({ argv: ["PeditEdu.exe"], requiresLauncher: true });
  assert.deepEqual(result.status, { mode: "restricted", reason: "LAUNCH_ARGUMENT_MISSING" });
});

test("valid Protocol v2 arguments create only a pending context", () => {
  const environment = {};
  const result = prepareLaunchEnvironment({ argv: validArgs(), environment, requiresLauncher: true });
  assert.equal(APP_ID, "pedit-edu");
  assert.equal(RUN_SCOPE, "app:pedit-edu:run");
  assert.equal(result.status.mode, "pending");
  assert.equal(result.context.dataDirectory, "C:\\PEDIT\\data\\pedit-edu");
  assert.equal(Object.values(environment).some((value) => String(value).includes("token")), false);
});

test("SDK connection requires the PEDIT EDU run scope", async () => {
  const bootstrap = prepareLaunchEnvironment({ argv: validArgs(), requiresLauncher: true });
  let requiredScope = "";
  class PermissionService {
    constructor(context) {
      this.context = context;
    }
    requireScope(scope) {
      requiredScope = scope;
      if (!this.context.scopes.includes(scope)) throw Object.assign(new Error("APP_SCOPE_REQUIRED"), { code: "APP_SCOPE_REQUIRED" });
    }
  }
  const sdk = {
    parseLaunchContext: () => bootstrap.context,
    AppPermissionService: PermissionService,
    LauncherConnection: {
      connect: async () => ({
        sessionContext: {
          userId: "user-1",
          workspaceId: "workspace-1",
          roles: [],
          scopes: ["app:pedit-edu:run"],
          expiresAt: "2026-07-20T00:00:00.000Z"
        }
      })
    }
  };

  const runtime = await establishLauncherRuntime({
    bootstrap,
    appVersion: "1.0.4",
    dataSchemaVersion: 1,
    loadSdk: async () => sdk
  });

  assert.equal(runtime.status.mode, "connected");
  assert.equal(requiredScope, "app:pedit-edu:run");
});

test("scope loss during session renewal invokes fail-closed callback", async () => {
  const bootstrap = prepareLaunchEnvironment({ argv: validArgs(), requiresLauncher: true });
  let renewalHandler;
  let failClosedReason = "";
  class PermissionService {
    constructor(context) {
      this.context = context;
    }
    requireScope(scope) {
      if (!this.context.scopes.includes(scope)) throw Object.assign(new Error("APP_SCOPE_REQUIRED"), { code: "APP_SCOPE_REQUIRED" });
    }
  }
  const sdk = {
    parseLaunchContext: () => bootstrap.context,
    AppPermissionService: PermissionService,
    LauncherConnection: {
      connect: async (options) => {
        renewalHandler = options.onSessionRenewed;
        return {
          sessionContext: {
            userId: "user-1",
            workspaceId: "workspace-1",
            roles: [],
            scopes: ["app:pedit-edu:run"],
            expiresAt: "2026-07-20T00:00:00.000Z"
          }
        };
      }
    }
  };
  await establishLauncherRuntime({
    bootstrap,
    appVersion: "1.0.4",
    dataSchemaVersion: 1,
    loadSdk: async () => sdk,
    onFailClosed: async (reason) => {
      failClosedReason = reason;
    }
  });

  await assert.rejects(
    renewalHandler({
      userId: "user-1",
      workspaceId: "workspace-1",
      roles: [],
      scopes: [],
      expiresAt: "2026-07-20T00:00:00.000Z"
    }),
    /APP_SCOPE_REQUIRED/
  );
  assert.equal(failClosedReason, "APP_SCOPE_REQUIRED");
});

test("heartbeat write failure event closes the application boundary", async () => {
  const bootstrap = prepareLaunchEnvironment({ argv: validArgs(), requiresLauncher: true });
  let eventSink;
  const failClosedReasons = [];
  class PermissionService {
    constructor(context) {
      this.context = context;
    }
    requireScope(scope) {
      if (!this.context.scopes.includes(scope)) throw new Error("APP_SCOPE_REQUIRED");
    }
  }
  const sdk = {
    parseLaunchContext: () => bootstrap.context,
    AppPermissionService: PermissionService,
    LauncherConnection: {
      connect: async (options) => {
        eventSink = options.eventSink;
        return {
          sessionContext: {
            userId: "user-1",
            workspaceId: "workspace-1",
            roles: [],
            scopes: ["app:pedit-edu:run"],
            expiresAt: "2026-07-20T00:00:00.000Z"
          }
        };
      }
    }
  };

  const runtime = await establishLauncherRuntime({
    bootstrap,
    appVersion: "1.0.4",
    dataSchemaVersion: 1,
    loadSdk: async () => sdk,
    onFailClosed: async (reason) => {
      failClosedReasons.push(reason);
    }
  });

  assert.equal(runtime.status.mode, "connected");
  await eventSink.record({
    level: "error",
    name: "app.fail_closed",
    fields: { code: "APP_HEARTBEAT_WRITE_FAILED" }
  });
  assert.deepEqual(failClosedReasons, ["APP_HEARTBEAT_WRITE_FAILED"]);
});

test("Electron quit boundary runs only after the SDK reports stopped flush completion", async () => {
  const bootstrap = prepareLaunchEnvironment({ argv: validArgs(), requiresLauncher: true });
  let eventSink;
  let completionCount = 0;
  class PermissionService {
    constructor(context) {
      this.context = context;
    }
    requireScope(scope) {
      if (!this.context.scopes.includes(scope)) throw new Error("APP_SCOPE_REQUIRED");
    }
  }
  const sdk = {
    parseLaunchContext: () => bootstrap.context,
    AppPermissionService: PermissionService,
    LauncherConnection: {
      connect: async (options) => {
        eventSink = options.eventSink;
        return {
          sessionContext: {
            userId: "user-1",
            workspaceId: "workspace-1",
            roles: [],
            scopes: ["app:pedit-edu:run"],
            expiresAt: "2026-07-20T00:00:00.000Z"
          }
        };
      }
    }
  };

  const runtime = await establishLauncherRuntime({
    bootstrap,
    appVersion: "1.0.4",
    dataSchemaVersion: 1,
    loadSdk: async () => sdk,
    onShutdownComplete: () => {
      completionCount += 1;
    }
  });

  assert.equal(runtime.status.mode, "connected");
  assert.equal(completionCount, 0);
  eventSink.record({ level: "info", name: "app.shutdown.started", fields: {} });
  assert.equal(completionCount, 0);
  eventSink.record({ level: "info", name: "app.shutdown.completed", fields: {} });
  assert.equal(completionCount, 1);
});
