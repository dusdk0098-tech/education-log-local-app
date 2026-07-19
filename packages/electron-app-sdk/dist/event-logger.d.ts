export type AppSdkEventLevel = "info" | "warn" | "error";
export type AppSdkEventField = string | number | boolean | null;
export type AppSdkEvent = {
    readonly level: AppSdkEventLevel;
    readonly name: string;
    readonly occurredAt: string;
    readonly appId: string;
    readonly instanceId: string;
    readonly fields: Readonly<Record<string, AppSdkEventField>>;
};
export interface AppSdkEventSink {
    record(event: AppSdkEvent): void | Promise<void>;
}
export declare class AppSdkEventLogger {
    private readonly sink?;
    private readonly now;
    private readonly appId;
    private readonly instanceId;
    private sinkHealthy;
    constructor(identity: {
        readonly appId: string;
        readonly instanceId: string;
    }, sink?: AppSdkEventSink | undefined, now?: () => Date);
    get sinkAvailable(): boolean;
    info(name: string, fields?: Readonly<Record<string, unknown>>): void;
    warn(name: string, fields?: Readonly<Record<string, unknown>>): void;
    error(name: string, fields?: Readonly<Record<string, unknown>>): void;
    private record;
}
//# sourceMappingURL=event-logger.d.ts.map