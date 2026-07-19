import { createHmac, randomUUID } from "node:crypto"
import { z } from "zod"

export const PEDIT_APP_PROTOCOL_VERSION = 2 as const

const EnvelopeShape = {
  messageId: z.uuid(),
  protocolVersion: z.literal(PEDIT_APP_PROTOCOL_VERSION),
  timestamp: z.iso.datetime(),
  instanceId: z.uuid(),
}

const AppIdentityShape = {
  launchSessionId: z.uuid(),
  appId: z.string().regex(/^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/),
  appVersion: z.string().regex(/^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$/),
  dataSchemaVersion: z.number().int().positive(),
  pid: z.number().int().positive(),
  packageHash: z.string().regex(/^[a-f0-9]{64}$/),
}

export const AppBootstrapSchema = z.strictObject({
  ...EnvelopeShape,
  type: z.literal("app.bootstrap"),
  payload: z.strictObject(AppIdentityShape),
})

export const AppHelloSchema = z.strictObject({
  ...EnvelopeShape,
  type: z.literal("app.hello"),
  payload: z.strictObject({
    ...AppIdentityShape,
    proof: z.string().regex(/^[A-Za-z0-9_-]{43}$/),
  }),
})

export const AppReadySchema = z.strictObject({
  ...EnvelopeShape,
  type: z.literal("app.ready"),
  payload: z.strictObject({
    databaseReady: z.boolean(),
    rendererReady: z.boolean(),
    windowReady: z.boolean(),
  }),
})

export const AppHeartbeatSchema = z.strictObject({
  ...EnvelopeShape,
  type: z.literal("app.heartbeat"),
  payload: z.strictObject({ sequence: z.number().int().nonnegative() }),
})

export const AppErrorSchema = z.strictObject({
  ...EnvelopeShape,
  type: z.literal("app.error"),
  payload: z.strictObject({
    code: z.string().regex(/^[A-Z]+-\d{3}$/),
    message: z.string().min(1).max(500),
    recoverable: z.boolean(),
  }),
})

export const AppStoppingSchema = z.strictObject({
  ...EnvelopeShape,
  type: z.literal("app.stopping"),
  payload: z.strictObject({ reason: z.string().min(1).max(200) }),
})

export const AppStoppedSchema = z.strictObject({
  ...EnvelopeShape,
  type: z.literal("app.stopped"),
  payload: z.strictObject({ exitCode: z.number().int().nullable() }),
})

export const AppMessageSchema = z.discriminatedUnion("type", [
  AppBootstrapSchema,
  AppHelloSchema,
  AppReadySchema,
  AppHeartbeatSchema,
  AppErrorSchema,
  AppStoppingSchema,
  AppStoppedSchema,
])
export type AppMessage = z.infer<typeof AppMessageSchema>

export const LauncherBootstrapSchema = z.strictObject({
  ...EnvelopeShape,
  type: z.literal("launcher.bootstrap"),
  payload: z.strictObject({
    launchSessionId: z.uuid(),
    bootstrapSecret: z.string().regex(/^[A-Za-z0-9_-]{43}$/),
  }),
})

export const LauncherSessionSchema = z.strictObject({
  ...EnvelopeShape,
  type: z.literal("launcher.session"),
  payload: z.strictObject({
    launchSessionId: z.uuid(),
    appSessionToken: z.string().min(32),
    expiresAt: z.iso.datetime(),
    userId: z.string().min(1),
    workspaceId: z.string().min(1),
    roles: z.array(z.string()),
    scopes: z.array(z.string()),
    deviceId: z.uuid().optional(),
    dataScopeId: z.uuid().optional(),
  }),
})

export const LauncherSessionRenewedSchema = z.strictObject({
  ...EnvelopeShape,
  type: z.literal("launcher.session-renewed"),
  payload: z.strictObject({
    launchSessionId: z.uuid(),
    appSessionToken: z.string().min(32),
    expiresAt: z.iso.datetime(),
    roles: z.array(z.string()),
    scopes: z.array(z.string()),
    deviceId: z.uuid().optional(),
    dataScopeId: z.uuid().optional(),
  }),
})

export const LauncherShutdownSchema = z.strictObject({
  ...EnvelopeShape,
  type: z.literal("launcher.shutdown"),
  payload: z.strictObject({ reason: z.string().min(1).max(200) }),
})

export const LauncherMessageSchema = z.discriminatedUnion("type", [
  LauncherBootstrapSchema,
  LauncherSessionSchema,
  LauncherSessionRenewedSchema,
  LauncherShutdownSchema,
])
export type LauncherSession = z.infer<typeof LauncherSessionSchema>
export type LauncherSessionRenewed = z.infer<typeof LauncherSessionRenewedSchema>
export type LauncherBootstrap = z.infer<typeof LauncherBootstrapSchema>

export function createEnvelope(instanceId: string, type: string, payload: object) {
  return {
    messageId: randomUUID(),
    type,
    protocolVersion: PEDIT_APP_PROTOCOL_VERSION,
    timestamp: new Date().toISOString(),
    instanceId,
    payload,
  }
}

export function createHelloProof(
  secret: string,
  input: {
    readonly launchSessionId: string
    readonly instanceId: string
    readonly appId: string
    readonly appVersion: string
    readonly dataSchemaVersion: number
    readonly pid: number
    readonly packageHash: string
  },
): string {
  const canonical = JSON.stringify([
    input.launchSessionId,
    input.instanceId,
    input.appId,
    input.appVersion,
    input.dataSchemaVersion,
    input.pid,
    input.packageHash,
  ])
  return createHmac("sha256", secret).update(canonical, "utf8").digest("base64url")
}
