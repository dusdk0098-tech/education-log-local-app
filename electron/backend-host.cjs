"use strict";

const crypto = require("node:crypto");
const { execFile, spawn } = require("node:child_process");
const path = require("node:path");

const READY_LIMIT = 16_384;
const SAFE_SESSION_FIELDS = ["userId", "workspaceId", "roles", "scopes", "expiresAt", "deviceId", "dataScopeId"];

function safeSessionContext(sessionContext) {
  const safeContext = {};
  for (const key of SAFE_SESSION_FIELDS) {
    if (sessionContext[key] !== undefined) safeContext[key] = sessionContext[key];
  }
  return safeContext;
}

function buildBootstrapPayload(dataDirectory, sessionContext) {
  return {
    dataDir: dataDirectory,
    backendSecret: crypto.randomBytes(32).toString("hex"),
    sessionContext: safeSessionContext(sessionContext)
  };
}

function backendError(code) {
  const error = new Error(code);
  error.code = code;
  return error;
}

function parseReadyLine(raw) {
  if (!Buffer.isBuffer(raw)) raw = Buffer.from(raw);
  if (raw.length > READY_LIMIT) throw backendError("BACKEND_READY_TOO_LARGE");
  let text = raw.toString("utf8");
  if (text.endsWith("\n")) text = text.slice(0, -1);
  if (!text || text.includes("\n") || text.includes("\r")) throw backendError("BACKEND_READY_INVALID_FRAME");
  let payload;
  try {
    payload = JSON.parse(text);
  } catch {
    throw backendError("BACKEND_READY_INVALID_JSON");
  }
  if (
    payload?.type !== "backend.ready"
    || payload.protocolVersion !== 1
    || payload.host !== "127.0.0.1"
    || !Number.isInteger(payload.port)
    || payload.port < 1
    || payload.port > 65_535
    || !Number.isInteger(payload.pid)
    || payload.pid < 1
  ) {
    throw backendError("BACKEND_READY_INVALID");
  }
  return { ...payload, origin: `http://127.0.0.1:${payload.port}` };
}

function hasExited(child) {
  return child.exitCode != null || child.signalCode != null;
}

function waitForExit(child, timeoutMs) {
  if (hasExited(child)) return Promise.resolve(true);
  return new Promise((resolve) => {
    let settled = false;
    const finish = (exited) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      child.off?.("exit", onExit);
      resolve(exited);
    };
    const onExit = () => finish(true);
    const timer = setTimeout(() => finish(false), timeoutMs);
    child.once("exit", onExit);
  });
}

function withTimeout(operation, timeoutMs, code) {
  return new Promise((resolve, reject) => {
    let settled = false;
    const finish = (callback, value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      callback(value);
    };
    const timer = setTimeout(() => finish(reject, backendError(code)), timeoutMs);
    Promise.resolve(operation).then(
      (value) => finish(resolve, value),
      (error) => finish(reject, error)
    );
  });
}

function forceKillProcessTree(pid, execFileImpl = execFile) {
  if (process.platform !== "win32") {
    try {
      process.kill(pid, "SIGKILL");
      return Promise.resolve();
    } catch {
      return Promise.reject(backendError("BACKEND_FORCE_KILL_FAILED"));
    }
  }
  return new Promise((resolve, reject) => {
    execFileImpl(
      "taskkill.exe",
      ["/PID", String(pid), "/T", "/F"],
      { windowsHide: true, shell: false },
      (error) => error
        ? reject(backendError("BACKEND_FORCE_KILL_FAILED"))
        : resolve()
    );
  });
}

function inspectWindowsProcess(pid, execFileImpl = execFile) {
  return new Promise((resolve, reject) => {
    execFileImpl(
      "powershell.exe",
      [
        "-NoProfile",
        "-Command",
        "$pidValue=[int]$env:PEDIT_BACKEND_PID;$p=Get-CimInstance Win32_Process -Filter \"ProcessId = $pidValue\";if($null -eq $p){exit 4};[pscustomobject]@{parentPid=[int]$p.ParentProcessId;executablePath=[string]$p.ExecutablePath}|ConvertTo-Json -Compress",
      ],
      { windowsHide: true, shell: false, env: { ...process.env, PEDIT_BACKEND_PID: String(pid) } },
      (error, stdout) => {
        if (error) return reject(backendError("BACKEND_PROCESS_INSPECTION_FAILED"));
        try {
          resolve(JSON.parse(stdout));
        } catch {
          reject(backendError("BACKEND_PROCESS_INSPECTION_FAILED"));
        }
      },
    );
  });
}

async function validateReadyProcess(spawnPid, readyPid, executablePath, inspectImpl = inspectWindowsProcess) {
  if (readyPid === spawnPid) return true;
  if (process.platform !== "win32") return false;
  const inspected = await inspectImpl(readyPid);
  return inspected.parentPid === spawnPid
    && path.win32.resolve(inspected.executablePath).toLowerCase()
      === path.win32.resolve(executablePath).toLowerCase();
}

function isWindowsProcessRunning(pid, execFileImpl = execFile) {
  return new Promise((resolve) => {
    execFileImpl(
      "powershell.exe",
      ["-NoProfile", "-Command", "$id=[int]$env:PEDIT_BACKEND_PID;exit $(if(Get-Process -Id $id -ErrorAction SilentlyContinue){0}else{1})"],
      { windowsHide: true, shell: false, env: { ...process.env, PEDIT_BACKEND_PID: String(pid) } },
      (error) => resolve(!error),
    );
  });
}

async function cleanupStartFailure(pids, options, child) {
  if (options.spawnImpl && !options.startCleanupKillImpl && !options.startProcessExistsImpl) {
    try { child.kill("SIGKILL"); } catch {}
    return;
  }
  const killImpl = options.startCleanupKillImpl || options.forceKillImpl || forceKillProcessTree;
  const existsImpl = options.startProcessExistsImpl || isWindowsProcessRunning;
  const uniquePids = [...new Set(pids.filter((pid) => Number.isInteger(pid) && pid > 0))];
  for (const pid of uniquePids) {
    if (!await existsImpl(pid)) continue;
    await killImpl(pid).catch(async (error) => {
      if (await existsImpl(pid)) throw error;
    });
  }
  const deadline = Date.now() + (options.startCleanupTimeoutMs || 3_000);
  while (Date.now() < deadline) {
    if (!(await Promise.all(uniquePids.map((pid) => existsImpl(pid)))).some(Boolean)) return;
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  throw backendError("BACKEND_START_CLEANUP_FAILED");
}

function createBackendHost(options) {
  const spawnImpl = options.spawnImpl || spawn;
  const fetchImpl = options.fetchImpl || globalThis.fetch;
  const bootstrap = buildBootstrapPayload(options.dataDirectory, options.sessionContext);
  const child = spawnImpl(options.executablePath, ["--launcher-host", "--port", "0", "--no-browser"], {
    windowsHide: true,
    shell: false,
    stdio: ["pipe", "pipe", "pipe"]
  });
  child.stdin.end(`${JSON.stringify(bootstrap)}\n`);
  return new Promise((resolve, reject) => {
    let settled = false;
    let failing = false;
    let readyResolved = false;
    let readyProcessPid = null;
    let stopping = false;
    let output = Buffer.alloc(0);
    const finishError = (error) => {
      if (settled || failing) return;
      failing = true;
      settled = true;
      clearTimeout(timer);
      void cleanupStartFailure([child.pid, readyProcessPid], options, child).then(
        () => reject(error),
        (cleanupError) => reject(cleanupError),
      );
    };
    const timer = setTimeout(() => finishError(backendError("BACKEND_READY_TIMEOUT")), options.timeoutMs || 30_000);
    timer.unref?.();
    child.once("error", () => finishError(backendError("BACKEND_START_FAILED")));
    child.once("exit", (code) => {
      if (readyResolved) {
        if (!stopping) Promise.resolve(options.onUnexpectedExit?.("BACKEND_EXITED")).catch(() => {});
        return;
      }
      const reason = code === 42 ? "LEGACY_DATABASE_RECOVERY_REQUIRED" : "BACKEND_EXITED_BEFORE_READY";
      finishError(backendError(reason));
    });
    child.stderr?.on("data", () => {});
    child.stdout.on("data", (chunk) => {
      if (settled) return;
      output = Buffer.concat([output, Buffer.from(chunk)]);
      if (output.length > READY_LIMIT) return finishError(backendError("BACKEND_READY_TOO_LARGE"));
      const newline = output.indexOf(0x0a);
      if (newline < 0) return;
      if (newline !== output.length - 1) return finishError(backendError("BACKEND_READY_INVALID_FRAME"));
      try {
        const ready = parseReadyLine(output);
        readyProcessPid = ready.pid;
        const validateReadyPidImpl = options.validateReadyPidImpl || validateReadyProcess;
        void Promise.resolve(validateReadyPidImpl(child.pid, ready.pid, options.executablePath)).then((valid) => {
          if (!valid) return finishError(backendError("BACKEND_READY_PID_MISMATCH"));
          if (settled) return;
          settled = true;
          readyResolved = true;
          clearTimeout(timer);
          let stopPromise = null;
          const forceKillImpl = options.forceKillImpl || forceKillProcessTree;
          resolve({
          ...ready,
          child,
          backendPid: ready.pid,
          secret: bootstrap.backendSecret,
          renewSession: async (sessionContext) => {
            const response = await fetchImpl(`${ready.origin}/__launcher/session/renew`, {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                Origin: ready.origin,
                "X-Pedit-Backend-Session": bootstrap.backendSecret
              },
              body: JSON.stringify(safeSessionContext(sessionContext))
            });
            if (!response.ok) throw backendError("BACKEND_SESSION_RENEW_FAILED");
          },
          stop: async () => {
            if (stopPromise) return stopPromise;
            stopPromise = (async () => {
              stopping = true;
              if (hasExited(child)) return;
              let shutdownPrepared = false;
              try {
                const response = await withTimeout(
                  fetchImpl(`${ready.origin}/__launcher/shutdown/prepare`, {
                    method: "POST",
                    headers: {
                      "Content-Type": "application/json",
                      Origin: ready.origin,
                      "X-Pedit-Backend-Session": bootstrap.backendSecret
                    },
                    body: "{}"
                  }),
                  options.prepareTimeoutMs || 1_000,
                  "BACKEND_SHUTDOWN_PREPARE_TIMEOUT"
                );
                shutdownPrepared = response.ok === true;
              } catch {}
              if (hasExited(child)) return;
              if (
                shutdownPrepared
                && await waitForExit(child, options.stopTimeoutMs || 3_000)
              ) return;
              if (process.platform !== "win32") {
                child.kill("SIGTERM");
                if (await waitForExit(child, options.stopTimeoutMs || 3_000)) return;
              }
              if (hasExited(child)) return;
              try {
                await forceKillImpl(child.pid);
              } catch (error) {
                if (!hasExited(child)) throw error;
              }
              if (!await waitForExit(child, options.forceWaitTimeoutMs || 2_000)) {
                throw backendError("BACKEND_STOP_TIMEOUT");
              }
            })();
            return stopPromise;
          }
          });
        }).catch(() => finishError(backendError("BACKEND_READY_PID_VALIDATION_FAILED")));
      } catch (error) {
        finishError(error);
      }
    });
  });
}

module.exports = {
  READY_LIMIT,
  buildBootstrapPayload,
  createBackendHost,
  forceKillProcessTree,
  inspectWindowsProcess,
  parseReadyLine,
  validateReadyProcess,
  waitForExit,
  withTimeout
};
