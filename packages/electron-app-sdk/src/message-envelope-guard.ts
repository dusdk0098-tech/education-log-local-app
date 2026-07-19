const MessageFreshnessWindowMs = 5 * 60_000
const MessageFutureClockSkewMs = 30_000

export type GuardedMessageEnvelope = {
  readonly messageId: string
  readonly timestamp: string
}

export class MessageEnvelopeGuard {
  private readonly seenMessageIds = new Map<string, number>()

  validate(message: GuardedMessageEnvelope): void {
    const now = Date.now()
    const timestamp = Date.parse(message.timestamp)
    if (timestamp < now - MessageFreshnessWindowMs || timestamp > now + MessageFutureClockSkewMs) {
      throw new MessageEnvelopeGuardError("LAUNCHER_MESSAGE_TIMESTAMP_INVALID")
    }

    const replayCutoff = now - MessageFreshnessWindowMs
    for (const [messageId, receivedAt] of this.seenMessageIds) {
      if (receivedAt < replayCutoff) this.seenMessageIds.delete(messageId)
    }
    if (this.seenMessageIds.has(message.messageId)) {
      throw new MessageEnvelopeGuardError("LAUNCHER_MESSAGE_REPLAYED")
    }
    this.seenMessageIds.set(message.messageId, now)
  }
}

export class MessageEnvelopeGuardError extends Error {
  readonly name = "MessageEnvelopeGuardError"

  constructor(readonly code: string) {
    super(code)
  }
}
