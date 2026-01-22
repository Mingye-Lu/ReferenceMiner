const { contextBridge, ipcRenderer } = require("electron")

contextBridge.exposeInMainWorld("installerApi", {
  getConfig: () => ipcRenderer.invoke("installer:get-config"),
  chooseInstallDir: () => ipcRenderer.invoke("installer:choose-install-dir"),
  startInstall: (options) => ipcRenderer.invoke("installer:start-install", options),
  startUninstall: (options) => ipcRenderer.invoke("installer:start-uninstall", options),
  startRepair: (options) => ipcRenderer.invoke("installer:start-repair", options),
  openLogs: () => ipcRenderer.invoke("installer:open-logs"),
  launchApp: (appExe) => ipcRenderer.invoke("installer:launch-app", appExe),
  onProgress: (callback) => {
    ipcRenderer.on("installer:progress", (_event, payload) => callback(payload))
  },
})
