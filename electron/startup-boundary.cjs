"use strict";

function startupError(code) {
  const error = new Error(code);
  error.code = code;
  return error;
}

function startupErrorCode(error) {
  if (error && typeof error.code === "string" && /^[A-Z][A-Z0-9_]+$/.test(error.code)) {
    return error.code;
  }
  return "APP_START_FAILED";
}

function withStartupTimeout(operation, timeoutMs, code) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(startupError(code)), timeoutMs);
    Promise.resolve(operation).then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      () => {
        clearTimeout(timer);
        reject(startupError(code));
      },
    );
  });
}

async function reportStartupFailure(runtime, failClosed, error) {
  const code = startupErrorCode(error);
  if (runtime?.status?.mode === "connected") {
    await runtime.connection.reportError("APP-001", code, false).catch(() => undefined);
  }
  await failClosed.fail(code);
}

module.exports = { reportStartupFailure, startupError, startupErrorCode, withStartupTimeout };
