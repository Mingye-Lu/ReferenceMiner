const { app, BrowserWindow, dialog, ipcMain, shell } = require("electron")
const { execFile } = require("child_process")
const crypto = require("crypto")
const fs = require("fs")
const fsp = require("fs/promises")
const path = require("path")

const PRODUCT_NAME = "ReferenceMiner"
const INSTALL_LOG_NAME = "install-log.json"

function getInstallerVersion() {
  try {
    const packagePath = path.join(__dirname, "package.json")
    const pkg = JSON.parse(fs.readFileSync(packagePath, "utf-8"))
    return pkg.version || "unknown"
  } catch {
    return "unknown"
  }
}

let mainWindow = null
let currentLogPath = null

function getPayloadRoot() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, "payload")
  }
  return path.join(__dirname, "payload")
}

function getDefaultInstallDir() {
  return path.join(app.getPath("localAppData"), PRODUCT_NAME)
}

async function ensureDir(dirPath) {
  await fsp.mkdir(dirPath, { recursive: true })
}

function sendProgress(payload) {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send("installer:progress", payload)
  }
}

function appendLog(line) {
  if (!currentLogPath) {
    return
  }
  const entry = `[${new Date().toISOString()}] ${line}\n`
  fs.appendFileSync(currentLogPath, entry)
  sendProgress({ type: "log", message: line })
}

function withLogContext() {
  const logDir = path.join(app.getPath("userData"), "logs")
  if (!fs.existsSync(logDir)) {
    fs.mkdirSync(logDir, { recursive: true })
  }
  currentLogPath = path.join(logDir, `install-${Date.now()}.log`)
  return currentLogPath
}

async function readManifest() {
  const manifestPath = path.join(getPayloadRoot(), "manifest.json")
  const raw = await fsp.readFile(manifestPath, "utf-8")
  return JSON.parse(raw)
}

function hashFile(filePath) {
  return new Promise((resolve, reject) => {
    const hash = crypto.createHash("sha256")
    const stream = fs.createReadStream(filePath)
    stream.on("error", reject)
    stream.on("data", (chunk) => hash.update(chunk))
    stream.on("end", () => resolve(hash.digest("hex")))
  })
}

async function verifyPayload(manifest) {
  const root = getPayloadRoot()
  for (const item of manifest.files || []) {
    const sourcePath = path.join(root, item.path)
    const digest = await hashFile(sourcePath)
    if (digest.toLowerCase() !== String(item.sha256).toLowerCase()) {
      throw new Error(`Payload hash mismatch: ${item.path}`)
    }
  }
}

async function copyPayload(manifest, installDir) {
  const root = getPayloadRoot()
  const files = manifest.files || []
  if (files.length === 0) {
    return
  }
  for (const [index, item] of files.entries()) {
    const sourcePath = path.join(root, item.path)
    const destPath = path.join(installDir, item.path)
    await ensureDir(path.dirname(destPath))
    await fsp.copyFile(sourcePath, destPath)
    const progress = Math.round(((index + 1) / files.length) * 100)
    sendProgress({ type: "step", message: `Copying ${item.path}`, progress })
  }
}

function execPowerShell(script) {
  return new Promise((resolve, reject) => {
    execFile(
      "powershell",
      ["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
      { windowsHide: true },
      (error, stdout, stderr) => {
        if (error) {
          reject(new Error(stderr || error.message))
          return
        }
        resolve(stdout)
      }
    )
  })
}

async function getFreeBytes(dir) {
  if (process.platform !== "win32") {
    return null
  }
  const root = path.parse(dir).root
  const driveLetter = root.replace(":", "").replace("\\", "")
  if (!driveLetter) {
    return null
  }
  const result = await execPowerShell(`(Get-PSDrive -Name ${driveLetter}).Free`)
  const value = Number(String(result).trim())
  return Number.isFinite(value) ? value : null
}

function getPayloadSize(manifest) {
  return (manifest.files || []).reduce((total, item) => total + (item.size || 0), 0)
}

async function createShortcut({ linkPath, targetPath, workingDir, iconPath }) {
  const ps = [
    "$ws = New-Object -ComObject WScript.Shell",
    `$sc = $ws.CreateShortcut("${linkPath}")`,
    `$sc.TargetPath = "${targetPath}"`,
    `$sc.WorkingDirectory = "${workingDir}"`,
    iconPath ? `$sc.IconLocation = "${iconPath}"` : "",
    "$sc.Save()",
  ]
    .filter(Boolean)
    .join("; ")
  await execPowerShell(ps)
}

async function removeShortcut(linkPath) {
  if (fs.existsSync(linkPath)) {
    await fsp.unlink(linkPath)
  }
}

async function writeUninstallEntry(installDir, displayVersion) {
  const uninstallExe = path.join(installDir, `${PRODUCT_NAME} Installer.exe`)
  const uninstallCmd = `"${uninstallExe}" --mode=uninstall --target="${installDir}"`
  const key = `HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${PRODUCT_NAME}`
  const commands = [
    `reg add "${key}" /f`,
    `reg add "${key}" /v DisplayName /t REG_SZ /d "${PRODUCT_NAME}" /f`,
    `reg add "${key}" /v DisplayVersion /t REG_SZ /d "${displayVersion}" /f`,
    `reg add "${key}" /v InstallLocation /t REG_SZ /d "${installDir}" /f`,
    `reg add "${key}" /v UninstallString /t REG_SZ /d "${uninstallCmd}" /f`,
  ]
  for (const cmd of commands) {
    await execPowerShell(cmd)
  }
}

async function removeUninstallEntry() {
  const key = `HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${PRODUCT_NAME}`
  await execPowerShell(`reg delete "${key}" /f`)
}

async function writeInstallLog(installDir, manifest, options) {
  const logPath = path.join(installDir, INSTALL_LOG_NAME)
  const data = {
    installedAt: new Date().toISOString(),
    installDir,
    manifest,
    options,
  }
  await fsp.writeFile(logPath, JSON.stringify(data, null, 2))
}

async function readInstallLog(installDir) {
  const logPath = path.join(installDir, INSTALL_LOG_NAME)
  const raw = await fsp.readFile(logPath, "utf-8")
  return JSON.parse(raw)
}

async function removeInstalledFiles(installDir, manifest) {
  const files = (manifest.files || []).slice().reverse()
  for (const item of files) {
    const filePath = path.join(installDir, item.path)
    if (fs.existsSync(filePath)) {
      await fsp.unlink(filePath)
    }
  }
}

async function removeEmptyDirs(rootDir) {
  if (!fs.existsSync(rootDir)) {
    return
  }
  const entries = await fsp.readdir(rootDir, { withFileTypes: true })
  for (const entry of entries) {
    const childPath = path.join(rootDir, entry.name)
    if (entry.isDirectory()) {
      await removeEmptyDirs(childPath)
    }
  }
  const remaining = await fsp.readdir(rootDir)
  if (remaining.length === 0) {
    await fsp.rmdir(rootDir)
  }
}

async function ensureInstallerCached(installDir) {
  if (!app.isPackaged) {
    return
  }
  const installerExe = process.execPath
  const targetExe = path.join(installDir, `${PRODUCT_NAME} Installer.exe`)
  if (!fs.existsSync(targetExe)) {
    await fsp.copyFile(installerExe, targetExe)
  }
}

async function runInstall(options) {
  withLogContext()
  appendLog("Starting install.")
  const manifest = await readManifest()
  sendProgress({ type: "step", message: "Verifying payload", progress: 3 })
  await verifyPayload(manifest)
  appendLog("Payload verified.")

  const installDir = options.installDir || getDefaultInstallDir()
  if (!installDir) {
    throw new Error("Install directory is required.")
  }
  const freeBytes = await getFreeBytes(installDir)
  const payloadSize = getPayloadSize(manifest)
  if (freeBytes !== null && payloadSize > freeBytes) {
    throw new Error("Not enough disk space for the offline payload.")
  }
  await ensureDir(installDir)

  await copyPayload(manifest, installDir)
  appendLog("Payload copied.")

  await ensureInstallerCached(installDir)

  const appExeRel = manifest.entry?.appExe || "app/ReferenceMiner.exe"
  const appExe = path.join(installDir, appExeRel)
  const startMenuDir = path.join(app.getPath("appData"), "Microsoft", "Windows", "Start Menu", "Programs", PRODUCT_NAME)
  const desktopLink = path.join(app.getPath("desktop"), `${PRODUCT_NAME}.lnk`)
  const startMenuLink = path.join(startMenuDir, `${PRODUCT_NAME}.lnk`)

  if (options.createStartMenu) {
    await ensureDir(startMenuDir)
    await createShortcut({
      linkPath: startMenuLink,
      targetPath: appExe,
      workingDir: path.dirname(appExe),
      iconPath: appExe,
    })
    appendLog("Start menu shortcut created.")
  }

  if (options.createDesktop) {
    await createShortcut({
      linkPath: desktopLink,
      targetPath: appExe,
      workingDir: path.dirname(appExe),
      iconPath: appExe,
    })
    appendLog("Desktop shortcut created.")
  }

  await writeUninstallEntry(installDir, manifest.version || getInstallerVersion())
  await writeInstallLog(installDir, manifest, options)
  appendLog("Install log written.")

  sendProgress({ type: "step", message: "Install complete", progress: 100 })
  appendLog("Install complete.")
  return { installDir, appExe }
}

async function runUninstall(options) {
  withLogContext()
  appendLog("Starting uninstall.")
  const installDir = options.installDir || getDefaultInstallDir()
  const logPath = path.join(installDir, INSTALL_LOG_NAME)
  if (!fs.existsSync(logPath)) {
    throw new Error("Install log not found. Cannot safely uninstall.")
  }
  const data = await readInstallLog(installDir)
  const appExeRel = data.manifest?.entry?.appExe || "app/ReferenceMiner.exe"
  const appExe = path.join(installDir, appExeRel)
  const startMenuDir = path.join(app.getPath("appData"), "Microsoft", "Windows", "Start Menu", "Programs", PRODUCT_NAME)
  const desktopLink = path.join(app.getPath("desktop"), `${PRODUCT_NAME}.lnk`)
  const startMenuLink = path.join(startMenuDir, `${PRODUCT_NAME}.lnk`)
  await removeShortcut(desktopLink)
  await removeShortcut(startMenuLink)
  await removeEmptyDirs(startMenuDir)
  await removeInstalledFiles(installDir, data.manifest)
  if (fs.existsSync(appExe)) {
    await fsp.unlink(appExe)
  }
  if (fs.existsSync(logPath)) {
    await fsp.unlink(logPath)
  }
  const cachedInstaller = path.join(installDir, `${PRODUCT_NAME} Installer.exe`)
  if (fs.existsSync(cachedInstaller)) {
    await fsp.unlink(cachedInstaller)
  }
  await removeEmptyDirs(installDir)
  await removeUninstallEntry()
  appendLog("Uninstall complete.")
  return { installDir }
}

async function runRepair(options) {
  withLogContext()
  appendLog("Starting repair.")
  await runInstall(options)
  appendLog("Repair complete.")
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 980,
    height: 700,
    minWidth: 900,
    minHeight: 640,
    show: false,
    backgroundColor: "#0b0f14",
    autoHideMenuBar: true,
    icon: path.join(__dirname, "assets", "icon.png"),
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, "preload.cjs"),
    },
  })

  mainWindow.once("ready-to-show", () => {
    mainWindow.show()
  })

  mainWindow.loadFile(path.join(__dirname, "renderer", "index.html"))
}

ipcMain.handle("installer:get-config", async () => {
  let manifest = null
  let error = null
  let existingInstall = false
  try {
    manifest = await readManifest()
  } catch (err) {
    error = err.message
  }
  const installLogPath = path.join(getDefaultInstallDir(), INSTALL_LOG_NAME)
  existingInstall = fs.existsSync(installLogPath)
  return {
    manifest,
    error,
    defaultInstallDir: getDefaultInstallDir(),
    existingInstall,
  }
})

ipcMain.handle("installer:choose-install-dir", async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ["openDirectory", "createDirectory"],
  })
  if (result.canceled || result.filePaths.length === 0) {
    return null
  }
  return result.filePaths[0]
})

ipcMain.handle("installer:start-install", async (_event, options) => {
  try {
    const result = await runInstall(options)
    if (options.launchAfter && result?.appExe) {
      shell.openPath(result.appExe)
    }
    return { ok: true, result }
  } catch (err) {
    appendLog(`Install failed: ${err.message}`)
    return { ok: false, error: err.message }
  }
})

ipcMain.handle("installer:start-uninstall", async (_event, options) => {
  try {
    const result = await runUninstall(options)
    return { ok: true, result }
  } catch (err) {
    appendLog(`Uninstall failed: ${err.message}`)
    return { ok: false, error: err.message }
  }
})

ipcMain.handle("installer:start-repair", async (_event, options) => {
  try {
    const result = await runRepair(options)
    return { ok: true, result }
  } catch (err) {
    appendLog(`Repair failed: ${err.message}`)
    return { ok: false, error: err.message }
  }
})

ipcMain.handle("installer:open-logs", async () => {
  const logDir = path.join(app.getPath("userData"), "logs")
  await shell.openPath(logDir)
})

ipcMain.handle("installer:launch-app", async (_event, appExe) => {
  if (!appExe) {
    return false
  }
  await shell.openPath(appExe)
  return true
})

app.whenReady().then(createWindow)

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit()
  }
})
