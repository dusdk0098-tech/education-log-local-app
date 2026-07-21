import { randomUUID } from "node:crypto"
import { execFile } from "node:child_process"
import { mkdtemp, readFile, rm } from "node:fs/promises"
import { tmpdir } from "node:os"
import path from "node:path"
import { promisify } from "node:util"
import {
  AppLaunchCoordinator,
  type AppSessionIssueRequest,
  type AppSessionIssuer,
  type RunningApp,
} from "../../../페딧 런처/src/main/apps/app-launch-coordinator"
import { AuthenticodeVerifier } from "../../../페딧 런처/src/main/apps/authenticode-verifier"
import { spawnManagedProcess } from "../../../페딧 런처/src/main/apps/managed-process"
import { PackageInstaller } from "../../../페딧 런처/src/main/apps/package-installer"
import { verifyReleaseManifestWithScopedKeyRing } from "../../../페딧 런처/src/main/apps/release-manifest-verifier"
import { WindowsPackageExtractor } from "../../../페딧 런처/src/main/apps/windows-package-extractor"
import { LauncherSessionRenewedSchema, LauncherSessionSchema } from "../../../페딧 런처/src/main/pipe/protocol"
import { startSecureLauncherPipeServer } from "../../../페딧 런처/src/main/pipe/secure-broker"
import { AppManifestSchema } from "../../../페딧 런처/src/shared/contracts"

const execFileAsync = promisify(execFile)
const delay = (milliseconds: number) => new Promise((resolve) => setTimeout(resolve, milliseconds))
const signer = {
  appId: "pedit-edu",
  subject: "CN=PEDIT EDU PEDIT-20260721-017 Authenticode",
  thumbprint: "59CF023FA686F6B1FB7CFD35DD5BAAD53088181D",
} as const
const publicJwk = {
  kty: "EC",
  crv: "P-256",
  x: "rzQlaNwnkyvdG9Swfe7FH-huxML4niZumolNVVR0wb8",
  y: "ZOEb8fZ43Vjy6sw-yIEIhqeyyplr8tWFl6yHw-zDXUo",
  kid: "pedit-edu-pedit-20260721-017-es256",
  alg: "ES256",
  use: "sig",
} as const

async function main() {
  const packageFile = path.resolve(required("PEDIT_EDU_PACKAGE"))
  const manifestBytes = await readFile(path.resolve(required("PEDIT_EDU_MANIFEST")))
  const releaseManifestJws = await readFile(path.resolve(required("PEDIT_EDU_MANIFEST_JWS")), "utf8")
  const launcherRoot = path.resolve(required("PEDIT_LAUNCHER_ROOT"))
  const brokerExecutable = path.join(launcherRoot, "resources", "native", "PeditPipeBroker.exe")
  const manifest = AppManifestSchema.parse(JSON.parse(manifestBytes.toString("utf8")))
  const signedManifest = await verifyReleaseManifestWithScopedKeyRing(
    releaseManifestJws,
    [],
    [{ appId: signer.appId, publicJwk }],
  )
  if (JSON.stringify(signedManifest) !== JSON.stringify(manifest)) throw new Error("SIGNED_MANIFEST_MISMATCH")

  const appsRoot = await mkdtemp(path.join(tmpdir(), "pedit-edu-beta7-install-"))
  const dataDirectory = await mkdtemp(path.join(tmpdir(), "pedit-edu-beta7-data-"))
  const sessionIssuer = new SyntheticSessionIssuer()
  let running: RunningApp | null = null
  try {
    const installed = await new PackageInstaller({
      extractor: new WindowsPackageExtractor(),
      signatureVerifier: new AuthenticodeVerifier([signer.thumbprint], undefined, { kind: "public-beta-thumbprint" }, [signer]),
    }).install({ manifest, releaseManifestJws, packageFile, appsRoot })
    const coordinator = new AppLaunchCoordinator({
      sessionIssuer,
      pipeFactory: { start: (options) => startSecureLauncherPipeServer(brokerExecutable, options) },
      spawner: { spawn: spawnManagedProcess },
    })
    running = await coordinator.launch({ manifest, installDirectory: installed.installDirectory, dataDirectory })
    const readyAt = Date.now()
    await Promise.race([
      delay(20_500),
      running.exited.then((exit) => { throw new Error(`BETA7_EXIT_DURING_READY:${exit.kind}`) }),
    ])
    const alive = await processCounts()
    if (sessionIssuer.heartbeatCalls < 4 || sessionIssuer.renewCalls < 1) throw new Error("BETA7_SESSION_LIFECYCLE_INCOMPLETE")
    if (alive.electron < 1 || alive.backend < 1 || alive.broker < 1) throw new Error("BETA7_PROCESS_NOT_ALIVE")

    running.requestStop()
    const exit = await Promise.race([
      running.exited,
      delay(12_000).then(() => { throw new Error("BETA7_SHUTDOWN_TIMEOUT") }),
    ])
    await delay(500)
    const stopped = await processCounts()
    if (exit.kind !== "exited" || sessionIssuer.endCalls < 1) throw new Error("BETA7_NORMAL_EXIT_INVALID")
    if (stopped.electron !== 0 || stopped.backend !== 0 || stopped.broker !== 0) throw new Error("BETA7_ORPHAN_PROCESS")
    console.log(JSON.stringify({
      status: "ready",
      launcherSource: "4a1bc3f47332193f99604cc42df575c9dcc0791b",
      readySurvivalMs: Date.now() - readyAt,
      heartbeatCalls: sessionIssuer.heartbeatCalls,
      sessionRenewed: sessionIssuer.renewCalls >= 1,
      alive,
      exitKind: exit.kind,
      orphanCounts: stopped,
    }))
  } finally {
    running?.forceStop()
    if (running !== null) await Promise.race([running.exited.catch(() => undefined), delay(3_000)])
    await rm(dataDirectory, { recursive: true, force: true, maxRetries: 10, retryDelay: 200 })
    await rm(appsRoot, { recursive: true, force: true, maxRetries: 10, retryDelay: 200 })
  }
}

class SyntheticSessionIssuer implements AppSessionIssuer {
  renewCalls = 0
  heartbeatCalls = 0
  endCalls = 0
  issue(request: AppSessionIssueRequest) {
    return Promise.resolve(LauncherSessionSchema.parse({
      messageId: randomUUID(), type: "launcher.session", protocolVersion: 2,
      timestamp: new Date().toISOString(), instanceId: request.instanceId,
      payload: {
        launchSessionId: request.launchSessionId, appSessionToken: "synthetic-beta7-session-token-for-test-only",
        expiresAt: new Date(Date.now() + 61_000).toISOString(), userId: "synthetic-user",
        workspaceId: "synthetic-workspace", roles: ["member"], scopes: ["app:pedit-edu:run"],
      },
    }))
  }
  renew(request: AppSessionIssueRequest) {
    this.renewCalls += 1
    return Promise.resolve(LauncherSessionRenewedSchema.parse({
      messageId: randomUUID(), type: "launcher.session-renewed", protocolVersion: 2,
      timestamp: new Date().toISOString(), instanceId: request.instanceId,
      payload: {
        launchSessionId: request.launchSessionId, appSessionToken: "synthetic-beta7-renewed-session-token-for-test-only",
        expiresAt: new Date(Date.now() + 5 * 60_000).toISOString(), roles: ["member"],
        scopes: ["app:pedit-edu:run"],
      },
    }))
  }
  heartbeat() { this.heartbeatCalls += 1; return Promise.resolve() }
  end() { this.endCalls += 1; return Promise.resolve() }
}

async function processCounts() {
  const { stdout } = await execFileAsync("powershell.exe", ["-NoProfile", "-Command", [
    "$names=@('PeditEdu','PeditEduBackend','PeditPipeBroker')",
    "$counts=@{}",
    "foreach($name in $names){$counts[$name]=@(Get-Process -Name $name -ErrorAction SilentlyContinue).Count}",
    "$counts|ConvertTo-Json -Compress",
  ].join(";")], { windowsHide: true })
  const counts = JSON.parse(stdout) as Record<string, number>
  return { electron: counts.PeditEdu ?? 0, backend: counts.PeditEduBackend ?? 0, broker: counts.PeditPipeBroker ?? 0 }
}

function required(name: string) {
  const value = process.env[name]
  if (!value) throw new Error(`E2E_ENVIRONMENT_MISSING:${name}`)
  return value
}

main().catch((error) => {
  if (error instanceof Error) {
    const cause = "cause" in error && error.cause instanceof Error ? error.cause : null
    console.error(JSON.stringify({
      name: error.name,
      code: "code" in error && typeof error.code === "string" ? error.code : null,
      stage: "stage" in error && typeof error.stage === "string" ? error.stage : null,
      causeName: cause?.name ?? null,
      causeCode: cause && "code" in cause && typeof cause.code === "string" ? cause.code : null,
      causeIssues: cause && "issues" in cause && Array.isArray(cause.issues)
        ? cause.issues.map((issue) => ({ code: issue.code, path: issue.path }))
        : [],
    }))
  } else console.error("BETA7_PACKAGED_LIFECYCLE_FAILED")
  process.exitCode = 1
})
