import { randomBytes, randomUUID } from "node:crypto"
import { execFile } from "node:child_process"
import { mkdtemp, readFile, readdir, rm } from "node:fs/promises"
import { createServer, type Server, type Socket } from "node:net"
import { tmpdir } from "node:os"
import path from "node:path"
import { promisify } from "node:util"
import { PackageInstaller } from "../../페딧 런처/src/main/apps/package-installer"
import { createAppProcessCommand } from "../../페딧 런처/src/main/apps/process-launcher"
import { type ManagedAppProcess, spawnManagedProcess } from "../../페딧 런처/src/main/apps/managed-process"
import { WindowsPackageExtractor } from "../../페딧 런처/src/main/apps/windows-package-extractor"
import {
  createLauncherShutdownMessage,
  JsonLinesDecoder,
  LauncherBootstrapSchema,
  LauncherSessionRenewedSchema,
  LauncherSessionSchema,
  parseAppMessage,
  type AppMessage,
  type LauncherMessage,
  verifyAppHelloProof,
} from "../../페딧 런처/src/main/pipe/protocol"
import { AppManifestSchema } from "../../페딧 런처/src/shared/contracts"

const execFileAsync = promisify(execFile)
const delay = (milliseconds: number) => new Promise((resolve) => setTimeout(resolve, milliseconds))
const MESSAGE_TIMEOUT_MS = 15_000

class RecordingProtocolV2Pipe {
  readonly observedTypes: string[] = []
  private readonly server: Server
  private socket: Socket | undefined
  private readonly messages: AppMessage[] = []
  private readonly waiters = new Set<() => void>()

  constructor(readonly pipePath: string) {
    this.server = createServer((socket) => this.attach(socket))
  }

  async listen(): Promise<void> {
    await new Promise<void>((resolve, reject) => {
      this.server.once("error", reject)
      this.server.listen(this.pipePath, () => {
        this.server.removeListener("error", reject)
        resolve()
      })
    })
  }

  async waitFor<T extends AppMessage["type"]>(type: T): Promise<Extract<AppMessage, { type: T }>> {
    const deadline = Date.now() + MESSAGE_TIMEOUT_MS
    while (Date.now() < deadline) {
      const index = this.messages.findIndex((message) => message.type === type)
      if (index >= 0) return this.messages.splice(index, 1)[0] as Extract<AppMessage, { type: T }>
      await new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(() => {
          this.waiters.delete(wake)
          reject(new Error(`PACKAGED_MESSAGE_TIMEOUT:${type}`))
        }, Math.max(1, deadline - Date.now()))
        const wake = () => {
          clearTimeout(timeout)
          this.waiters.delete(wake)
          resolve()
        }
        this.waiters.add(wake)
      })
    }
    throw new Error(`PACKAGED_MESSAGE_TIMEOUT:${type}`)
  }

  async waitForAny<T extends AppMessage["type"]>(types: readonly T[]): Promise<Extract<AppMessage, { type: T }>> {
    const deadline = Date.now() + MESSAGE_TIMEOUT_MS
    while (Date.now() < deadline) {
      const index = this.messages.findIndex((message) => types.includes(message.type as T))
      if (index >= 0) return this.messages.splice(index, 1)[0] as Extract<AppMessage, { type: T }>
      await new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(() => {
          this.waiters.delete(wake)
          reject(new Error(`PACKAGED_MESSAGE_TIMEOUT:${types.join("|")}:observed=${this.observedTypes.join(",")}`))
        }, Math.max(1, deadline - Date.now()))
        const wake = () => {
          clearTimeout(timeout)
          this.waiters.delete(wake)
          resolve()
        }
        this.waiters.add(wake)
      })
    }
    throw new Error(`PACKAGED_MESSAGE_TIMEOUT:${types.join("|")}:observed=${this.observedTypes.join(",")}`)
  }

  async send(message: LauncherMessage): Promise<void> {
    const socket = this.socket
    if (socket === undefined || socket.destroyed) throw new Error("PACKAGED_PIPE_NOT_CONNECTED")
    await new Promise<void>((resolve, reject) => {
      socket.write(`${JSON.stringify(message)}\n`, (error) => error ? reject(error) : resolve())
    })
  }

  async close(): Promise<void> {
    this.socket?.destroy()
    await new Promise<void>((resolve) => {
      if (!this.server.listening) return resolve()
      this.server.close(() => resolve())
    })
  }

  private attach(socket: Socket): void {
    if (this.socket !== undefined) {
      socket.destroy()
      return
    }
    this.socket = socket
    const decoder = new JsonLinesDecoder(64 * 1024)
    socket.on("data", (chunk) => {
      for (const raw of decoder.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk))) {
        const message = parseAppMessage(raw)
        this.observedTypes.push(message.type)
        this.messages.push(message)
        for (const wake of [...this.waiters]) wake()
      }
    })
  }
}

async function countExactProcesses(name: string, executablePath: string): Promise<number> {
  const { stdout } = await execFileAsync(
    "powershell.exe",
    [
      "-NoProfile",
      "-Command",
      "$n=$env:PEDIT_E2E_NAME;$p=$env:PEDIT_E2E_PATH; @(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq $n -and $_.ExecutablePath -eq $p }).Count",
    ],
    { env: { ...process.env, PEDIT_E2E_NAME: name, PEDIT_E2E_PATH: executablePath }, windowsHide: true },
  )
  return Number(stdout.trim())
}

async function waitForBackend(executablePath: string): Promise<void> {
  const deadline = Date.now() + 8_000
  while (Date.now() < deadline) {
    if (await countExactProcesses("PeditEduBackend.exe", executablePath) > 0) return
    await delay(100)
  }
  throw new Error("PACKAGED_BACKEND_NOT_STARTED")
}

async function containsSecret(root: string, secrets: readonly string[]): Promise<boolean> {
  const entries = await readdir(root, { withFileTypes: true })
  for (const entry of entries) {
    const candidate = path.join(root, entry.name)
    if (entry.isDirectory()) {
      if (await containsSecret(candidate, secrets)) return true
      continue
    }
    if (!entry.isFile()) continue
    const content = await readFile(candidate)
    if (secrets.some((secret) => content.includes(Buffer.from(secret)))) return true
  }
  return false
}

function guardedTemporaryPath(candidate: string): string {
  const resolved = path.resolve(candidate)
  if (!resolved.startsWith(path.resolve(tmpdir()) + path.sep)) {
    throw new Error("E2E_CLEANUP_GUARD_FAILED")
  }
  return resolved
}

async function removeTemporaryTree(candidate: string): Promise<void> {
  const guarded = guardedTemporaryPath(candidate)
  let lastError: unknown
  for (let attempt = 0; attempt < 4; attempt += 1) {
    try {
      await rm(guarded, { recursive: true, force: true, maxRetries: 2, retryDelay: 100 })
      return
    } catch (error) {
      lastError = error
      await delay(250)
    }
  }
  throw lastError
}

async function forceStopExactBackend(executablePath: string): Promise<void> {
  if (!executablePath) return
  await execFileAsync(
    "powershell.exe",
    [
      "-NoProfile",
      "-Command",
      "$target=$env:PEDIT_E2E_BACKEND; $items=Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'PeditEduBackend.exe' -and $_.ExecutablePath -eq $target }; foreach($item in $items){ Stop-Process -Id $item.ProcessId -Force -ErrorAction Stop; Wait-Process -Id $item.ProcessId -Timeout 5 -ErrorAction SilentlyContinue }; if(@(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'PeditEduBackend.exe' -and $_.ExecutablePath -eq $target }).Count -ne 0){ exit 23 }",
    ],
    { env: { ...process.env, PEDIT_E2E_BACKEND: executablePath }, windowsHide: true },
  )
}

async function main() {
  const packageFile = path.resolve(required("PEDIT_EDU_PACKAGE"))
  const manifestPath = path.resolve(required("PEDIT_EDU_MANIFEST"))
  const manifest = AppManifestSchema.parse(JSON.parse(await readFile(manifestPath, "utf8")))
  const appsRoot = await mkdtemp(path.join(tmpdir(), "pedit-edu-install-"))
  const dataDirectory = await mkdtemp(path.join(tmpdir(), "pedit-edu-data-"))
  const launchSessionId = randomUUID()
  const instanceId = randomUUID()
  const bootstrapSecret = randomBytes(32).toString("base64url")
  const initialToken = "pedit-edu-e2e-initial-token-never-persist"
  const renewedToken = "pedit-edu-e2e-renewed-token-never-persist"
  const pipe = new RecordingProtocolV2Pipe(`\\\\.\\pipe\\PlatformLauncher-${launchSessionId}`)
  const installer = new PackageInstaller({
    extractor: new WindowsPackageExtractor(),
    signatureVerifier: { verifyExecutable: () => Promise.resolve() },
  })
  let process: ManagedAppProcess | undefined
  let backendExecutable = ""
  let entryExecutable = ""
  let primaryError: unknown
  let cleanupError: unknown

  try {
    const installed = await installer.install({
      manifest,
      releaseManifestJws: "synthetic-e2e-jws-not-a-secret",
      packageFile,
      appsRoot,
    })
    backendExecutable = path.join(installed.installDirectory, "resources", "backend", "PeditEduBackend.exe")
    entryExecutable = path.join(installed.installDirectory, manifest.entryPoint)
    await pipe.listen()
    process = await spawnManagedProcess(createAppProcessCommand({
      manifest,
      installDirectory: installed.installDirectory,
      dataDirectory,
      launcherPipe: pipe.pipePath,
      launchSessionId,
      instanceId,
    }))

    const appBootstrap = await pipe.waitFor("app.bootstrap")
    if (appBootstrap.instanceId !== instanceId || appBootstrap.payload.pid !== process.pid) {
      throw new Error("PACKAGED_BOOTSTRAP_BINDING_INVALID")
    }
    await pipe.send(LauncherBootstrapSchema.parse({
      messageId: randomUUID(),
      type: "launcher.bootstrap",
      protocolVersion: 2,
      timestamp: new Date().toISOString(),
      instanceId,
      payload: { launchSessionId, bootstrapSecret },
    }))

    const hello = await pipe.waitFor("app.hello")
    if (!verifyAppHelloProof(bootstrapSecret, {
      launchSessionId,
      instanceId,
      appId: hello.payload.appId,
      appVersion: hello.payload.appVersion,
      dataSchemaVersion: hello.payload.dataSchemaVersion,
      pid: hello.payload.pid,
      packageHash: hello.payload.packageHash,
    }, hello.payload.proof)) throw new Error("PACKAGED_HELLO_PROOF_INVALID")

    await pipe.send(LauncherSessionSchema.parse({
      messageId: randomUUID(),
      type: "launcher.session",
      protocolVersion: 2,
      timestamp: new Date().toISOString(),
      instanceId,
      payload: {
        launchSessionId,
        appSessionToken: initialToken,
        expiresAt: new Date(Date.now() + 61_000).toISOString(),
        userId: "pedit-edu-e2e-user",
        workspaceId: "pedit-edu-e2e-workspace",
        roles: ["member"],
        scopes: ["app:pedit-edu:run"],
      },
    }))

    const startup = await Promise.race([
      pipe.waitForAny(["app.ready", "app.error"] as const),
      process.exited.then((exit) => {
        throw new Error(`PACKAGED_EXIT_BEFORE_READY:${exit.kind}:observed=${pipe.observedTypes.join(",")}`)
      }),
    ])
    if (startup.type === "app.error") {
      throw new Error(`PACKAGED_APP_ERROR_BEFORE_READY:${startup.payload.code}:${startup.payload.message}`)
    }
    const ready = startup
    if (!ready.payload.databaseReady || !ready.payload.rendererReady || !ready.payload.windowReady) {
      throw new Error("PACKAGED_READY_CHECK_FAILED")
    }
    await waitForBackend(backendExecutable)
    const firstHeartbeat = await pipe.waitFor("app.heartbeat")

    await pipe.send(LauncherSessionRenewedSchema.parse({
      messageId: randomUUID(),
      type: "launcher.session-renewed",
      protocolVersion: 2,
      timestamp: new Date().toISOString(),
      instanceId,
      payload: {
        launchSessionId,
        appSessionToken: renewedToken,
        expiresAt: new Date(Date.now() + 5 * 60_000).toISOString(),
        roles: ["member"],
        scopes: ["app:pedit-edu:run"],
      },
    }))
    const secondHeartbeat = await pipe.waitFor("app.heartbeat")
    if (secondHeartbeat.payload.sequence <= firstHeartbeat.payload.sequence) {
      throw new Error("PACKAGED_HEARTBEAT_SEQUENCE_INVALID")
    }

    await pipe.send(createLauncherShutdownMessage(instanceId, "E2E_COMPLETE"))
    const stopping = await pipe.waitFor("app.stopping")
    const stopped = await pipe.waitFor("app.stopped")
    const exit = await Promise.race([
      process.exited,
      delay(12_000).then(() => { throw new Error("PACKAGED_SHUTDOWN_TIMEOUT") }),
    ])
    await delay(300)

    if (stopping.payload.reason !== "E2E_COMPLETE" || stopped.payload.exitCode !== 0) {
      throw new Error("PACKAGED_STOP_MESSAGES_INVALID")
    }
    if (exit.kind === "failed") throw new Error(`PACKAGED_PROCESS_FAILED:${exit.error.name}`)
    if (await countExactProcesses("PeditEdu.exe", entryExecutable) !== 0) {
      throw new Error("PACKAGED_ELECTRON_NOT_STOPPED")
    }
    if (await countExactProcesses("PeditEduBackend.exe", backendExecutable) !== 0) {
      throw new Error("PACKAGED_BACKEND_NOT_STOPPED")
    }
    if (await containsSecret(dataDirectory, [initialToken, renewedToken, bootstrapSecret])) {
      throw new Error("PACKAGED_TOKEN_PERSISTED")
    }

    console.log(JSON.stringify({
      status: "ready",
      appId: manifest.appId,
      protocolVersion: manifest.protocolVersion,
      installedFromReleaseZip: true,
      handshake: ["app.bootstrap", "app.hello"],
      ready: true,
      heartbeats: [firstHeartbeat.payload.sequence, secondHeartbeat.payload.sequence],
      sessionRenewed: true,
      lifecycle: [stopping.type, stopped.type],
      appExitKind: exit.kind,
      backendStopException: null,
      electronProcesses: 0,
      backendProcesses: 0,
      tokenPersisted: false,
    }))
  } catch (error) {
    primaryError = error
    throw error
  } finally {
    process?.forceStop()
    if (process !== undefined) {
      await Promise.race([process.exited.catch(() => undefined), delay(3_000)])
    }
    await forceStopExactBackend(backendExecutable).catch((error) => { cleanupError ??= error })
    await pipe.close().catch((error) => { cleanupError ??= error })
    await removeTemporaryTree(appsRoot).catch((error) => { cleanupError ??= error })
    await removeTemporaryTree(dataDirectory).catch((error) => { cleanupError ??= error })
    if (primaryError === undefined && cleanupError !== undefined) throw cleanupError
  }
}

function required(name: string): string {
  const value = process.env[name]
  if (!value) throw new Error(`E2E_ENVIRONMENT_MISSING:${name}`)
  return value
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : "PACKAGED_PROTOCOL_V2_E2E_FAILED")
  process.exitCode = 1
})
