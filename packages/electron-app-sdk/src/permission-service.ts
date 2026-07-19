import { z } from "zod"
import type { AppSessionContext } from "./launcher-connection.js"

const PermissionNameSchema = z
  .string()
  .trim()
  .min(1)
  .max(100)
  .regex(/^[A-Za-z0-9._:-]+$/)

export class AppPermissionService {
  private readonly roles: ReadonlySet<string>
  private readonly scopes: ReadonlySet<string>

  constructor(context: AppSessionContext) {
    this.roles = new Set(context.roles.map(parsePermissionName))
    this.scopes = new Set(context.scopes.map(parsePermissionName))
  }

  hasRole(role: string): boolean {
    return this.roles.has(parsePermissionName(role))
  }

  hasAnyRole(roles: readonly string[]): boolean {
    const requested = parsePermissionNames(roles)
    return requested.some((role) => this.roles.has(role))
  }

  hasScope(scope: string): boolean {
    return this.scopes.has(parsePermissionName(scope))
  }

  hasAllScopes(scopes: readonly string[]): boolean {
    const requested = parsePermissionNames(scopes)
    return requested.every((scope) => this.scopes.has(scope))
  }

  requireScope(scope: string): void {
    if (!this.hasScope(scope)) throw new AppPermissionDeniedError("APP_SCOPE_REQUIRED")
  }

  requireAnyRole(roles: readonly string[]): void {
    if (!this.hasAnyRole(roles)) throw new AppPermissionDeniedError("APP_ROLE_REQUIRED")
  }
}

export class AppPermissionDeniedError extends Error {
  readonly name = "AppPermissionDeniedError"
  constructor(readonly code: "APP_SCOPE_REQUIRED" | "APP_ROLE_REQUIRED") {
    super(code)
  }
}

function parsePermissionNames(values: readonly string[]): string[] {
  if (values.length === 0) throw new AppPermissionInputError()
  return values.map(parsePermissionName)
}

function parsePermissionName(value: string): string {
  const parsed = PermissionNameSchema.safeParse(value)
  if (!parsed.success) throw new AppPermissionInputError()
  return parsed.data
}

export class AppPermissionInputError extends Error {
  readonly name = "AppPermissionInputError"
  constructor() {
    super("APP_PERMISSION_INPUT_INVALID")
  }
}
