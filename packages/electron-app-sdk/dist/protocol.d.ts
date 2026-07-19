import { z } from "zod";
export declare const PEDIT_APP_PROTOCOL_VERSION: 2;
export declare const AppBootstrapSchema: z.ZodObject<{
    messageId: z.ZodUUID;
    protocolVersion: z.ZodLiteral<2>;
    timestamp: z.ZodISODateTime;
    instanceId: z.ZodUUID;
    type: z.ZodLiteral<"app.bootstrap">;
    payload: z.ZodObject<{
        launchSessionId: z.ZodUUID;
        appId: z.ZodString;
        appVersion: z.ZodString;
        dataSchemaVersion: z.ZodNumber;
        pid: z.ZodNumber;
        packageHash: z.ZodString;
    }, z.core.$strict>;
}, z.core.$strict>;
export declare const AppHelloSchema: z.ZodObject<{
    messageId: z.ZodUUID;
    protocolVersion: z.ZodLiteral<2>;
    timestamp: z.ZodISODateTime;
    instanceId: z.ZodUUID;
    type: z.ZodLiteral<"app.hello">;
    payload: z.ZodObject<{
        launchSessionId: z.ZodUUID;
        appId: z.ZodString;
        appVersion: z.ZodString;
        dataSchemaVersion: z.ZodNumber;
        pid: z.ZodNumber;
        packageHash: z.ZodString;
        proof: z.ZodString;
    }, z.core.$strict>;
}, z.core.$strict>;
export declare const AppReadySchema: z.ZodObject<{
    messageId: z.ZodUUID;
    protocolVersion: z.ZodLiteral<2>;
    timestamp: z.ZodISODateTime;
    instanceId: z.ZodUUID;
    type: z.ZodLiteral<"app.ready">;
    payload: z.ZodObject<{
        databaseReady: z.ZodBoolean;
        rendererReady: z.ZodBoolean;
        windowReady: z.ZodBoolean;
    }, z.core.$strict>;
}, z.core.$strict>;
export declare const AppHeartbeatSchema: z.ZodObject<{
    messageId: z.ZodUUID;
    protocolVersion: z.ZodLiteral<2>;
    timestamp: z.ZodISODateTime;
    instanceId: z.ZodUUID;
    type: z.ZodLiteral<"app.heartbeat">;
    payload: z.ZodObject<{
        sequence: z.ZodNumber;
    }, z.core.$strict>;
}, z.core.$strict>;
export declare const AppErrorSchema: z.ZodObject<{
    messageId: z.ZodUUID;
    protocolVersion: z.ZodLiteral<2>;
    timestamp: z.ZodISODateTime;
    instanceId: z.ZodUUID;
    type: z.ZodLiteral<"app.error">;
    payload: z.ZodObject<{
        code: z.ZodString;
        message: z.ZodString;
        recoverable: z.ZodBoolean;
    }, z.core.$strict>;
}, z.core.$strict>;
export declare const AppStoppingSchema: z.ZodObject<{
    messageId: z.ZodUUID;
    protocolVersion: z.ZodLiteral<2>;
    timestamp: z.ZodISODateTime;
    instanceId: z.ZodUUID;
    type: z.ZodLiteral<"app.stopping">;
    payload: z.ZodObject<{
        reason: z.ZodString;
    }, z.core.$strict>;
}, z.core.$strict>;
export declare const AppStoppedSchema: z.ZodObject<{
    messageId: z.ZodUUID;
    protocolVersion: z.ZodLiteral<2>;
    timestamp: z.ZodISODateTime;
    instanceId: z.ZodUUID;
    type: z.ZodLiteral<"app.stopped">;
    payload: z.ZodObject<{
        exitCode: z.ZodNullable<z.ZodNumber>;
    }, z.core.$strict>;
}, z.core.$strict>;
export declare const AppMessageSchema: z.ZodDiscriminatedUnion<[z.ZodObject<{
    messageId: z.ZodUUID;
    protocolVersion: z.ZodLiteral<2>;
    timestamp: z.ZodISODateTime;
    instanceId: z.ZodUUID;
    type: z.ZodLiteral<"app.bootstrap">;
    payload: z.ZodObject<{
        launchSessionId: z.ZodUUID;
        appId: z.ZodString;
        appVersion: z.ZodString;
        dataSchemaVersion: z.ZodNumber;
        pid: z.ZodNumber;
        packageHash: z.ZodString;
    }, z.core.$strict>;
}, z.core.$strict>, z.ZodObject<{
    messageId: z.ZodUUID;
    protocolVersion: z.ZodLiteral<2>;
    timestamp: z.ZodISODateTime;
    instanceId: z.ZodUUID;
    type: z.ZodLiteral<"app.hello">;
    payload: z.ZodObject<{
        launchSessionId: z.ZodUUID;
        appId: z.ZodString;
        appVersion: z.ZodString;
        dataSchemaVersion: z.ZodNumber;
        pid: z.ZodNumber;
        packageHash: z.ZodString;
        proof: z.ZodString;
    }, z.core.$strict>;
}, z.core.$strict>, z.ZodObject<{
    messageId: z.ZodUUID;
    protocolVersion: z.ZodLiteral<2>;
    timestamp: z.ZodISODateTime;
    instanceId: z.ZodUUID;
    type: z.ZodLiteral<"app.ready">;
    payload: z.ZodObject<{
        databaseReady: z.ZodBoolean;
        rendererReady: z.ZodBoolean;
        windowReady: z.ZodBoolean;
    }, z.core.$strict>;
}, z.core.$strict>, z.ZodObject<{
    messageId: z.ZodUUID;
    protocolVersion: z.ZodLiteral<2>;
    timestamp: z.ZodISODateTime;
    instanceId: z.ZodUUID;
    type: z.ZodLiteral<"app.heartbeat">;
    payload: z.ZodObject<{
        sequence: z.ZodNumber;
    }, z.core.$strict>;
}, z.core.$strict>, z.ZodObject<{
    messageId: z.ZodUUID;
    protocolVersion: z.ZodLiteral<2>;
    timestamp: z.ZodISODateTime;
    instanceId: z.ZodUUID;
    type: z.ZodLiteral<"app.error">;
    payload: z.ZodObject<{
        code: z.ZodString;
        message: z.ZodString;
        recoverable: z.ZodBoolean;
    }, z.core.$strict>;
}, z.core.$strict>, z.ZodObject<{
    messageId: z.ZodUUID;
    protocolVersion: z.ZodLiteral<2>;
    timestamp: z.ZodISODateTime;
    instanceId: z.ZodUUID;
    type: z.ZodLiteral<"app.stopping">;
    payload: z.ZodObject<{
        reason: z.ZodString;
    }, z.core.$strict>;
}, z.core.$strict>, z.ZodObject<{
    messageId: z.ZodUUID;
    protocolVersion: z.ZodLiteral<2>;
    timestamp: z.ZodISODateTime;
    instanceId: z.ZodUUID;
    type: z.ZodLiteral<"app.stopped">;
    payload: z.ZodObject<{
        exitCode: z.ZodNullable<z.ZodNumber>;
    }, z.core.$strict>;
}, z.core.$strict>], "type">;
export type AppMessage = z.infer<typeof AppMessageSchema>;
export declare const LauncherBootstrapSchema: z.ZodObject<{
    messageId: z.ZodUUID;
    protocolVersion: z.ZodLiteral<2>;
    timestamp: z.ZodISODateTime;
    instanceId: z.ZodUUID;
    type: z.ZodLiteral<"launcher.bootstrap">;
    payload: z.ZodObject<{
        launchSessionId: z.ZodUUID;
        bootstrapSecret: z.ZodString;
    }, z.core.$strict>;
}, z.core.$strict>;
export declare const LauncherSessionSchema: z.ZodObject<{
    messageId: z.ZodUUID;
    protocolVersion: z.ZodLiteral<2>;
    timestamp: z.ZodISODateTime;
    instanceId: z.ZodUUID;
    type: z.ZodLiteral<"launcher.session">;
    payload: z.ZodObject<{
        launchSessionId: z.ZodUUID;
        appSessionToken: z.ZodString;
        expiresAt: z.ZodISODateTime;
        userId: z.ZodString;
        workspaceId: z.ZodString;
        roles: z.ZodArray<z.ZodString>;
        scopes: z.ZodArray<z.ZodString>;
        deviceId: z.ZodOptional<z.ZodUUID>;
        dataScopeId: z.ZodOptional<z.ZodUUID>;
    }, z.core.$strict>;
}, z.core.$strict>;
export declare const LauncherSessionRenewedSchema: z.ZodObject<{
    messageId: z.ZodUUID;
    protocolVersion: z.ZodLiteral<2>;
    timestamp: z.ZodISODateTime;
    instanceId: z.ZodUUID;
    type: z.ZodLiteral<"launcher.session-renewed">;
    payload: z.ZodObject<{
        launchSessionId: z.ZodUUID;
        appSessionToken: z.ZodString;
        expiresAt: z.ZodISODateTime;
        roles: z.ZodArray<z.ZodString>;
        scopes: z.ZodArray<z.ZodString>;
        deviceId: z.ZodOptional<z.ZodUUID>;
        dataScopeId: z.ZodOptional<z.ZodUUID>;
    }, z.core.$strict>;
}, z.core.$strict>;
export declare const LauncherShutdownSchema: z.ZodObject<{
    messageId: z.ZodUUID;
    protocolVersion: z.ZodLiteral<2>;
    timestamp: z.ZodISODateTime;
    instanceId: z.ZodUUID;
    type: z.ZodLiteral<"launcher.shutdown">;
    payload: z.ZodObject<{
        reason: z.ZodString;
    }, z.core.$strict>;
}, z.core.$strict>;
export declare const LauncherMessageSchema: z.ZodDiscriminatedUnion<[z.ZodObject<{
    messageId: z.ZodUUID;
    protocolVersion: z.ZodLiteral<2>;
    timestamp: z.ZodISODateTime;
    instanceId: z.ZodUUID;
    type: z.ZodLiteral<"launcher.bootstrap">;
    payload: z.ZodObject<{
        launchSessionId: z.ZodUUID;
        bootstrapSecret: z.ZodString;
    }, z.core.$strict>;
}, z.core.$strict>, z.ZodObject<{
    messageId: z.ZodUUID;
    protocolVersion: z.ZodLiteral<2>;
    timestamp: z.ZodISODateTime;
    instanceId: z.ZodUUID;
    type: z.ZodLiteral<"launcher.session">;
    payload: z.ZodObject<{
        launchSessionId: z.ZodUUID;
        appSessionToken: z.ZodString;
        expiresAt: z.ZodISODateTime;
        userId: z.ZodString;
        workspaceId: z.ZodString;
        roles: z.ZodArray<z.ZodString>;
        scopes: z.ZodArray<z.ZodString>;
        deviceId: z.ZodOptional<z.ZodUUID>;
        dataScopeId: z.ZodOptional<z.ZodUUID>;
    }, z.core.$strict>;
}, z.core.$strict>, z.ZodObject<{
    messageId: z.ZodUUID;
    protocolVersion: z.ZodLiteral<2>;
    timestamp: z.ZodISODateTime;
    instanceId: z.ZodUUID;
    type: z.ZodLiteral<"launcher.session-renewed">;
    payload: z.ZodObject<{
        launchSessionId: z.ZodUUID;
        appSessionToken: z.ZodString;
        expiresAt: z.ZodISODateTime;
        roles: z.ZodArray<z.ZodString>;
        scopes: z.ZodArray<z.ZodString>;
        deviceId: z.ZodOptional<z.ZodUUID>;
        dataScopeId: z.ZodOptional<z.ZodUUID>;
    }, z.core.$strict>;
}, z.core.$strict>, z.ZodObject<{
    messageId: z.ZodUUID;
    protocolVersion: z.ZodLiteral<2>;
    timestamp: z.ZodISODateTime;
    instanceId: z.ZodUUID;
    type: z.ZodLiteral<"launcher.shutdown">;
    payload: z.ZodObject<{
        reason: z.ZodString;
    }, z.core.$strict>;
}, z.core.$strict>], "type">;
export type LauncherSession = z.infer<typeof LauncherSessionSchema>;
export type LauncherSessionRenewed = z.infer<typeof LauncherSessionRenewedSchema>;
export type LauncherBootstrap = z.infer<typeof LauncherBootstrapSchema>;
export declare function createEnvelope(instanceId: string, type: string, payload: object): {
    messageId: `${string}-${string}-${string}-${string}-${string}`;
    type: string;
    protocolVersion: 2;
    timestamp: string;
    instanceId: string;
    payload: object;
};
export declare function createHelloProof(secret: string, input: {
    readonly launchSessionId: string;
    readonly instanceId: string;
    readonly appId: string;
    readonly appVersion: string;
    readonly dataSchemaVersion: number;
    readonly pid: number;
    readonly packageHash: string;
}): string;
//# sourceMappingURL=protocol.d.ts.map