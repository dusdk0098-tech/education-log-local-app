import { connect } from "node:net";
import { createEnvelope, createHelloProof, LauncherBootstrapSchema, LauncherSessionSchema, } from "./protocol.js";
export function connectPipe(pipePath) {
    return new Promise((resolve, reject) => {
        const socket = connect(pipePath);
        socket.once("connect", () => resolve(socket));
        socket.once("error", reject);
    });
}
export function writeMessage(socket, message) {
    return new Promise((resolve, reject) => {
        socket.write(`${JSON.stringify(message)}\n`, (error) => {
            if (error === null || error === undefined)
                resolve();
            else
                reject(error);
        });
    });
}
export async function performHandshake(socket, context, identity, timeoutMs, envelopeGuard) {
    const decoder = new JsonLineDecoder();
    let phase = "bootstrap";
    const { instanceId: _instanceId, ...identityPayload } = identity;
    const sessionPromise = new Promise((resolve, reject) => {
        const timeout = setTimeout(() => finish(new TransportError("LAUNCHER_HANDSHAKE_TIMEOUT")), timeoutMs);
        const handleData = (chunk) => {
            try {
                const messages = decoder.push(chunk);
                for (const message of messages) {
                    if (phase === "bootstrap") {
                        const bootstrap = LauncherBootstrapSchema.parse(message);
                        envelopeGuard.validate(bootstrap);
                        assertBinding(bootstrap.instanceId, bootstrap.payload.launchSessionId, context, "LAUNCHER_BOOTSTRAP_BINDING_INVALID");
                        phase = "session";
                        void writeMessage(socket, createEnvelope(context.instanceId, "app.hello", {
                            ...identityPayload,
                            proof: createHelloProof(bootstrap.payload.bootstrapSecret, identity),
                        })).catch((error) => finish(error instanceof Error ? error : new TransportError("APP_HELLO_WRITE_FAILED")));
                        continue;
                    }
                    const session = LauncherSessionSchema.parse(message);
                    envelopeGuard.validate(session);
                    assertBinding(session.instanceId, session.payload.launchSessionId, context, "LAUNCHER_SESSION_BINDING_INVALID");
                    finish(undefined, session);
                    return;
                }
            }
            catch (error) {
                finish(error instanceof Error ? error : new TransportError("LAUNCHER_HANDSHAKE_INVALID"));
            }
        };
        const handleError = (error) => finish(error);
        const finish = (error, session) => {
            clearTimeout(timeout);
            socket.removeListener("data", handleData);
            socket.removeListener("error", handleError);
            if (error !== undefined)
                reject(error);
            else if (session !== undefined)
                resolve(session);
        };
        socket.on("data", handleData);
        socket.once("error", handleError);
    });
    await writeMessage(socket, createEnvelope(context.instanceId, "app.bootstrap", identityPayload));
    return sessionPromise;
}
function assertBinding(instanceId, launchSessionId, context, code) {
    if (instanceId !== context.instanceId || launchSessionId !== context.launchSessionId) {
        throw new TransportError(code);
    }
}
export class JsonLineDecoder {
    buffered = "";
    push(chunk) {
        this.buffered += chunk.toString("utf8");
        if (Buffer.byteLength(this.buffered, "utf8") > 64 * 1024) {
            throw new TransportError("LAUNCHER_MESSAGE_TOO_LARGE");
        }
        const lines = this.buffered.split("\n");
        this.buffered = lines.pop() ?? "";
        const messages = [];
        for (const line of lines) {
            if (line.length > 0)
                messages.push(JSON.parse(line));
        }
        return messages;
    }
}
export class TransportError extends Error {
    code;
    name = "TransportError";
    constructor(code) {
        super(code);
        this.code = code;
    }
}
//# sourceMappingURL=transport.js.map