"use strict";

function createFailClosedController(options) {
  let failed = false;
  return {
    async fail(reason) {
      if (failed) return;
      failed = true;
      await options.closeBusinessSurface();
      await options.stopBackend();
      await options.showRestriction(reason);
    },
    get failed() {
      return failed;
    },
    shouldQuitOnWindowAllClosed() {
      return !failed;
    }
  };
}

module.exports = { createFailClosedController };
