"use strict";

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("peditLauncher", Object.freeze({
  getStatus: () => ipcRenderer.invoke("launcher:status")
}));
