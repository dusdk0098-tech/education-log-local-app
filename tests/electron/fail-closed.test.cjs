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
