export type GuardedMessageEnvelope = {
    readonly messageId: string;
    readonly timestamp: string;
};
export declare class MessageEnvelopeGuard {
    private readonly seenMessageIds;
    validate(message: GuardedMessageEnvelope): void;
}
export declare class MessageEnvelopeGuardError extends Error {
    readonly code: string;
    readonly name = "MessageEnvelopeGuardError";
    constructor(code: string);
}
//# sourceMappingURL=message-envelope-guard.d.ts.map