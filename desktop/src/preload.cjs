const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("companyAIUpdates", {
  checkNow: () => ipcRenderer.invoke("updates:check-now"),
});
