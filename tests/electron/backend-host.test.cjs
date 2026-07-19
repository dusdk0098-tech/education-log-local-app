const assert = require("node:assert/strict");
const { EventEmitter } = require("node:events");
const test = require("node:test");

const {
  buildBootstrapPayload,
  createBackendHost,
  parseReadyLine
} = require("../../electron/backend-host.cjs");

function safeSessionContext() {
  return {
    userId: "user-1",
    workspaceId: "workspace-1",
    roles: ["member"],
    scopes: ["app:pedit-edu:run"],
    expiresAt: "2026-07-20T00:00:00.000Z",
    deviceId: "device-1"
  };
}

test("backend bootstrap contains only safe context and a fresh per-run secret", () => {
  const first = buildBootstrapPayload("C:\\PEDIT\\data", safeSessionContext());
  const second = buildBootstrapPayload("C:\\PEDIT\\data", safeSessionContext());
  assert.match(first.backendSecret, /^[0-9a-f]{64}$/);
  assert.notEqual(first.backendSecret, second.backendSecret);
  assert.equal(first.sessionContext.userId, "user-1");
  assert.equal("appSessionToken" in first.sessionContext, false);
  assert.equal(JSON.stringify(first).includes("Bearer"), false);
});

test("ready parser accepts exactly one bounded localhost JSON line", () => {
  const ready = parseReadyLine(Buffer.from(JSON.stringify({
    type: "backend.ready",
    protocolVersion: 1,
    host: "127.0.0.1",
    port: 49152,
    pid: 1234
  }), "utf8"));
  assert.equal(ready.origin, "http://127.0.0.1:49152");
  assert.throws(() => parseReadyLine(Buffer.from("{}\n{}")), /BACKEND_READY_INVALID_FRAME/);
  assert.throws(() => parseReadyLine(Buffer.alloc(16_385, 97)), /BACKEND_READY_TOO_LARGE/);
  assert.throws(() => parseReadyLine(Buffer.from(JSON.stringify({ type: "backend.ready", host: "0.0.0.0", port: 49152, pid: 1 }))), /BACKEND_READY_INVALID/);
  assert.throws(() => parseReadyLine(Buffer.from(JSON.stringify({ type: "backend.ready", host: "127.0.0.1", port: 70000, pid: 1 }))), /BACKEND_READY_INVALID/);
});

test("backend host sends bootstrap through stdin and never logs unexpected stdout", async () => {
  const child = new EventEmitter();
  child.stdout = new EventEmitter();
  child.stderr = new EventEmitter();
  let stdinValue = "";
  child.stdin = {
    end(value) {
      stdinValue += value;
    }
  };
  child.pid = 4321;
  child.kill = () => true;
  const hostPromise = createBackendHost({
    executablePath: "PeditEduBackend.exe",
    dataDirectory: "C:\\PEDIT\\data",
    sessionContext: safeSessionContext(),
    timeoutMs: 500,
    spawnImpl: () => child
  });
  child.stdout.emit("data", Buffer.from(JSON.stringify({
    type: "backend.ready",
    protocolVersion: 1,
    host: "127.0.0.1",
    port: 49153,
    pid: 4321
  }) + "\n"));
  const host = await hostPromise;
  const bootstrap = JSON.parse(stdinValue.trim());
  assert.equal(bootstrap.dataDir, "C:\\PEDIT\\data");
  assert.equal(bootstrap.sessionContext.workspaceId, "workspace-1");
  assert.equal(JSON.stringify(bootstrap).includes("appSessionToken"), false);
  assert.equal(host.origin, "http://127.0.0.1:49153");
  assert.equal(host.secret, bootstrap.backendSecret);
});

test("onefile ready PID is accepted only when it is the exact backend descendant", async () => {
  const child = new EventEmitter();
  child.stdout = new EventEmitter();
  child.stderr = new EventEmitter();
  child.stdin = { end() {} };
  child.pid = 4321;
  child.exitCode = null;
  child.signalCode = null;
  child.kill = () => true;
  let validation;
  const hostPromise = createBackendHost({
    executablePath: "C:\\PEDIT\\PeditEduBackend.exe",
    dataDirectory: "C:\\PEDIT\\data",
    sessionContext: safeSessionContext(),
    timeoutMs: 500,
    spawnImpl: () => child,
    validateReadyPidImpl: async (...args) => {
      validation = args;
      return true;
    },
  });
  child.stdout.emit("data", Buffer.from(JSON.stringify({
    type: "backend.ready",
    protocolVersion: 1,
    host: "127.0.0.1",
    port: 49159,
    pid: 4322,
  }) + "\n"));

  const host = await hostPromise;
  assert.deepEqual(validation, [4321, 4322, "C:\\PEDIT\\PeditEduBackend.exe"]);
  assert.equal(host.backendPid, 4322);
});

test("invalid onefile ready PID kills and verifies both root and payload processes", async () => {
  const child = new EventEmitter();
  child.stdout = new EventEmitter();
  child.stderr = new EventEmitter();
  child.stdin = { end() {} };
  child.pid = 4321;
  child.exitCode = null;
  child.signalCode = null;
  child.kill = () => true;
  const running = new Set([4321, 9876]);
  const killed = [];
  const hostPromise = createBackendHost({
    executablePath: "C:\\PEDIT\\PeditEduBackend.exe",
    dataDirectory: "C:\\PEDIT\\data",
    sessionContext: safeSessionContext(),
    timeoutMs: 500,
    spawnImpl: () => child,
    validateReadyPidImpl: async () => false,
    startCleanupKillImpl: async (pid) => {
      killed.push(pid);
      running.delete(pid);
    },
    startProcessExistsImpl: async (pid) => running.has(pid),
  });
  child.stdout.emit("data", Buffer.from(JSON.stringify({
    type: "backend.ready",
    protocolVersion: 1,
    host: "127.0.0.1",
    port: 49160,
    pid: 9876,
  }) + "\n"));

  await assert.rejects(hostPromise, /BACKEND_READY_PID_MISMATCH/);
  assert.deepEqual(killed, [4321, 9876]);
  assert.equal(running.size, 0);
});

test("backend host times out and kills a silent child", async () => {
  const child = new EventEmitter();
  child.stdout = new EventEmitter();
  child.stderr = new EventEmitter();
  child.stdin = { end() {} };
  child.pid = 4321;
  let killed = false;
  child.kill = () => {
    killed = true;
    return true;
  };
  await assert.rejects(
    createBackendHost({
      executablePath: "PeditEduBackend.exe",
      dataDirectory: "C:\\PEDIT\\data",
      sessionContext: safeSessionContext(),
      timeoutMs: 10,
      spawnImpl: () => child
    }),
    /BACKEND_READY_TIMEOUT/
  );
  assert.equal(killed, true);
});

test("unexpected backend exit after ready invokes fail-closed callback", async () => {
  const child = new EventEmitter();
  child.stdout = new EventEmitter();
  child.stderr = new EventEmitter();
  child.stdin = { end() {} };
  child.pid = 4321;
  child.exitCode = null;
  child.signalCode = null;
  child.kill = () => true;
  let exitReason = "";
  const hostPromise = createBackendHost({
    executablePath: "PeditEduBackend.exe",
    dataDirectory: "C:\\PEDIT\\data",
    sessionContext: safeSessionContext(),
    timeoutMs: 500,
    spawnImpl: () => child,
    onUnexpectedExit: async (reason) => {
      exitReason = reason;
    }
  });
  child.stdout.emit("data", Buffer.from(JSON.stringify({
    type: "backend.ready",
    protocolVersion: 1,
    host: "127.0.0.1",
    port: 49154,
    pid: 4321
  }) + "\n"));
  await hostPromise;
  child.emit("exit", 17, null);
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(exitReason, "BACKEND_EXITED");
});

test("legacy migration exit code maps to a recovery-safe error", async () => {
  const child = new EventEmitter();
  child.stdout = new EventEmitter();
  child.stderr = new EventEmitter();
  child.stdin = { end() {} };
  child.pid = 4321;
  child.kill = () => true;
  const promise = createBackendHost({
    executablePath: "PeditEduBackend.exe",
    dataDirectory: "C:\\PEDIT\\data",
    sessionContext: safeSessionContext(),
    timeoutMs: 500,
    spawnImpl: () => child
  });
  child.emit("exit", 42, null);
  await assert.rejects(promise, /LEGACY_DATABASE_RECOVERY_REQUIRED/);
});

test("session renewal sends only safe context over the authenticated loopback channel", async () => {
  const child = new EventEmitter();
  child.stdout = new EventEmitter();
  child.stderr = new EventEmitter();
  child.stdin = { end() {} };
  child.pid = 4321;
  child.exitCode = null;
  child.signalCode = null;
  child.kill = () => true;
  let captured;
  const hostPromise = createBackendHost({
    executablePath: "PeditEduBackend.exe",
    dataDirectory: "C:\\PEDIT\\data",
    sessionContext: safeSessionContext(),
    timeoutMs: 500,
    spawnImpl: () => child,
    fetchImpl: async (url, options) => {
      captured = { url, options };
      return { ok: true };
    }
  });
  child.stdout.emit("data", Buffer.from(JSON.stringify({
    type: "backend.ready",
    protocolVersion: 1,
    host: "127.0.0.1",
    port: 49155,
    pid: 4321
  }) + "\n"));
  const host = await hostPromise;
  await host.renewSession({ ...safeSessionContext(), appSessionToken: "must-never-cross" });
  assert.equal(captured.url, "http://127.0.0.1:49155/__launcher/session/renew");
  assert.equal(captured.options.headers["X-Pedit-Backend-Session"], host.secret);
  assert.equal(captured.options.headers.Origin, host.origin);
  assert.equal(JSON.parse(captured.options.body).appSessionToken, undefined);
});

test("backend stop blocks new requests and waits for the backend to exit itself", async () => {
  const child = new EventEmitter();
  child.stdout = new EventEmitter();
  child.stderr = new EventEmitter();
  child.stdin = { end() {} };
  child.pid = 4321;
  child.exitCode = null;
  child.signalCode = null;
  const signals = [];
  child.kill = (signal) => {
    signals.push(signal);
    return true;
  };
  let shutdownRequest;
  let forced = false;
  const hostPromise = createBackendHost({
    executablePath: "PeditEduBackend.exe",
    dataDirectory: "C:\\PEDIT\\data",
    sessionContext: safeSessionContext(),
    timeoutMs: 500,
    stopTimeoutMs: 50,
    spawnImpl: () => child,
    fetchImpl: async (url, options) => {
      shutdownRequest = { url, options };
      setImmediate(() => {
        child.exitCode = 0;
        child.emit("exit", 0, null);
      });
      return { ok: true };
    },
    forceKillImpl: async () => {
      forced = true;
    }
  });
  child.stdout.emit("data", Buffer.from(JSON.stringify({
    type: "backend.ready",
    protocolVersion: 1,
    host: "127.0.0.1",
    port: 49156,
    pid: 4321
  }) + "\n"));
  const host = await hostPromise;

  await host.stop();

  assert.equal(shutdownRequest.url, "http://127.0.0.1:49156/__launcher/shutdown/prepare");
  assert.equal(shutdownRequest.options.headers["X-Pedit-Backend-Session"], host.secret);
  assert.deepEqual(signals, []);
  assert.equal(forced, false);
  assert.equal(child.exitCode, 0);
});

test("backend stop force-kills the process tree after the graceful timeout", async () => {
  const child = new EventEmitter();
  child.stdout = new EventEmitter();
  child.stderr = new EventEmitter();
  child.stdin = { end() {} };
  child.pid = 4321;
  child.exitCode = null;
  child.signalCode = null;
  const signals = [];
  child.kill = (signal) => {
    signals.push(signal);
    return true;
  };
  const forcedPids = [];
  const hostPromise = createBackendHost({
    executablePath: "PeditEduBackend.exe",
    dataDirectory: "C:\\PEDIT\\data",
    sessionContext: safeSessionContext(),
    timeoutMs: 500,
    stopTimeoutMs: 10,
    forceWaitTimeoutMs: 50,
    spawnImpl: () => child,
    fetchImpl: async () => ({ ok: true }),
    forceKillImpl: async (pid) => {
      forcedPids.push(pid);
      setImmediate(() => {
        child.signalCode = "SIGKILL";
        child.emit("exit", null, "SIGKILL");
      });
    }
  });
  child.stdout.emit("data", Buffer.from(JSON.stringify({
    type: "backend.ready",
    protocolVersion: 1,
    host: "127.0.0.1",
    port: 49157,
    pid: 4321
  }) + "\n"));
  const host = await hostPromise;

  await host.stop();

  assert.deepEqual(signals, []);
  assert.deepEqual(forcedPids, [4321]);
  assert.equal(child.signalCode, "SIGKILL");
});

test("backend stop cannot hang on the shutdown preparation request", async () => {
  const child = new EventEmitter();
  child.stdout = new EventEmitter();
  child.stderr = new EventEmitter();
  child.stdin = { end() {} };
  child.pid = 4321;
  child.exitCode = null;
  child.signalCode = null;
  child.kill = (signal) => {
    setImmediate(() => {
      child.signalCode = signal;
      child.emit("exit", null, signal);
    });
    return true;
  };
  const hostPromise = createBackendHost({
    executablePath: "PeditEduBackend.exe",
    dataDirectory: "C:\\PEDIT\\data",
    sessionContext: safeSessionContext(),
    timeoutMs: 500,
    prepareTimeoutMs: 10,
    stopTimeoutMs: 50,
    spawnImpl: () => child,
    fetchImpl: async () => new Promise(() => {}),
    forceKillImpl: async () => {
      setImmediate(() => {
        child.signalCode = "SIGKILL";
        child.emit("exit", null, "SIGKILL");
      });
    }
  });
  child.stdout.emit("data", Buffer.from(JSON.stringify({
    type: "backend.ready",
    protocolVersion: 1,
    host: "127.0.0.1",
    port: 49158,
    pid: 4321
  }) + "\n"));
  const host = await hostPromise;

  await host.stop();

  assert.equal(child.signalCode, "SIGKILL");
});
