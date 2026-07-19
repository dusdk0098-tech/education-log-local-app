import path from "node:path"

export type LaunchContext = {
  readonly appId: string
  readonly launcherPipe: string
  readonly launchSessionId: string
  readonly instanceId: string
  readonly dataDirectory: string
  readonly packageHash: string
}

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
const APP_ID_PATTERN = /^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/
const SHA256_PATTERN = /^[a-f0-9]{64}$/

export function parseLaunchContext(argv: readonly string[]): LaunchContext {
  const values = new Map<string, string>()
  for (let index = 0; index < argv.length; index += 2) {
    const name = argv[index]
    const value = argv[index + 1]
    if (name === undefined || value === undefined || !name.startsWith("--")) {
      throw new LaunchContextError("LAUNCH_ARGUMENT_INVALID")
    }
    if (values.has(name)) throw new LaunchContextError("LAUNCH_ARGUMENT_DUPLICATE")
    values.set(name, value)
  }
  const appId = required(values, "--app-id")
  const launcherPipe = required(values, "--launcher-pipe")
  const launchSessionId = required(values, "--launch-session-id")
  const instanceId = required(values, "--instance-id")
  const dataDirectory = required(values, "--data-dir")
  const packageHash = required(values, "--package-hash")
  if (!APP_ID_PATTERN.test(appId)) throw new LaunchContextError("LAUNCH_APP_ID_INVALID")
  if (!launcherPipe.startsWith("\\\\.\\pipe\\PlatformLauncher-")) {
    throw new LaunchContextError("LAUNCH_PIPE_INVALID")
  }
  if (!UUID_PATTERN.test(launchSessionId) || !UUID_PATTERN.test(instanceId)) {
    throw new LaunchContextError("LAUNCH_SESSION_ID_INVALID")
  }
  if (!path.win32.isAbsolute(dataDirectory)) throw new LaunchContextError("LAUNCH_DATA_DIR_INVALID")
  if (!SHA256_PATTERN.test(packageHash) || /^0{64}$/.test(packageHash)) {
    throw new LaunchContextError("LAUNCH_PACKAGE_HASH_INVALID")
  }
  if (required(values, "--environment") !== "production") {
    throw new LaunchContextError("LAUNCH_ENVIRONMENT_INVALID")
  }
  if (required(values, "--protocol-version") !== "2") {
    throw new LaunchContextError("LAUNCH_PROTOCOL_UNSUPPORTED")
  }
  return { appId, launcherPipe, launchSessionId, instanceId, dataDirectory, packageHash }
}

function required(values: ReadonlyMap<string, string>, name: string): string {
  const value = values.get(name)
  if (value === undefined || value.length === 0)
    throw new LaunchContextError("LAUNCH_ARGUMENT_MISSING")
  return value
}

export class LaunchContextError extends Error {
  readonly name = "LaunchContextError"
  constructor(readonly code: string) {
    super(code)
  }
}
