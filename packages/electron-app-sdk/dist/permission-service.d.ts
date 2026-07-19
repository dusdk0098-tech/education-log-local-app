import type { AppSessionContext } from "./launcher-connection.js";
export declare class AppPermissionService {
    private readonly roles;
    private readonly scopes;
    constructor(context: AppSessionContext);
    hasRole(role: string): boolean;
    hasAnyRole(roles: readonly string[]): boolean;
    hasScope(scope: string): boolean;
    hasAllScopes(scopes: readonly string[]): boolean;
    requireScope(scope: string): void;
    requireAnyRole(roles: readonly string[]): void;
}
export declare class AppPermissionDeniedError extends Error {
    readonly code: "APP_SCOPE_REQUIRED" | "APP_ROLE_REQUIRED";
    readonly name = "AppPermissionDeniedError";
    constructor(code: "APP_SCOPE_REQUIRED" | "APP_ROLE_REQUIRED");
}
export declare class AppPermissionInputError extends Error {
    readonly name = "AppPermissionInputError";
    constructor();
}
//# sourceMappingURL=permission-service.d.ts.map