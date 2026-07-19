import { type Socket } from "node:net";
import type { LaunchContext } from "./launch-context.js";
import type { MessageEnvelopeGuard } from "./message-envelope-guard.js";
import { type LauncherSession } from "./protocol.js";
export type AppHandshakeIdentity = {
    readonly launchSessionId: string;
    readonly instanceId: string;
    readonly appId: string;
    readonly appVersion: string;
    readonly dataSchemaVersion: number;
    readonly pid: number;
    readonly packageHash: string;
};
export declare function connectPipe(pipePath: string): Promise<Socket>;
export declare function writeMessage(socket: Socket, message: object): Promise<void>;
export declare function performHandshake(socket: Socket, context: LaunchContext, identity: AppHandshakeIdentity, timeoutMs: number, envelopeGuard: MessageEnvelopeGuard): Promise<LauncherSession>;
export declare class JsonLineDecoder {
    private buffered;
    push(chunk: Buffer): readonly unknown[];
}
export declare class TransportError extends Error {
    readonly code: string;
    readonly name = "TransportError";
    constructor(code: string);
}
//# sourceMappingURL=transport.d.ts.map