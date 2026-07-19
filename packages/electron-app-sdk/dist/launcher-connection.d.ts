import { type AppSdkEventSink } from "./event-logger.js";
import type { LaunchContext } from "./launch-context.js";
export declare const APP_HEARTBEAT_INTERVAL_MS = 5000;
export type LauncherConnectionOptions = {
    readonly context: LaunchContext;
    readonly appVersion: string;
    readonly dataSchemaVersion: number;
    readonly packageHash: string;
    readonly handshakeTimeoutMs?: number;
    readonly heartbeatIntervalMs?: number;
    readonly onShutdown: (reason: string) => Promise<void>;
    readonly onSessionRenewed?: (context: AppSessionContext) => Promise<void>;
    readonly eventSink?: AppSdkEventSink;
};
export type AppSessionContext = {
    readonly userId: string;
    readonly workspaceId: string;
    readonly roles: readonly string[];
    readonly scopes: readonly string[];
    readonly expiresAt: string;
    readonly deviceId?: string;
    readonly dataScopeId?: string;
};
export declare class LauncherConnection {
    private readonly socket;
    private readonly context;
    private readonly options;
    private readonly envelopeGuard;
    private readonly events;
    private accessToken;
    private heartbeat;
    private heartbeatSequence;
    private closing;
    private currentSessionContext;
    private constructor();
    get sessionContext(): AppSessionContext;
    static connect(options: LauncherConnectionOptions): Promise<LauncherConnection>;
    reportReady(): Promise<void>;
    withAccessToken<T>(operation: (accessToken: string) => Promise<T>): Promise<T>;
    reportError(code: string, message: string, recoverable: boolean): Promise<void>;
    close(reason: string): Promise<void>;
    private listenForRuntimeMessages;
    private startHeartbeat;
    private applyRenewedSession;
    private shutdown;
    private failClosed;
    private clearSecrets;
}
export declare class LauncherConnectionError extends Error {
    readonly code: string;
    readonly name = "LauncherConnectionError";
    constructor(code: string);
}
//# sourceMappingURL=launcher-connection.d.ts.map