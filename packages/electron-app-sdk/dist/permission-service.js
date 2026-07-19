import { z } from "zod";
const PermissionNameSchema = z
    .string()
    .trim()
    .min(1)
    .max(100)
    .regex(/^[A-Za-z0-9._:-]+$/);
export class AppPermissionService {
    roles;
    scopes;
    constructor(context) {
        this.roles = new Set(context.roles.map(parsePermissionName));
        this.scopes = new Set(context.scopes.map(parsePermissionName));
    }
    hasRole(role) {
        return this.roles.has(parsePermissionName(role));
    }
    hasAnyRole(roles) {
        const requested = parsePermissionNames(roles);
        return requested.some((role) => this.roles.has(role));
    }
    hasScope(scope) {
        return this.scopes.has(parsePermissionName(scope));
    }
    hasAllScopes(scopes) {
        const requested = parsePermissionNames(scopes);
        return requested.every((scope) => this.scopes.has(scope));
    }
    requireScope(scope) {
        if (!this.hasScope(scope))
            throw new AppPermissionDeniedError("APP_SCOPE_REQUIRED");
    }
    requireAnyRole(roles) {
        if (!this.hasAnyRole(roles))
            throw new AppPermissionDeniedError("APP_ROLE_REQUIRED");
    }
}
export class AppPermissionDeniedError extends Error {
    code;
    name = "AppPermissionDeniedError";
    constructor(code) {
        super(code);
        this.code = code;
    }
}
function parsePermissionNames(values) {
    if (values.length === 0)
        throw new AppPermissionInputError();
    return values.map(parsePermissionName);
}
function parsePermissionName(value) {
    const parsed = PermissionNameSchema.safeParse(value);
    if (!parsed.success)
        throw new AppPermissionInputError();
    return parsed.data;
}
export class AppPermissionInputError extends Error {
    name = "AppPermissionInputError";
    constructor() {
        super("APP_PERMISSION_INPUT_INVALID");
    }
}
//# sourceMappingURL=permission-service.js.map