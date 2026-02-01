const state = {
  manifest: null,
  installDir: "",
  existingInstall: false,
  installResult: null,
};

const elements = {
  statusMessage: document.getElementById("statusMessage"),
  versionLabel: document.getElementById("versionLabel"),
  installDir: document.getElementById("installDir"),
  browseDir: document.getElementById("browseDir"),
  nextToOptions: document.getElementById("nextToOptions"),
  backToLocation: document.getElementById("backToLocation"),
  nextToInstall: document.getElementById("nextToInstall"),
  cancelInstall: document.getElementById("cancelInstall"),
  progressFill: document.getElementById("progressFill"),
  progressLabel: document.getElementById("progressLabel"),
  logBox: document.getElementById("logBox"),
  finalPath: document.getElementById("finalPath"),
  finalVersion: document.getElementById("finalVersion"),
  finishClose: document.getElementById("finishClose"),
  finishLaunch: document.getElementById("finishLaunch"),
  openLogs: document.getElementById("openLogs"),
  optDesktop: document.getElementById("optDesktop"),
  optStartMenu: document.getElementById("optStartMenu"),
  optLaunch: document.getElementById("optLaunch"),
  existingInstall: document.getElementById("existingInstall"),
  repairInstall: document.getElementById("repairInstall"),
  uninstallInstall: document.getElementById("uninstallInstall"),
};

const panes = ["pane-1", "pane-2", "pane-3", "pane-4"].map((id) =>
  document.getElementById(id),
);

function setStep(step) {
  panes.forEach((pane, index) => {
    pane.classList.toggle("active", index === step - 1);
  });
  document.querySelectorAll(".step").forEach((item) => {
    item.classList.toggle("active", Number(item.dataset.step) === step);
  });
}

function setStatus(message) {
  elements.statusMessage.textContent = message;
}

function addLog(message) {
  const line = document.createElement("div");
  line.textContent = message;
  elements.logBox.appendChild(line);
  elements.logBox.scrollTop = elements.logBox.scrollHeight;
}

function clearLog() {
  elements.logBox.textContent = "";
}

async function loadConfig() {
  const result = await window.installerApi.getConfig();
  if (result.error) {
    setStatus(result.error);
    return;
  }
  state.manifest = result.manifest;
  state.installDir = result.defaultInstallDir;
  state.existingInstall = result.existingInstall;
  elements.installDir.value = state.installDir;
  elements.versionLabel.textContent = `v${state.manifest?.version || "unknown"}`;
  if (state.existingInstall) {
    elements.existingInstall.classList.remove("hidden");
  }
}

async function chooseDir() {
  const result = await window.installerApi.chooseInstallDir();
  if (result) {
    state.installDir = result;
    elements.installDir.value = result;
  }
}

async function startInstall() {
  setStep(3);
  setStatus("Installing ReferenceMiner...");
  elements.nextToInstall.disabled = true;
  clearLog();
  elements.progressFill.style.width = "0%";
  elements.progressLabel.textContent = "Preparing install...";
  const options = {
    installDir: elements.installDir.value,
    createDesktop: elements.optDesktop.checked,
    createStartMenu: elements.optStartMenu.checked,
    launchAfter: elements.optLaunch.checked,
  };
  const result = await window.installerApi.startInstall(options);
  if (!result.ok) {
    setStatus("Install failed.");
    elements.progressLabel.textContent = result.error || "Install failed.";
    elements.nextToInstall.disabled = false;
    return;
  }
  state.installResult = result.result;
  elements.finalPath.textContent = result.result.installDir;
  elements.finalVersion.textContent = state.manifest?.version || "unknown";
  elements.finishLaunch.disabled = !result.result.appExe;
  setStatus("Install complete.");
  setStep(4);
}

async function startRepair() {
  setStep(3);
  setStatus("Repairing ReferenceMiner...");
  elements.nextToInstall.disabled = true;
  clearLog();
  const options = { installDir: elements.installDir.value };
  const result = await window.installerApi.startRepair(options);
  if (!result.ok) {
    setStatus("Repair failed.");
    elements.progressLabel.textContent = result.error || "Repair failed.";
    elements.nextToInstall.disabled = false;
    return;
  }
  setStatus("Repair complete.");
  setStep(4);
}

async function startUninstall() {
  setStep(3);
  setStatus("Uninstalling ReferenceMiner...");
  elements.nextToInstall.disabled = true;
  clearLog();
  const options = { installDir: elements.installDir.value };
  const result = await window.installerApi.startUninstall(options);
  if (!result.ok) {
    setStatus("Uninstall failed.");
    elements.progressLabel.textContent = result.error || "Uninstall failed.";
    elements.nextToInstall.disabled = false;
    return;
  }
  setStatus("Uninstall complete.");
  elements.progressLabel.textContent = "ReferenceMiner was removed.";
}

function bindEvents() {
  elements.browseDir.addEventListener("click", chooseDir);
  elements.nextToOptions.addEventListener("click", () => setStep(2));
  elements.backToLocation.addEventListener("click", () => setStep(1));
  elements.nextToInstall.addEventListener("click", startInstall);
  elements.cancelInstall.addEventListener("click", () => window.close());
  elements.finishClose.addEventListener("click", () => window.close());
  elements.finishLaunch.addEventListener("click", () => {
    if (state.installResult?.appExe) {
      window.installerApi.launchApp(state.installResult.appExe);
    }
  });
  elements.openLogs.addEventListener("click", () =>
    window.installerApi.openLogs(),
  );
  elements.repairInstall.addEventListener("click", startRepair);
  elements.uninstallInstall.addEventListener("click", startUninstall);
}

window.installerApi.onProgress((payload) => {
  if (payload.type === "step") {
    elements.progressLabel.textContent = payload.message;
    elements.progressFill.style.width = `${payload.progress || 0}%`;
    setStatus(payload.message);
  }
  if (payload.type === "log") {
    addLog(payload.message);
  }
});

bindEvents();
loadConfig();
setStep(1);
elements.finishLaunch.disabled = true;
