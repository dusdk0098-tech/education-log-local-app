import { z } from "zod";
const EventNameSchema = z
    .string()
    .regex(/^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$/)
    .max(100);
const AppIdSchema = z.string().regex(/^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/);
const InstanceIdSchema = z.uuid();
export class AppSdkEventLogger {
    sink;
    now;
    appId;
    instanceId;
    sinkHealthy = true;
    constructor(identity, sink, now = () => new Date()) {
        this.sink = sink;
        this.now = now;
        this.appId = AppIdSchema.parse(identity.appId);
        this.instanceId = InstanceIdSchema.parse(identity.instanceId);
    }
    get sinkAvailable() {
        return this.sinkHealthy;
    }
    info(name, fields = {}) {
        this.record("info", name, fields);
    }
    warn(name, fields = {}) {
        this.record("warn", name, fields);
    }
    error(name, fields = {}) {
        this.record("error", name, fields);
    }
    record(level, name, fields) {
        if (this.sink === undefined)
            return;
        const event = {
            level,
            name: EventNameSchema.parse(name),
            occurredAt: this.now().toISOString(),
            appId: this.appId,
            instanceId: this.instanceId,
            fields: sanitizeFields(fields),
        };
        try {
            const result = this.sink.record(event);
            if (result instanceof Promise) {
                void result.catch(() => {
                    this.sinkHealthy = false;
                });
            }
        }
        catch {
            this.sinkHealthy = false;
        }
    }
}
const BlockedFieldNames = [
    "token",
    "authorization",
    "cookie",
    "password",
    "secret",
    "email",
    "displayname",
    "userid",
    "workspaceid",
];
function sanitizeFields(input) {
    const fields = {};
    for (const [key, value] of Object.entries(input)) {
        if (!isSafeFieldName(key) || !isEventField(value))
            continue;
        fields[key] = typeof value === "string" ? value.slice(0, 200) : value;
    }
    return fields;
}
function isSafeFieldName(value) {
    if (value.length === 0 || value.length > 80 || !/^[A-Za-z][A-Za-z0-9_.-]*$/.test(value)) {
        return false;
    }
    const normalized = value.toLowerCase().replaceAll(/[^a-z0-9]/g, "");
    return !BlockedFieldNames.some((blocked) => normalized.includes(blocked));
}
function isEventField(value) {
    return (value === null ||
        typeof value === "string" ||
        (typeof value === "number" && Number.isFinite(value)) ||
        typeof value === "boolean");
}
//# sourceMappingURL=event-logger.js.map