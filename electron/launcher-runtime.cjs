"use strict";

const path = require("node:path");

const APP_ID = "pedit-edu";
const RUN_SCOPE = `app:${APP_ID}:run`;
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const APP_ID_PATTERN = /^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/;
const SHA256_PATTERN = /^[a-f0-9]{64}$/;

function launcherArguments(argv) {
  const index = argv.indexOf("--app-id");
  return index < 0 ? [] : argv.slice(index);
}

function prepareLaunchEnvironment(options = {}) {
  const argv = options.argv || process.argv;
  const requiresLauncher = options.requiresLauncher === true;
  const args = launcherArguments(argv);
  if (args.length === 0) {
    return requiresLauncher
      ? restricted("LAUNCH_ARGUMENT_MISSING")
      : { status: { mode: "standalone" }, connection: null, arguments: [] };
  }
  try {
    const context = parseLaunchContext(args);
    if (context.appId !== APP_ID) return restricted("LAUNCH_APP_ID_MISMATCH");
    return { status: { mode: "pending" }, connection: null, context, arguments: args };
  } catch (error) {
    return restricted(errorCode(error));
  }
}

async function establishLauncherRuntime(options) {
  const { bootstrap } = options;
  if (bootstrap.status.mode !== "pending") return bootstrap;
  try {
    const sdk = await (options.loadSdk || (() => import("@pedit/electron-app-sdk")))();
    const context = sdk.parseLaunchContext(bootstrap.arguments);
    if (context.appId !== APP_ID) return restricted("LAUNCH_APP_ID_MISMATCH");
    if (!sameContext(context, bootstrap.context)) return restricted("LAUNCH_CONTEXT_CHANGED");
    let runtime;
    let failClosedTriggered = false;
    const triggerFailClosed = async (reason) => {
      if (failClosedTriggered) return;
      failClosedTriggered = true;
      await options.onFailClosed?.(reason);
    };
    const connection = await sdk.LauncherConnection.connect({
      context,
      appVersion: options.appVersion,
      dataSchemaVersion: options.dataSchemaVersion,
      packageHash: context.packageHash,
      onShutdown: options.onShutdown,
      eventSink: {
        record: (event) => {
          if (event.name === "app.shutdown.completed") {
            return options.onShutdownComplete?.();
          }
          if (event.level === "error" && event.name === "app.fail_closed") {
            const reason = typeof event.fields?.code === "string"
              ? event.fields.code
              : "LAUNCHER_CONNECTION_FAILED";
            return triggerFailClosed(reason);
          }
        }
      },
      onSessionRenewed: async (sessionContext) => {
        try {
          const renewedPermissionService = new sdk.AppPermissionService(sessionContext);
          renewedPermissionService.requireScope(RUN_SCOPE);
          if (runtime) runtime.permissionService = renewedPermissionService;
          await options.onSessionRenewed?.(sessionContext);
        } catch (error) {
          await triggerFailClosed(errorCode(error));
          throw error;
        }
      }
    });
    const permissionService = new sdk.AppPermissionService(connection.sessionContext);
    permissionService.requireScope(RUN_SCOPE);
    runtime = {
      status: { mode: "connected" },
      connection,
      context,
      dataDirectory: context.dataDirectory,
      permissionService
    };
    return runtime;
  } catch (error) {
    return restricted(errorCode(error));
  }
}

function parseLaunchContext(argv) {
  const values = new Map();
  if (argv.length % 2 !== 0) throw launchError("LAUNCH_ARGUMENT_INVALID");
  for (let index = 0; index < argv.length; index += 2) {
    const name = argv[index];
    const value = argv[index + 1];
    if (!name || value === undefined || !name.startsWith("--")) throw launchError("LAUNCH_ARGUMENT_INVALID");
    if (values.has(name)) throw launchError("LAUNCH_ARGUMENT_DUPLICATE");
    values.set(name, value);
  }
  const appId = required(values, "--app-id");
  const launcherPipe = required(values, "--launcher-pipe");
  const launchSessionId = required(values, "--launch-session-id");
  const instanceId = required(values, "--instance-id");
  const dataDirectory = path.win32.normalize(required(values, "--data-dir"));
  const packageHash = required(values, "--package-hash");
  if (!APP_ID_PATTERN.test(appId)) throw launchError("LAUNCH_APP_ID_INVALID");
  if (!launcherPipe.startsWith("\\\\.\\pipe\\PlatformLauncher-")) throw launchError("LAUNCH_PIPE_INVALID");
  if (!UUID_PATTERN.test(launchSessionId) || !UUID_PATTERN.test(instanceId)) throw launchError("LAUNCH_SESSION_ID_INVALID");
  if (!path.win32.isAbsolute(dataDirectory)) throw launchError("LAUNCH_DATA_DIR_INVALID");
  if (!SHA256_PATTERN.test(packageHash) || /^0{64}$/.test(packageHash)) throw launchError("LAUNCH_PACKAGE_HASH_INVALID");
  if (required(values, "--environment") !== "production") throw launchError("LAUNCH_ENVIRONMENT_INVALID");
  if (required(values, "--protocol-version") !== "2") throw launchError("LAUNCH_PROTOCOL_UNSUPPORTED");
  return { appId, launcherPipe, launchSessionId, instanceId, dataDirectory, packageHash };
}

function required(values, name) {
  const value = values.get(name);
  if (!value) throw launchError("LAUNCH_ARGUMENT_MISSING");
  return value;
}

function sameContext(left, right) {
  return ["appId", "launcherPipe", "launchSessionId", "instanceId", "dataDirectory", "packageHash"]
    .every((key) => left[key] === right[key]);
}

function restricted(reason) {
  return { status: { mode: "restricted", reason }, connection: null, arguments: [] };
}

function launchError(code) {
  const error = new Error(code);
  error.code = code;
  return error;
}

function errorCode(error) {
  if (error && typeof error.code === "string" && error.code.length > 0) return error.code;
  if (error instanceof Error && /^[A-Z][A-Z0-9_-]+$/.test(error.message)) return error.message;
  return "LAUNCHER_CONNECTION_FAILED";
}

module.exports = {
  APP_ID,
  RUN_SCOPE,
  establishLauncherRuntime,
  launcherArguments,
  parseLaunchContext,
  prepareLaunchEnvironment
};
