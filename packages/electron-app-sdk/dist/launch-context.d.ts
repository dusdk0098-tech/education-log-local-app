export type LaunchContext = {
    readonly appId: string;
    readonly launcherPipe: string;
    readonly launchSessionId: string;
    readonly instanceId: string;
    readonly dataDirectory: string;
    readonly packageHash: string;
};
export declare function parseLaunchContext(argv: readonly string[]): LaunchContext;
export declare class LaunchContextError extends Error {
    readonly code: string;
    readonly name = "LaunchContextError";
    constructor(code: string);
}
//# sourceMappingURL=launch-context.d.ts.map