"use strict";

async function shutdownApplication(options) {
  await options.closeBusinessSurface();
  await options.stopBackend();
}

module.exports = { shutdownApplication };
