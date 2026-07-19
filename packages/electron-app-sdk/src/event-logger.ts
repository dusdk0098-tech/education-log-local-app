import { z } from "zod"

const EventNameSchema = z
  .string()
  .regex(/^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$/)
  .max(100)
const AppIdSchema = z.string().regex(/^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/)
const InstanceIdSchema = z.uuid()

export type AppSdkEventLevel = "info" | "warn" | "error"
export type AppSdkEventField = string | number | boolean | null
export type AppSdkEvent = {
  readonly level: AppSdkEventLevel
  readonly name: string
  readonly occurredAt: string
  readonly appId: string
  readonly instanceId: string
  readonly fields: Readonly<Record<string, AppSdkEventField>>
}

export interface AppSdkEventSink {
  record(event: AppSdkEvent): void | Promise<void>
}

export class AppSdkEventLogger {
  private readonly appId: string
  private readonly instanceId: string
  private sinkHealthy = true

  constructor(
    identity: { readonly appId: string; readonly instanceId: string },
    private readonly sink?: AppSdkEventSink,
    private readonly now: () => Date = () => new Date(),
  ) {
    this.appId = AppIdSchema.parse(identity.appId)
    this.instanceId = InstanceIdSchema.parse(identity.instanceId)
  }

  get sinkAvailable(): boolean {
    return this.sinkHealthy
  }

  info(name: string, fields: Readonly<Record<string, unknown>> = {}): void {
    this.record("info", name, fields)
  }

  warn(name: string, fields: Readonly<Record<string, unknown>> = {}): void {
    this.record("warn", name, fields)
  }

  error(name: string, fields: Readonly<Record<string, unknown>> = {}): void {
    this.record("error", name, fields)
  }

  private record(
    level: AppSdkEventLevel,
    name: string,
    fields: Readonly<Record<string, unknown>>,
  ): void {
    if (this.sink === undefined) return
    const event: AppSdkEvent = {
      level,
      name: EventNameSchema.parse(name),
      occurredAt: this.now().toISOString(),
      appId: this.appId,
      instanceId: this.instanceId,
      fields: sanitizeFields(fields),
    }
    try {
      const result = this.sink.record(event)
      if (result instanceof Promise) {
        void result.catch(() => {
          this.sinkHealthy = false
        })
      }
    } catch {
      this.sinkHealthy = false
    }
  }
}

const BlockedFieldNames = [
  "token",
  "authorization",
  "cookie",
  "password",
  "secret",
  "email",
  "displayname",
  "userid",
  "workspaceid",
] as const

function sanitizeFields(
  input: Readonly<Record<string, unknown>>,
): Record<string, AppSdkEventField> {
  const fields: Record<string, AppSdkEventField> = {}
  for (const [key, value] of Object.entries(input)) {
    if (!isSafeFieldName(key) || !isEventField(value)) continue
    fields[key] = typeof value === "string" ? value.slice(0, 200) : value
  }
  return fields
}

function isSafeFieldName(value: string): boolean {
  if (value.length === 0 || value.length > 80 || !/^[A-Za-z][A-Za-z0-9_.-]*$/.test(value)) {
    return false
  }
  const normalized = value.toLowerCase().replaceAll(/[^a-z0-9]/g, "")
  return !BlockedFieldNames.some((blocked) => normalized.includes(blocked))
}

function isEventField(value: unknown): value is AppSdkEventField {
  return (
    value === null ||
    typeof value === "string" ||
    (typeof value === "number" && Number.isFinite(value)) ||
    typeof value === "boolean"
  )
}
