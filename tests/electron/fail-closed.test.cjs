const assert = require("node:assert/strict");
const test = require("node:test");

const { createFailClosedController } = require("../../electron/fail-closed.cjs");

test("backend exit closes business surface and shows restriction once", async () => {
  const events = [];
  const controller = createFailClosedController({
    closeBusinessSurface: async () => events.push("close"),
    stopBackend: async () => events.push("stop"),
    showRestriction: async (reason) => events.push(`restricted:${reason}`)
  });
  await controller.fail("BACKEND_EXITED");
  await controller.fail("BACKEND_EXITED_AGAIN");
  assert.deepEqual(events, ["close", "stop", "restricted:BACKEND_EXITED"]);
});

test("fail-closed transition suppresses window-all-closed quit until restriction is shown", async () => {
  const events = [];
  let releaseClose;
  const closePending = new Promise((resolve) => {
    releaseClose = resolve;
  });
  const controller = createFailClosedController({
    closeBusinessSurface: async () => {
      events.push("close");
      await closePending;
    },
    stopBackend: async () => events.push("stop"),
    showRestriction: async () => events.push("restricted")
  });

  const transition = controller.fail("LAUNCHER_PIPE_CLOSED");
  assert.equal(controller.shouldQuitOnWindowAllClosed(), false);
  assert.deepEqual(events, ["close"]);

  releaseClose();
  await transition;
  assert.deepEqual(events, ["close", "stop", "restricted"]);
});
