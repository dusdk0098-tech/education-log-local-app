import { AppSdkEventLogger } from "./event-logger.js";
import { MessageEnvelopeGuard } from "./message-envelope-guard.js";
import { createEnvelope, LauncherMessageSchema, } from "./protocol.js";
import { connectPipe, JsonLineDecoder, performHandshake, writeMessage } from "./transport.js";
export const APP_HEARTBEAT_INTERVAL_MS = 5_000;
export class LauncherConnection {
    socket;
    context;
    options;
    envelopeGuard;
    events;
    accessToken;
    heartbeat = null;
    heartbeatSequence = 0;
    closing = false;
    currentSessionContext;
    constructor(socket, context, session, options, envelopeGuard, events) {
        this.socket = socket;
        this.context = context;
        this.options = options;
        this.envelopeGuard = envelopeGuard;
        this.events = events;
        this.accessToken = session.payload.appSessionToken;
        this.currentSessionContext = {
            userId: session.payload.userId,
            workspaceId: session.payload.workspaceId,
            roles: [...session.payload.roles],
            scopes: [...session.payload.scopes],
            expiresAt: session.payload.expiresAt,
            ...(session.payload.deviceId === undefined ? {} : { deviceId: session.payload.deviceId }),
            ...(session.payload.dataScopeId === undefined
                ? {}
                : { dataScopeId: session.payload.dataScopeId }),
        };
    }
    get sessionContext() {
        return this.currentSessionContext;
    }
    static async connect(options) {
        if (options.packageHash !== options.context.packageHash) {
            throw new LauncherConnectionError("APP_PACKAGE_HASH_MISMATCH");
        }
        const socket = await connectPipe(options.context.launcherPipe);
        const identity = {
            launchSessionId: options.context.launchSessionId,
            instanceId: options.context.instanceId,
            appId: options.context.appId,
            appVersion: options.appVersion,
            dataSchemaVersion: options.dataSchemaVersion,
            pid: process.pid,
            packageHash: options.packageHash,
        };
        const envelopeGuard = new MessageEnvelopeGuard();
        const events = new AppSdkEventLogger({ appId: options.context.appId, instanceId: options.context.instanceId }, options.eventSink);
        const session = await performHandshake(socket, options.context, identity, options.handshakeTimeoutMs ?? 10_000, envelopeGuard);
        const connection = new LauncherConnection(socket, options.context, session, options, envelopeGuard, events);
        connection.listenForRuntimeMessages();
        events.info("launcher.connection.ready", { protocolVersion: 2 });
        return connection;
    }
    async reportReady() {
        await writeMessage(this.socket, createEnvelope(this.context.instanceId, "app.ready", {
            databaseReady: true,
            rendererReady: true,
            windowReady: true,
        }));
        this.startHeartbeat();
        this.events.info("app.ready");
    }
    async withAccessToken(operation) {
        if (this.accessToken === null)
            throw new LauncherConnectionError("APP_SESSION_UNAVAILABLE");
        return operation(this.accessToken);
    }
    async reportError(code, message, recoverable) {
        await writeMessage(this.socket, createEnvelope(this.context.instanceId, "app.error", { code, message, recoverable }));
    }
    async close(reason) {
        await this.shutdown(reason);
    }
    listenForRuntimeMessages() {
        const decoder = new JsonLineDecoder();
        this.socket.on("data", (chunk) => {
            try {
                for (const raw of decoder.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk))) {
                    const message = LauncherMessageSchema.parse(raw);
                    this.envelopeGuard.validate(message);
                    if (message.instanceId !== this.context.instanceId) {
                        void this.failClosed("LAUNCHER_INSTANCE_MISMATCH");
                        continue;
                    }
                    switch (message.type) {
                        case "launcher.bootstrap":
                            void this.failClosed("LAUNCHER_BOOTSTRAP_REPLAYED");
                            break;
                        case "launcher.session":
                            void this.failClosed("LAUNCHER_SESSION_REPLAYED");
                            break;
                        case "launcher.session-renewed":
                            if (message.payload.launchSessionId !== this.context.launchSessionId) {
                                void this.failClosed("LAUNCHER_SESSION_BINDING_INVALID");
                                break;
                            }
                            void this.applyRenewedSession(message).catch(() => this.failClosed("APP_SESSION_RENEWAL_HANDLER_FAILED"));
                            break;
                        case "launcher.shutdown":
                            void this.shutdown(message.payload.reason);
                            break;
                        default:
                            assertNever(message);
                    }
                }
            }
            catch {
                void this.failClosed("LAUNCHER_MESSAGE_INVALID");
            }
        });
        this.socket.once("close", () => {
            if (this.closing)
                this.clearSecrets();
            else
                void this.failClosed("LAUNCHER_PIPE_CLOSED");
        });
    }
    startHeartbeat() {
        if (this.heartbeat !== null)
            return;
        this.heartbeat = setInterval(() => {
            const sequence = this.heartbeatSequence;
            this.heartbeatSequence += 1;
            void writeMessage(this.socket, createEnvelope(this.context.instanceId, "app.heartbeat", { sequence })).catch(() => this.failClosed("APP_HEARTBEAT_WRITE_FAILED"));
        }, this.options.heartbeatIntervalMs ?? APP_HEARTBEAT_INTERVAL_MS);
        this.heartbeat.unref();
    }
    async applyRenewedSession(message) {
        this.accessToken = message.payload.appSessionToken;
        this.currentSessionContext = {
            ...this.currentSessionContext,
            roles: [...message.payload.roles],
            scopes: [...message.payload.scopes],
            expiresAt: message.payload.expiresAt,
            ...(message.payload.deviceId === undefined ? {} : { deviceId: message.payload.deviceId }),
            ...(message.payload.dataScopeId === undefined
                ? {}
                : { dataScopeId: message.payload.dataScopeId }),
        };
        await this.options.onSessionRenewed?.(this.currentSessionContext);
        this.events.info("app.session.renewed");
    }
    async shutdown(reason) {
        if (this.closing)
            return;
        this.closing = true;
        this.events.info("app.shutdown.started");
        if (this.heartbeat !== null)
            clearInterval(this.heartbeat);
        await writeMessage(this.socket, createEnvelope(this.context.instanceId, "app.stopping", { reason }));
        try {
            await this.options.onShutdown(reason);
            await writeMessage(this.socket, createEnvelope(this.context.instanceId, "app.stopped", { exitCode: 0 }));
        }
        finally {
            this.clearSecrets();
            this.socket.end();
            this.events.info("app.shutdown.completed");
        }
    }
    async failClosed(code) {
        if (this.closing)
            return;
        this.closing = true;
        this.events.error("app.fail_closed", { code });
        this.clearSecrets();
        try {
            await this.reportError("IPC-001", code, false);
        }
        catch {
            // The pipe may already be gone; local fail-closed must still complete.
        }
        finally {
            this.socket.destroy();
        }
    }
    clearSecrets() {
        this.accessToken = null;
        if (this.heartbeat !== null)
            clearInterval(this.heartbeat);
        this.heartbeat = null;
    }
}
export class LauncherConnectionError extends Error {
    code;
    name = "LauncherConnectionError";
    constructor(code) {
        super(code);
        this.code = code;
    }
}
function assertNever(value) {
    throw new LauncherConnectionError(`LAUNCHER_MESSAGE_UNSUPPORTED:${String(value)}`);
}
//# sourceMappingURL=launcher-connection.js.map