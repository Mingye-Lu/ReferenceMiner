const { app, BrowserWindow, dialog } = require("electron")
const { spawn, exec } = require("child_process")
const http = require("http")
const os = require("os")
const path = require("path")
const fs = require("fs")

const DEFAULT_PORT = 8000

let mainWindow = null
let backendProcess = null
let backendPort = DEFAULT_PORT

function resolveBaseDir() {
  const appPath = app.getAppPath()
  const candidates = [
    appPath,
    path.resolve(appPath, ".."),
    path.resolve(appPath, "..", ".."),
  ]
  for (const candidate of candidates) {
    if (fs.existsSync(path.join(candidate, "src"))) {
      return candidate
    }
  }
  return appPath
}

function resolvePythonCommand() {
  return process.env.REFMINER_PYTHON || "python"
}

function resolveBackendExecutable() {
  const exePath = path.join(process.resourcesPath, "backend", "ReferenceMiner.exe")
  return fs.existsSync(exePath) ? exePath : null
}

function waitForServer(url, timeoutMs = 20000) {
  const start = Date.now()
  return new Promise((resolve, reject) => {
    const tick = () => {
      const req = http.get(url, (res) => {
        res.resume()
        if (res.statusCode && res.statusCode < 500) {
          resolve()
          return
        }
        if (Date.now() - start > timeoutMs) {
          reject(new Error("Timed out waiting for backend"))
          return
        }
        setTimeout(tick, 500)
      })
      req.on("error", () => {
        if (Date.now() - start > timeoutMs) {
          reject(new Error("Timed out waiting for backend"))
          return
        }
        setTimeout(tick, 500)
      })
    }
    tick()
  })
}

function startBackend(port) {
  const baseDir = resolveBaseDir()
  const isPackaged = app.isPackaged
  let command = null
  let args = []
  let cwd = baseDir
  let dataDir = baseDir

  if (isPackaged) {
    const exePath = resolveBackendExecutable()
    if (!exePath) {
      dialog.showErrorBox("Backend Error", "Bundled backend was not found.")
      return
    }
    cwd = path.dirname(exePath)
    // Use user data directory for references and index (writable location)
    dataDir = app.getPath("userData")
    // Use cmd /k to keep terminal open for debugging
    command = "cmd"
    args = ["/k", exePath]
  } else {
    command = resolvePythonCommand()
    args = ["-m", "uvicorn", "refminer.server:app", "--app-dir", "src", "--port", String(port)]
  }

  backendProcess = spawn(command, args, {
    cwd,
    windowsHide: false,
    stdio: "inherit",
    env: {
      ...process.env,
      REFMINER_PORT: String(port),
      REFMINER_PARENT_PID: String(process.pid),
      REFMINER_DATA_DIR: dataDir,
    },
  })

  backendProcess.on("error", (err) => {
    dialog.showErrorBox("Backend Error", `Failed to start backend: ${err.message}`)
  })
}

function stopBackend() {
  if (!backendProcess || backendProcess.killed) {
    if (os.platform() === "win32") {
      killPortProcess(backendPort)
    }
    return
  }
  const pid = backendProcess.pid
  if (!pid) {
    if (os.platform() === "win32") {
      killPortProcess(backendPort)
    }
    return
  }
  if (os.platform() === "win32") {
    spawn("taskkill", ["/PID", String(pid), "/T", "/F"], { windowsHide: true })
    killPortProcess(backendPort)
  } else {
    backendProcess.kill("SIGTERM")
  }
}

function killPortProcess(port) {
  const cmd = `for /f "tokens=5" %a in ('netstat -ano ^| findstr :${port} ^| findstr LISTENING') do taskkill /F /PID %a`
  exec(`cmd.exe /c "${cmd}"`, { windowsHide: true })
}

async function createWindow() {
  const port = Number(process.env.REFMINER_PORT || DEFAULT_PORT)
  backendPort = port
  startBackend(port)

  try {
    await waitForServer(`http://127.0.0.1:${port}/`)
  } catch (err) {
    dialog.showErrorBox("Backend Timeout", err.message || "Backend did not start in time.")
  }

  mainWindow = new BrowserWindow({
    width: 1280,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    show: false,
    backgroundColor: "#0c0f14",
    autoHideMenuBar: false,
    icon: path.join(__dirname, "..", "icon.png"),
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, "preload.cjs"),
    },
  })

  mainWindow.once("ready-to-show", () => {
    mainWindow.show()
  })

  mainWindow.on("closed", () => {
    stopBackend()
    mainWindow = null
  })

  const appUrl = `http://127.0.0.1:${port}/`
  await mainWindow.loadURL(appUrl)
}

app.whenReady().then(createWindow)

app.on("window-all-closed", () => {
  stopBackend()
  if (process.platform !== "darwin") {
    app.quit()
  }
})

app.on("before-quit", () => {
  stopBackend()
})

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow()
  }
})
