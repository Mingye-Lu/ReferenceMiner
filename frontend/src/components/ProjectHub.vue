<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from "vue";
import { useRouter } from "vue-router";
import {
  fetchProjects,
  createProject,
  fetchBankManifest,
  deleteFile,
  deleteProject,
  selectProjectFiles,
  getSettings,
  saveApiKey,
  saveLlmSettings,
  validateApiKey,
  deleteApiKey,
  resetAllData,
  fetchModels,
  reprocessReferenceBankStream,
  reprocessReferenceFileStream,
  fetchVersion,
  fetchUpdateCheck,
} from "../api/client";
import type {
  Project,
  ManifestEntry,
  BalanceInfo,
  Settings as AppSettings,
  UploadQueueItem,
  UploadStatus,
  UploadPhase,
  UpdateCheck,
} from "../types";
import ProjectCard from "./ProjectCard.vue";
import FileUploader from "./FileUploader.vue";
import FilePreviewModal from "./FilePreviewModal.vue";
import ConfirmationModal from "./ConfirmationModal.vue";
import CustomSelect from "./CustomSelect.vue";
import BankFileSelectorModal from "./BankFileSelectorModal.vue";
import {
  Plus,
  Search,
  Loader2,
  Upload,
  FileText,
  Trash2,
  Settings,
  ListOrdered,
} from "lucide-vue-next";
import { type Theme, getStoredTheme, setTheme } from "../utils/theme";
import { getFileName } from "../utils";
import { usePdfSettings } from "../composables/usePdfSettings";

const router = useRouter();
const isDev = import.meta.env.DEV;
const activeTab = ref<"projects" | "bank" | "settings">("projects");
const settingsSection = ref<"preferences" | "advanced">("preferences");
const currentTheme = ref<Theme>("system");
const projects = ref<Project[]>([]);
const bankFiles = ref<ManifestEntry[]>([]);
const loading = ref(true);
const bankLoading = ref(false);
const searchQuery = ref("");
const showCreateModal = ref(false);
const newProjectName = ref("");
const newProjectDesc = ref("");
const creating = ref(false);
const showPreviewModal = ref(false);
const previewFile = ref<ManifestEntry | null>(null);
const showDeleteModal = ref(false);
const fileToDelete = ref<ManifestEntry | null>(null);
const deleting = ref(false);
const showDeleteProjectModal = ref(false);
const projectToDelete = ref<Project | null>(null);
const deletingProject = ref(false);
const showFileSelectorForCreate = ref(false);
const selectedFilesForCreate = ref<Set<string>>(new Set());

// Advanced Settings State
const settings = ref<AppSettings | null>(null);
const apiKeyInput = ref("");
const showApiKey = ref(false);
const isLoadingSettings = ref(false);
const isSaving = ref(false);
const isSavingLlm = ref(false);
const isValidating = ref(false);
const isResetting = ref(false);
const showResetConfirm = ref(false);
const showReprocessConfirm = ref(false);
const validationStatus = ref<"none" | "valid" | "invalid">("none");
const validationError = ref("");
const balanceInfos = ref<BalanceInfo[]>([]);
const balanceAvailable = ref<boolean | null>(null);
const saveError = ref("");
const llmSaveError = ref("");
const llmSaveSuccess = ref("");
const resetError = ref("");
const resetSuccess = ref("");
const baseUrlInput = ref("");
const modelInput = ref("");
const updateInfo = ref<UpdateCheck | null>(null);
const isCheckingUpdate = ref(false);
const updateError = ref("");
const currentVersion = ref<string>("");

// Display Settings
const filesPerPage = ref(7);
const notesPerPage = ref(4);
const chatsPerPage = ref(0); // 0 = unlimited

const { settings: pdfSettings, setViewMode } = usePdfSettings();
const viewMode = computed(() => pdfSettings.value.viewMode);

const providerOptions = [
  { value: "openai", label: "ChatGPT" },
  { value: "gemini", label: "Gemini" },
  { value: "anthropic", label: "Anthropic" },
  { value: "deepseek", label: "DeepSeek" },
  { value: "custom", label: "Custom" },
];
const providerDefaults: Record<string, { baseUrl: string; model: string }> = {
  deepseek: { baseUrl: "https://api.deepseek.com", model: "deepseek-chat" },
  openai: { baseUrl: "https://api.openai.com/v1", model: "gpt-4o-mini" },
  gemini: {
    baseUrl: "https://generativelanguage.googleapis.com/v1beta/openai",
    model: "gemini-1.5-flash",
  },
  anthropic: {
    baseUrl: "https://api.anthropic.com/v1",
    model: "claude-3-haiku-20240307",
  },
  custom: { baseUrl: "https://api.openai.com/v1", model: "gpt-4o-mini" },
};
const providerLinks: Record<string, { url: string; label: string }> = {
  deepseek: {
    url: "https://platform.deepseek.com/api_keys",
    label: "platform.deepseek.com",
  },
  openai: {
    url: "https://platform.openai.com/api-keys",
    label: "platform.openai.com",
  },
  gemini: {
    url: "https://aistudio.google.com/app/apikey",
    label: "aistudio.google.com",
  },
  anthropic: {
    url: "https://console.anthropic.com/settings/keys",
    label: "console.anthropic.com",
  },
  custom: { url: "", label: "" },
};
const selectedProvider = ref("custom");
const modelOptions = ref<{ value: string; label: string }[]>([]);
const isLoadingModels = ref(false);
const isReprocessing = ref(false);
const isQueueOpen = ref(false);
const bankQueueItems = ref<UploadQueueItem[]>([]);
const reprocessQueueItems = ref<UploadQueueItem[]>([]);
const queueRef = ref<HTMLElement | null>(null);

const currentProviderKey = computed(() => {
  const provider = selectedProvider.value;
  const entry = settings.value?.providerKeys?.[provider];
  return entry ?? { hasKey: false, maskedKey: null };
});

const currentProviderLink = computed(() => {
  const provider = selectedProvider.value;
  return providerLinks[provider] ?? providerLinks.custom;
});

const apiKeyStatusMessage = computed(() => {
  return balanceAvailable.value === false
    ? "API key is valid, but balance is insufficient"
    : "API key is valid";
});

const currentVersionLabel = computed(() => {
  return (
    currentVersion.value || updateInfo.value?.current?.version || "unknown"
  );
});

const lastCheckedLabel = computed(() => {
  const checkedAt = updateInfo.value?.checkedAt;
  if (!checkedAt) return "";
  return new Date(checkedAt).toLocaleString();
});

const updateBadgeText = computed(() => {
  if (!updateInfo.value) return "Not checked";
  if (updateInfo.value.error) return "Check failed";
  if (!updateInfo.value.latest?.version) return "No release";
  return updateInfo.value.isUpdateAvailable ? "Update available" : "Up to date";
});

const updateBadgeClass = computed(() => {
  if (!updateInfo.value) return "neutral";
  if (updateInfo.value.error) return "error";
  if (!updateInfo.value.latest?.version) return "neutral";
  return updateInfo.value.isUpdateAvailable ? "available" : "current";
});

const themeOptions = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "system", label: "System" },
];

const pdfViewOptions = [
  { value: "single", label: "Single Page" },
  { value: "continuous", label: "Continuous Scroll" },
];

async function loadProjects() {
  try {
    loading.value = true;
    projects.value = await fetchProjects();
  } catch (err) {
    console.error("Failed to load projects:", err);
  } finally {
    loading.value = false;
  }
}

async function loadBankFiles() {
  try {
    bankLoading.value = true;
    bankFiles.value = await fetchBankManifest();
  } catch (err) {
    console.error("Failed to load bank files:", err);
  } finally {
    bankLoading.value = false;
  }
}

async function handleCreate() {
  if (!newProjectName.value.trim()) return;
  try {
    creating.value = true;
    const p = await createProject({
      name: newProjectName.value,
      description: newProjectDesc.value,
    });

    if (selectedFilesForCreate.value.size > 0) {
      try {
        await selectProjectFiles(
          p.id,
          Array.from(selectedFilesForCreate.value),
        );
      } catch (e) {
        console.error("Failed to add initial files", e);
      }
    }

    projects.value.push(p);
    showCreateModal.value = false;
    newProjectName.value = "";
    newProjectDesc.value = "";
    selectedFilesForCreate.value = new Set();

    openProject(p.id);
  } catch (err) {
    console.error("Failed to create project:", err);
  } finally {
    creating.value = false;
  }
}

const sortedBankFiles = computed(() => {
  return [...bankFiles.value].sort((a, b) => {
    const nameA = getFileName(a.relPath).toLowerCase();
    const nameB = getFileName(b.relPath).toLowerCase();
    if (nameA !== nameB) return nameA.localeCompare(nameB);
    return a.relPath.localeCompare(b.relPath);
  });
});

function upsertBankFile(entry: ManifestEntry) {
  const idx = bankFiles.value.findIndex(
    (item) => item.relPath === entry.relPath,
  );
  if (idx === -1) {
    bankFiles.value = [...bankFiles.value, entry];
    return;
  }
  const next = [...bankFiles.value];
  next[idx] = entry;
  bankFiles.value = next;
}

function openFileSelectorForCreate() {
  showFileSelectorForCreate.value = true;
}

function handleInitialFilesSelected(files: string[]) {
  selectedFilesForCreate.value = new Set(files);
  showFileSelectorForCreate.value = false;
}

function openProject(id: string) {
  router.push(`/project/${id}`);
}

function handlePreview(file: ManifestEntry) {
  previewFile.value = file;
  showPreviewModal.value = true;
}

function requestDelete(file: ManifestEntry) {
  fileToDelete.value = file;
  showDeleteModal.value = true;
}

async function confirmDelete() {
  if (!fileToDelete.value) return;
  try {
    deleting.value = true;
    const relPath = fileToDelete.value.relPath;
    bankFiles.value = bankFiles.value.filter(
      (file) => file.relPath !== relPath,
    );
    if (previewFile.value?.relPath === relPath) {
      previewFile.value = null;
    }
    await deleteFile("default", relPath);
    showDeleteModal.value = false;
    fileToDelete.value = null;
  } catch (err) {
    await loadBankFiles();
    console.error("Failed to delete file:", err);
  } finally {
    deleting.value = false;
  }
}

function cancelDelete() {
  showDeleteModal.value = false;
  fileToDelete.value = null;
}

function handleDeleteProject(projectId: string) {
  const project = projects.value.find((p) => p.id === projectId);
  if (project) {
    projectToDelete.value = project;
    showDeleteProjectModal.value = true;
  }
}

async function confirmDeleteProject() {
  if (!projectToDelete.value) return;
  try {
    deletingProject.value = true;
    await deleteProject(projectToDelete.value.id);
    await loadProjects();
    showDeleteProjectModal.value = false;
    projectToDelete.value = null;
  } catch (err) {
    console.error("Failed to delete project:", err);
  } finally {
    deletingProject.value = false;
  }
}

function cancelDeleteProject() {
  showDeleteProjectModal.value = false;
  projectToDelete.value = null;
}

function handleBankQueueUpdated(items: UploadQueueItem[]) {
  bankQueueItems.value = items;
}

const queueItems = computed(() => {
  const combined = [...bankQueueItems.value, ...reprocessQueueItems.value];
  return combined.filter((item) => item.status !== "complete");
});

const queueCount = computed(() => {
  const combined = [...bankQueueItems.value, ...reprocessQueueItems.value];
  return combined.filter(
    (item) =>
      item.status === "pending" ||
      item.status === "uploading" ||
      item.status === "processing",
  ).length;
});

function formatQueueStatus(status: UploadStatus): string {
  switch (status) {
    case "pending":
      return "Pending";
    case "uploading":
      return "Uploading";
    case "processing":
      return "Processing";
    case "complete":
      return "Complete";
    case "error":
      return "Error";
    case "duplicate":
      return "Duplicate";
    default:
      return status;
  }
}

function formatQueuePhase(phase?: string): string {
  if (!phase) return "";
  switch (phase) {
    case "uploading":
      return "Uploading";
    case "hashing":
      return "Hashing";
    case "checking_duplicate":
      return "Checking";
    case "storing":
      return "Storing";
    case "extracting":
      return "Extracting";
    case "indexing":
      return "Indexing";
    case "scanning":
      return "Scanning";
    case "resetting":
      return "Resetting";
    default:
      return phase.replace(/_/g, " ");
  }
}

function upsertReprocessQueueItem(
  relPath: string,
  status: UploadStatus,
  phase?: string,
) {
  const existing = reprocessQueueItems.value.find(
    (item) => item.id === relPath,
  );
  const progress = status === "complete" ? 100 : 0;
  const name = getFileName(relPath);
  if (!existing) {
    reprocessQueueItems.value = [
      ...reprocessQueueItems.value,
      {
        id: relPath,
        name,
        status,
        progress,
        phase: phase as UploadPhase | undefined,
      },
    ];
    return;
  }
  const next = [...reprocessQueueItems.value];
  const idx = next.findIndex((item) => item.id === relPath);
  next[idx] = {
    ...next[idx],
    name,
    status,
    progress,
    phase: phase as UploadPhase | undefined,
  };
  reprocessQueueItems.value = next;
}

function handleOutsideQueueClick(event: MouseEvent) {
  if (!isQueueOpen.value) return;
  const target = event.target as Node | null;
  if (!target) return;
  if (queueRef.value && queueRef.value.contains(target)) return;
  isQueueOpen.value = false;
}

async function handleReprocessConfirm() {
  if (isReprocessing.value) return;
  try {
    isReprocessing.value = true;
    reprocessQueueItems.value = [];
    await reprocessReferenceBankStream({
      onFile: (payload) => {
        if (!payload.relPath) return;
        upsertReprocessQueueItem(
          payload.relPath,
          payload.status as UploadStatus,
          payload.phase,
        );
      },
      onComplete: async () => {
        await loadBankFiles();
      },
      onError: (_code, message) => {
        console.error("Failed to reprocess reference bank:", message);
      },
    });
  } catch (err) {
    console.error("Failed to reprocess reference bank:", err);
  } finally {
    isReprocessing.value = false;
    showReprocessConfirm.value = false;
  }
}

async function handleReprocessFile(file: ManifestEntry) {
  if (isReprocessing.value) return;
  try {
    isReprocessing.value = true;
    upsertReprocessQueueItem(file.relPath, "processing", "extracting");
    await reprocessReferenceFileStream(file.relPath, {
      onFile: (payload) => {
        if (!payload.relPath) return;
        upsertReprocessQueueItem(
          payload.relPath,
          payload.status as UploadStatus,
          payload.phase,
        );
      },
      onComplete: async () => {
        upsertReprocessQueueItem(file.relPath, "complete", undefined);
        await loadBankFiles();
      },
      onError: (_code, message) => {
        console.error("Failed to reprocess file:", message);
        upsertReprocessQueueItem(file.relPath, "error", undefined);
      },
    });
  } catch (err) {
    console.error("Failed to reprocess file:", err);
  } finally {
    isReprocessing.value = false;
  }
}

async function handleUploadComplete(entry: ManifestEntry) {
  upsertBankFile(entry);
}

function handleBeforeLeave(el: Element) {
  const element = el as HTMLElement;
  const parent = element.parentElement;
  if (!parent) return;

  const rect = element.getBoundingClientRect();
  const parentRect = parent.getBoundingClientRect();
  element.style.position = "absolute";
  element.style.top = `${rect.top - parentRect.top}px`;
  element.style.left = `${rect.left - parentRect.left}px`;
  element.style.width = `${rect.width}px`;
  element.style.height = `${rect.height}px`;
}

function switchToBank() {
  activeTab.value = "bank";
  if (bankFiles.value.length === 0) {
    loadBankFiles();
  }
}

async function handleDataReset() {
  // Reload projects list after data reset
  await loadProjects();
  // Reload bank files if currently viewing bank tab
  if (activeTab.value === "bank") {
    await loadBankFiles();
  }
}

// Settings Methods
async function handleValidate() {
  isValidating.value = true;
  validationStatus.value = "none";
  validationError.value = "";
  try {
    const result = await validateApiKey(
      apiKeyInput.value || undefined,
      baseUrlInput.value || settings.value?.baseUrl,
      modelInput.value || settings.value?.model,
      selectedProvider.value,
    );
    validationStatus.value = result.valid ? "valid" : "invalid";
    validationError.value = formatValidationError(result.error);
    balanceInfos.value = result.balanceInfos ?? [];
    balanceAvailable.value =
      typeof result.isAvailable === "boolean" ? result.isAvailable : null;
  } catch (e: any) {
    validationStatus.value = "invalid";
    validationError.value = formatValidationError(
      e.message || "Validation failed",
    );
    balanceInfos.value = [];
    balanceAvailable.value = null;
  } finally {
    isValidating.value = false;
  }
}

async function handleSave() {
  if (!apiKeyInput.value) return;
  isSaving.value = true;
  saveError.value = "";
  try {
    await saveApiKey(apiKeyInput.value, selectedProvider.value);
    settings.value = await getSettings();
    syncLlmInputs(settings.value);
    apiKeyInput.value = "";
    validationStatus.value = "none";
    balanceInfos.value = [];
    balanceAvailable.value = null;
    modelOptions.value = [];
  } catch (e: any) {
    saveError.value = e.message || "Failed to save";
  } finally {
    isSaving.value = false;
  }
}

async function handleDeleteApiKey() {
  isSaving.value = true;
  try {
    await deleteApiKey(selectedProvider.value);
    settings.value = await getSettings();
    syncLlmInputs(settings.value);
    validationStatus.value = "none";
    apiKeyInput.value = "";
    balanceInfos.value = [];
    balanceAvailable.value = null;
    modelOptions.value = [];
  } catch (e) {
    console.error("Failed to delete API key:", e);
  } finally {
    isSaving.value = false;
  }
}

function handleResetClick() {
  showResetConfirm.value = true;
  resetError.value = "";
  resetSuccess.value = "";
}

async function handleSaveLlmSettings() {
  const baseUrl = baseUrlInput.value.trim();
  const model = modelInput.value.trim();
  llmSaveError.value = "";
  llmSaveSuccess.value = "";
  if (!baseUrl || !model) {
    llmSaveError.value = "Base URL and model are required";
    return;
  }
  isSavingLlm.value = true;
  try {
    const result = await saveLlmSettings(
      baseUrl,
      model,
      selectedProvider.value,
    );
    if (!settings.value) {
      settings.value = {
        activeProvider: result.activeProvider,
        providerKeys: {},
        providerSettings: {},
        baseUrl: result.baseUrl,
        model: result.model,
      };
    } else {
      settings.value.activeProvider = result.activeProvider;
      settings.value.baseUrl = result.baseUrl;
      settings.value.model = result.model;
    }
    if (settings.value) {
      if (!settings.value.providerSettings) {
        settings.value.providerSettings = {};
      }
      settings.value.providerSettings[selectedProvider.value] = {
        baseUrl: result.baseUrl,
        model: result.model,
      };
    }
    baseUrlInput.value = result.baseUrl;
    modelInput.value = result.model;
    llmSaveSuccess.value = "Endpoint and model saved";
    validationStatus.value = "none";
    validationError.value = "";
  } catch (e: any) {
    llmSaveError.value = e.message || "Failed to save LLM settings";
  } finally {
    isSavingLlm.value = false;
  }
}

async function handleResetConfirm() {
  isResetting.value = true;
  resetError.value = "";
  resetSuccess.value = "";
  try {
    const result = await resetAllData();
    resetSuccess.value = result.message;
    showResetConfirm.value = false;
    await handleDataReset();
  } catch (e: any) {
    resetError.value = e.message || "Failed to reset data";
  } finally {
    isResetting.value = false;
  }
}

async function handleLoadModels() {
  isLoadingModels.value = true;
  llmSaveError.value = "";
  llmSaveSuccess.value = "";
  try {
    const models = await fetchModels(
      apiKeyInput.value || undefined,
      baseUrlInput.value || settings.value?.baseUrl,
      selectedProvider.value,
    );
    modelOptions.value = models
      .filter((id) => typeof id === "string" && id.trim())
      .map((id) => ({ value: id, label: id }));
    if (!modelOptions.value.length) {
      llmSaveError.value = "No models returned for this endpoint";
    }
  } catch (e: any) {
    llmSaveError.value = e.message || "Failed to load models";
  } finally {
    isLoadingModels.value = false;
  }
}

async function handleUpdateCheck() {
  isCheckingUpdate.value = true;
  updateError.value = "";
  try {
    updateInfo.value = await fetchUpdateCheck();
    if (updateInfo.value?.error) {
      updateError.value = updateInfo.value.error;
    }
  } catch (e: any) {
    updateError.value = e.message || "Failed to check for updates";
  } finally {
    isCheckingUpdate.value = false;
  }
}

onMounted(() => {
  if (!isDev) {
    handleUpdateCheck();
  }
});

function formatValidationError(error?: string): string {
  if (!error) return "";
  const trimmed = error.trim();
  const jsonStart = trimmed.indexOf("{");
  if (jsonStart !== -1) {
    const maybeJson = trimmed.slice(jsonStart);
    try {
      const parsed = JSON.parse(maybeJson);
      const message = parsed?.error?.message;
      if (typeof message === "string" && message.trim()) {
        return message.trim();
      }
    } catch {
      // Ignore JSON parsing errors
    }
  }
  return trimmed;
}

function setProvider(provider: string) {
  selectedProvider.value = provider;
  const defaults = providerDefaults[provider] ?? providerDefaults.custom;
  const stored = settings.value?.providerSettings?.[provider];
  baseUrlInput.value = stored?.baseUrl || defaults.baseUrl;
  modelInput.value = stored?.model || defaults.model;
  modelOptions.value = [];
  validationStatus.value = "none";
  validationError.value = "";
  llmSaveError.value = "";
  llmSaveSuccess.value = "";
}

function syncLlmInputs(next: AppSettings | null) {
  if (!next) return;
  const provider = next.activeProvider || "deepseek";
  const defaults = providerDefaults[provider] ?? providerDefaults.custom;
  const stored = next.providerSettings?.[provider];
  selectedProvider.value = provider;
  baseUrlInput.value = stored?.baseUrl || next.baseUrl || defaults.baseUrl;
  modelInput.value = stored?.model || next.model || defaults.model;
}

function saveDisplaySetting(
  key: "filesPerPage" | "notesPerPage" | "chatsPerPage",
  value: number,
) {
  if (key === "filesPerPage") filesPerPage.value = value;
  if (key === "notesPerPage") notesPerPage.value = value;
  if (key === "chatsPerPage") chatsPerPage.value = value;

  localStorage.setItem(key, String(value));

  // Notify other components
  window.dispatchEvent(
    new CustomEvent("settingChanged", {
      detail: { key, value },
    }),
  );
}

onMounted(async () => {
  // Load display settings
  const storedFiles = localStorage.getItem("filesPerPage");
  if (storedFiles) filesPerPage.value = parseInt(storedFiles, 10);

  const storedNotes = localStorage.getItem("notesPerPage");
  if (storedNotes) notesPerPage.value = parseInt(storedNotes, 10);

  const storedChats = localStorage.getItem("chatsPerPage");
  if (storedChats) chatsPerPage.value = parseInt(storedChats, 10);

  await loadProjects();

  // Load current theme
  currentTheme.value = getStoredTheme();

  // Listen for theme changes
  window.addEventListener("themeChanged", ((e: CustomEvent) => {
    currentTheme.value = e.detail;
  }) as EventListener);

  // Load settings and version
  isLoadingSettings.value = true;
  try {
    const [settingsData, version] = await Promise.all([
      getSettings(),
      fetchVersion().catch(() => ""),
    ]);
    settings.value = settingsData;
    currentVersion.value = version;
    syncLlmInputs(settingsData);
  } catch (e) {
    console.error("Failed to load settings:", e);
  } finally {
    isLoadingSettings.value = false;
  }

  document.addEventListener("click", handleOutsideQueueClick);
});

onUnmounted(() => {
  document.removeEventListener("click", handleOutsideQueueClick);
});
</script>

<template>
  <div class="project-hub-container">
    <header class="hub-header">
      <div class="header-left">
        <div class="logo">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
          </svg>
          <span>ReferenceMiner</span>
        </div>
        <h1>Your Dashboard</h1>
      </div>
      <div class="header-right">
        <div class="search-bar">
          <Search :size="16" />
          <input v-model="searchQuery" placeholder="Search studies..." />
        </div>
        <button class="btn-primary" @click="showCreateModal = true">
          <Plus :size="18" />
          <span>New Study</span>
        </button>
      </div>
    </header>

    <!-- Tabs -->
    <div class="hub-tabs">
      <div class="tabs-left">
        <button class="tab-btn" :class="{ active: activeTab === 'projects' }" @click="activeTab = 'projects'">
          <Search :size="16" />
          <span>Projects</span>
        </button>
        <button class="tab-btn" :class="{ active: activeTab === 'bank' }" @click="switchToBank">
          <FileText :size="16" />
          <span>Reference Bank</span>
        </button>
      </div>
      <div class="tabs-right">
        <button class="tab-btn" :class="{ active: activeTab === 'settings' }" @click="activeTab = 'settings'">
          <Settings :size="16" />
          <span>Settings</span>
        </button>
      </div>
    </div>

    <main class="hub-content" :class="{ 'settings-active': activeTab === 'settings' }">
      <!-- Projects Tab -->
      <div v-if="activeTab === 'projects'">
        <div v-if="loading" class="loading-state">
          <Loader2 class="spinner" :size="32" />
          <p>Loading your research space...</p>
        </div>

        <div v-else-if="projects.length === 0" class="empty-state">
          <div class="empty-icon">📂</div>
          <h2>No studies yet</h2>
          <p>Create your first research project to get started.</p>
          <button class="btn-primary" @click="showCreateModal = true">
            <Plus :size="18" />
            <span>Create New Study</span>
          </button>
        </div>

        <div v-else class="project-grid">
          <ProjectCard v-for="p in projects" :key="p.id" :project="p" @open="openProject"
            @delete="handleDeleteProject" />

          <div class="create-card" @click="showCreateModal = true">
            <div class="plus-icon">
              <Plus :size="32" />
            </div>
            <span>Start New Project</span>
          </div>
        </div>
      </div>

      <!-- Reference Bank Tab -->
      <div v-else-if="activeTab === 'bank'" class="bank-content">
        <div class="bank-header">
          <div class="bank-header-text">
            <h2>Reference Bank</h2>
            <p>
              Upload and manage your research files. Files can be selected in
              any project.
            </p>
          </div>
          <div class="bank-header-actions">
            <button class="bank-action-btn" :disabled="isReprocessing || bankLoading"
              @click="showReprocessConfirm = true">
              <Loader2 v-if="isReprocessing" class="spinner" :size="14" />
              <span>{{
                isReprocessing ? "Reprocessing..." : "Reprocess All"
              }}</span>
            </button>
          </div>
        </div>

        <FileUploader upload-mode="bank" @upload-complete="handleUploadComplete"
          @queue-updated="handleBankQueueUpdated" />

        <div v-if="bankLoading" class="loading-state">
          <Loader2 class="spinner" :size="32" />
          <p>Loading files...</p>
        </div>

        <div v-else-if="bankFiles.length === 0" class="empty-state">
          <Upload :size="48" class="empty-icon-svg" />
          <h3>No files in Reference Bank</h3>
          <p>Upload files using the button above to get started.</p>
        </div>

        <TransitionGroup v-else name="file-list" tag="div" class="file-grid" @before-leave="handleBeforeLeave">
          <div v-for="file in sortedBankFiles" :key="file.relPath" class="file-card">
            <div class="file-icon">
              <FileText :size="24" />
            </div>
            <div class="file-info">
              <div class="file-name" :title="getFileName(file.relPath)">
                {{ getFileName(file.relPath) }}
              </div>
              <div class="file-meta">
                {{ file.fileType }} ·
                {{ Math.round((file.sizeBytes || 0) / 1024) }}KB
              </div>
            </div>
            <div class="file-actions">
              <button class="btn-icon tooltip" data-tooltip="Preview file" @click="handlePreview(file)">
                <Search :size="16" />
              </button>
              <button class="btn-icon tooltip" data-tooltip="Reprocess file" @click="handleReprocessFile(file)">
                <Upload :size="16" />
              </button>
              <button class="btn-icon delete tooltip" data-tooltip="Delete file" @click="requestDelete(file)">
                <Trash2 :size="16" />
              </button>
            </div>
          </div>
        </TransitionGroup>

        <div ref="queueRef" class="bank-queue-fab">
          <button class="queue-toggle" @click="isQueueOpen = !isQueueOpen">
            <ListOrdered :size="16" />
            <span v-if="queueCount > 0" class="queue-badge">{{
              queueCount
            }}</span>
          </button>
          <Transition name="queue-panel">
            <div v-if="isQueueOpen" class="queue-panel">
              <div v-if="queueItems.length === 0" class="queue-empty">
                No active tasks.
              </div>
              <div v-else class="queue-list">
                <div v-for="item in queueItems" :key="item.id" class="queue-item">
                  <div class="queue-name" :title="item.name">
                    {{ item.name }}
                  </div>
                  <div class="queue-meta">
                    <span class="queue-status" :class="item.status">{{
                      formatQueueStatus(item.status)
                    }}</span>
                    <span v-if="item.phase" class="queue-phase">{{
                      formatQueuePhase(item.phase)
                    }}</span>
                    <span v-if="item.progress >= 0" class="queue-progress-text">{{ item.progress }}%</span>
                  </div>
                  <div v-if="item.progress >= 0" class="queue-progress">
                    <div class="queue-progress-fill" :style="{ width: `${item.progress}%` }"></div>
                  </div>
                  <div v-if="item.status === 'error' && item.error" class="queue-error">
                    {{ item.error }}
                  </div>
                  <div v-if="item.status === 'duplicate' && item.duplicatePath" class="queue-duplicate">
                    Duplicate: {{ item.duplicatePath }}
                  </div>
                </div>
              </div>
            </div>
          </Transition>
        </div>
      </div>

      <!-- Settings Tab -->
      <div v-else-if="activeTab === 'settings'" class="settings-container">
        <aside class="settings-sidebar">
          <nav class="settings-nav">
            <button class="settings-nav-item" :class="{ active: settingsSection === 'preferences' }"
              @click="settingsSection = 'preferences'">
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path
                  d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
              <span>Preferences</span>
            </button>
            <button class="settings-nav-item" :class="{ active: settingsSection === 'advanced' }"
              @click="settingsSection = 'advanced'">
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                <line x1="9" y1="3" x2="9" y2="21"></line>
              </svg>
              <span>Advanced</span>
            </button>
          </nav>
        </aside>

        <main class="settings-content">
          <!-- Preferences Section -->
          <div v-if="settingsSection === 'preferences'" class="settings-section-container">
            <div class="settings-header">
              <h2 class="settings-section-title">Preferences</h2>
              <p class="settings-section-desc">
                Customize your experience with theme, keyboard shortcuts, and
                display options.
              </p>
            </div>

            <div class="start-settings-content">
              <!-- Theme Card -->
              <section class="settings-card updates-card">
                <div class="section-header">
                  <div class="section-icon">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none"
                      stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <circle cx="12" cy="12" r="4" />
                      <path d="M12 2v2" />
                      <path d="M12 20v2" />
                      <path d="m4.93 4.93 1.41 1.41" />
                      <path d="m17.66 17.66 1.41 1.41" />
                      <path d="M2 12h2" />
                      <path d="M20 12h2" />
                      <path d="m6.34 17.66-1.41 1.41" />
                      <path d="m19.07 4.93-1.41 1.41" />
                    </svg>
                  </div>
                  <div>
                    <h4 class="section-title">Theme</h4>
                    <p class="section-description">
                      Choose your preferred color theme
                    </p>
                  </div>
                </div>
                <div class="section-content">
                  <div class="pref-setting-row">
                    <div class="pref-setting-info">
                      <label class="form-label">Appearance</label>
                      <p class="form-hint">
                        Select light, dark, or match your system settings
                      </p>
                    </div>
                    <CustomSelect :model-value="currentTheme" :options="themeOptions"
                      @update:model-value="(value) => setTheme(value as Theme)" />
                  </div>
                </div>
              </section>

              <!-- PDF View Mode -->
              <section class="settings-card">
                <div class="section-header">
                  <div class="section-icon">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none"
                      stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"></path>
                      <polyline points="14 2 14 8 20 8"></polyline>
                    </svg>
                  </div>
                  <div>
                    <h4 class="section-title">PDF Viewing</h4>
                    <p class="section-description">
                      Customize how you read documents
                    </p>
                  </div>
                </div>
                <div class="section-content">
                  <div class="pref-setting-row">
                    <div class="pref-setting-info">
                      <label class="form-label">Default View Mode</label>
                      <p class="form-hint">
                        Choose between single page or continuous scrolling
                      </p>
                    </div>
                    <CustomSelect :model-value="viewMode" :options="pdfViewOptions" @update:model-value="
                      (value) => setViewMode(value as 'single' | 'continuous')
                    " />
                  </div>
                </div>
              </section>

              <!-- Submit Prompt Key Card -->
              <section class="settings-card">
                <div class="section-header">
                  <div class="section-icon">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none"
                      stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M9 18l6-6-6-6" />
                    </svg>
                  </div>
                  <div>
                    <h4 class="section-title">Submit Prompt Key</h4>
                    <p class="section-description">
                      Choose how to submit your prompts
                    </p>
                  </div>
                </div>
                <div class="section-content">
                  <div class="radio-group-vertical">
                    <label class="radio-option">
                      <input type="radio" name="submitKey" value="enter" checked />
                      <div class="radio-option-content">
                        <span class="radio-option-label">Enter to send</span>
                        <span class="radio-option-desc">Shift+Enter for new line</span>
                      </div>
                    </label>
                    <label class="radio-option">
                      <input type="radio" name="submitKey" value="ctrl-enter" />
                      <div class="radio-option-content">
                        <span class="radio-option-label">Ctrl+Enter to send</span>
                        <span class="radio-option-desc">Enter for new line</span>
                      </div>
                    </label>
                  </div>
                </div>
              </section>

              <!-- Display Card -->
              <section class="settings-card">
                <div class="section-header">
                  <div class="section-icon">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none"
                      stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
                      <line x1="8" y1="21" x2="16" y2="21" />
                      <line x1="12" y1="17" x2="12" y2="21" />
                    </svg>
                  </div>
                  <div>
                    <h4 class="section-title">Display</h4>
                    <p class="section-description">
                      Customize how content is displayed
                    </p>
                  </div>
                </div>
                <div class="section-content">
                  <!-- Files Limit -->
                  <div class="pref-setting-row">
                    <div class="pref-setting-info">
                      <label class="form-label">Project Files Limit</label>
                      <p class="form-hint">
                        Items per page in sidebar (0 for unlimited)
                      </p>
                    </div>
                    <div class="input-group" style="width: 120px">
                      <input type="number" min="0" class="form-input" :value="filesPerPage" @input="
                        (e) =>
                          saveDisplaySetting(
                            'filesPerPage',
                            parseInt((e.target as HTMLInputElement).value) ||
                            0,
                          )
                      " />
                    </div>
                  </div>

                  <!-- Notes Limit -->
                  <div class="pref-setting-row">
                    <div class="pref-setting-info">
                      <label class="form-label">Pinned Notes Limit</label>
                      <p class="form-hint">
                        Notes per page in sidebar (0 for unlimited)
                      </p>
                    </div>
                    <div class="input-group" style="width: 120px">
                      <input type="number" min="0" class="form-input" :value="notesPerPage" @input="
                        (e) =>
                          saveDisplaySetting(
                            'notesPerPage',
                            parseInt((e.target as HTMLInputElement).value) ||
                            0,
                          )
                      " />
                    </div>
                  </div>

                  <!-- Chats Limit -->
                  <div class="pref-setting-row">
                    <div class="pref-setting-info">
                      <label class="form-label">Chat List Limit</label>
                      <p class="form-hint">
                        Chats per page in sidebar (0 for unlimited)
                      </p>
                    </div>
                    <div class="input-group" style="width: 120px">
                      <input type="number" min="0" class="form-input" :value="chatsPerPage" @input="
                        (e) =>
                          saveDisplaySetting(
                            'chatsPerPage',
                            parseInt((e.target as HTMLInputElement).value) ||
                            0,
                          )
                      " />
                    </div>
                  </div>
                </div>
              </section>
            </div>
          </div>

          <!-- Advanced Section -->
          <div v-else-if="settingsSection === 'advanced'" class="settings-section-container">
            <div class="settings-header">
              <h2 class="settings-section-title">Advanced</h2>
              <p class="settings-section-desc">
                Manage API configuration and perform advanced operations.
              </p>
            </div>

            <div v-if="isLoadingSettings" class="loading-settings">
              Loading settings...
            </div>

            <div v-else class="start-settings-content">
              <!-- API Configuration Section -->
              <section class="settings-card">
                <div class="section-header">
                  <div class="section-icon">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none"
                      stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path
                        d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4" />
                    </svg>
                  </div>
                  <div>
                    <h4 class="section-title">API Configuration</h4>
                    <p class="section-description">
                      Configure your provider, API key, and model for AI-powered
                      answers
                    </p>
                  </div>
                </div>

                <div class="section-content">
                  <div class="llm-setup-intro">
                    <div class="llm-setup-title">Quick setup</div>
                    <p class="form-hint">
                      Choose a provider, add your API key, then load and save a
                      model. Presets: ChatGPT, Gemini, Anthropic, DeepSeek.
                    </p>
                  </div>

                  <div class="llm-setup-grid">
                    <div class="llm-setup-step">
                      <div class="step-badge">1</div>
                      <div class="step-body">
                        <div class="step-title">Provider preset</div>
                        <p class="step-desc">
                          ChatGPT, Gemini, Anthropic, DeepSeek, or a custom
                          endpoint.
                        </p>
                        <CustomSelect :model-value="selectedProvider" :options="providerOptions" @update:model-value="
                          (value) => setProvider(value as string)
                        " />
                      </div>
                    </div>

                    <div class="llm-setup-step">
                      <div class="step-badge">2</div>
                      <div class="step-body">
                        <div class="step-title">API key</div>
                        <p class="step-desc">
                          Stored per provider. If empty, validation will use any
                          stored key on the server.
                        </p>
                        <p v-if="currentProviderLink.url" class="form-hint">
                          Get your key from
                          <a :href="currentProviderLink.url" target="_blank" rel="noopener noreferrer">{{
                            currentProviderLink.label }}</a>
                        </p>

                        <div class="current-key" v-if="currentProviderKey.hasKey">
                          <span class="key-status valid">
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"
                              fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"
                              stroke-linejoin="round">
                              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                              <polyline points="22 4 12 14.01 9 11.01" />
                            </svg>
                            Key configured
                          </span>
                          <span class="masked-key">{{
                            currentProviderKey.maskedKey
                          }}</span>
                          <button class="btn-link danger" @click="handleDeleteApiKey" :disabled="isSaving">
                            Remove
                          </button>
                        </div>

                        <div class="api-input-row">
                          <div class="input-group">
                            <input v-model="apiKeyInput" :type="showApiKey ? 'text' : 'password'" class="form-input"
                              :placeholder="currentProviderKey.hasKey
                                  ? 'Enter new key to replace'
                                  : 'Enter your API key'
                                " />
                            <button class="input-addon" @click="showApiKey = !showApiKey" type="button">
                              <svg v-if="showApiKey" xmlns="http://www.w3.org/2000/svg" width="16" height="16"
                                viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                                stroke-linecap="round" stroke-linejoin="round">
                                <path
                                  d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                                <line x1="1" x2="23" y1="1" y2="23" />
                              </svg>
                              <svg v-else xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
                                fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"
                                stroke-linejoin="round">
                                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                                <circle cx="12" cy="12" r="3" />
                              </svg>
                            </button>
                          </div>
                          <div class="api-actions">
                            <button class="btn btn-outline" @click="handleValidate" :disabled="isValidating">
                              {{ isValidating ? "Validating..." : "Validate" }}
                            </button>
                            <button class="btn btn-primary-sm" @click="handleSave" :disabled="isSaving || !apiKeyInput">
                              {{ isSaving ? "Saving..." : "Save" }}
                            </button>
                          </div>
                        </div>

                        <div v-if="saveError" class="error-message">
                          {{ saveError }}
                        </div>

                        <div class="validation-result" v-if="validationStatus !== 'none'">
                          <span v-if="validationStatus === 'valid'" class="status valid">
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"
                              fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"
                              stroke-linejoin="round">
                              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                              <polyline points="22 4 12 14.01 9 11.01" />
                            </svg>
                            {{ apiKeyStatusMessage }}
                          </span>
                          <span v-else class="status invalid">
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"
                              fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"
                              stroke-linejoin="round">
                              <circle cx="12" cy="12" r="10" />
                              <line x1="15" x2="9" y1="9" y2="15" />
                              <line x1="9" x2="15" y1="9" y2="15" />
                            </svg>
                            Invalid:
                            {{
                              validationError || "API key verification failed"
                            }}
                          </span>
                        </div>

                        <div v-if="balanceInfos.length" class="balance-panel">
                          <div class="balance-header">
                            <span class="balance-title">Remaining balance</span>
                            <span v-if="balanceAvailable === false" class="balance-warning">Insufficient for API
                              calls</span>
                          </div>
                          <div class="balance-list">
                            <div v-for="info in balanceInfos" :key="info.currency" class="balance-item">
                              <div class="balance-line">
                                <span class="balance-currency">{{
                                  info.currency
                                }}</span>
                                <span class="balance-amount">{{
                                  info.totalBalance
                                }}</span>
                              </div>
                              <div class="balance-meta">
                                Granted {{ info.grantedBalance }} · Topped up
                                {{ info.toppedUpBalance }}
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div class="llm-setup-step">
                      <div class="step-badge">3</div>
                      <div class="step-body">
                        <div class="step-title">Endpoint & model</div>
                        <p class="step-desc">
                          Confirm the base URL, load models, then save your
                          selection.
                        </p>

                        <label class="form-label">Base URL</label>
                        <div class="input-group">
                          <input v-model="baseUrlInput" class="form-input" placeholder="https://api.openai.com/v1" />
                        </div>

                        <label class="form-label">Model</label>
                        <div v-if="modelOptions.length" class="model-select-row">
                          <CustomSelect :model-value="modelInput" :options="modelOptions" @update:model-value="
                            (value) => (modelInput = value as string)
                          " />
                          <button class="btn btn-outline" @click="handleLoadModels" :disabled="isLoadingModels">
                            {{
                              isLoadingModels ? "Loading..." : "Reload models"
                            }}
                          </button>
                        </div>
                        <div v-else class="input-group">
                          <input v-model="modelInput" class="form-input" placeholder="gpt-4o-mini" />
                        </div>

                        <div class="llm-config-actions">
                          <button class="btn btn-outline" @click="handleLoadModels" :disabled="isLoadingModels">
                            {{ isLoadingModels ? "Loading..." : "Load models" }}
                          </button>
                          <button class="btn btn-primary-sm" @click="handleSaveLlmSettings" :disabled="isSavingLlm">
                            {{
                              isSavingLlm
                                ? "Saving..."
                                : "Save Endpoint & Model"
                            }}
                          </button>
                        </div>

                        <div v-if="llmSaveError" class="error-message">
                          {{ llmSaveError }}
                        </div>
                        <div v-if="llmSaveSuccess" class="success-message">
                          {{ llmSaveSuccess }}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </section>

              <section class="settings-card updates-section">
                <div class="section-header">
                  <div class="section-icon">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none"
                      stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M21 12a9 9 0 1 1-9-9" />
                      <path d="M22 3 12 13" />
                      <path d="M22 3 15 3" />
                      <path d="M22 3 22 10" />
                    </svg>
                  </div>
                  <div>
                    <h4 class="section-title">Updates</h4>
                    <p class="section-description">
                      Version {{ currentVersionLabel }}
                    </p>
                  </div>
                  <div class="section-header-actions">
                    <span class="update-badge" :class="updateBadgeClass">{{
                      updateBadgeText
                    }}</span>
                  </div>
                </div>

                <div class="section-content">
                  <div class="pref-setting-row">
                    <div class="pref-setting-info">
                      <label class="form-label">Check for Updates</label>
                      <p class="form-hint">
                        <template v-if="updateInfo?.isUpdateAvailable">
                          Version {{ updateInfo.latest?.version }} is available
                        </template>
                        <template v-else-if="lastCheckedLabel">
                          Last checked {{ lastCheckedLabel }}
                        </template>
                        <template v-else>
                          Check GitHub for new releases
                        </template>
                      </p>
                    </div>
                    <div class="update-actions">
                      <a v-if="
                        updateInfo?.isUpdateAvailable &&
                        updateInfo?.latest?.url
                      " class="btn btn-primary-sm" :href="updateInfo.latest.url" target="_blank"
                        rel="noopener noreferrer">Download</a>
                      <button class="btn btn-outline" @click="handleUpdateCheck" :disabled="isCheckingUpdate">
                        {{ isCheckingUpdate ? "Checking..." : "Check" }}
                      </button>
                    </div>
                  </div>
                  <div v-if="updateError" class="error-message">
                    {{ updateError }}
                  </div>
                </div>
              </section>

              <!-- Danger Zone Section -->
              <section class="settings-card danger-zone-card">
                <div class="section-header">
                  <div class="section-icon danger-icon">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none"
                      stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
                      <line x1="12" x2="12" y1="9" y2="13" />
                      <line x1="12" x2="12.01" y1="17" y2="17" />
                    </svg>
                  </div>
                  <div>
                    <h4 class="section-title">Danger Zone</h4>
                    <p class="section-description">
                      Destructive actions that cannot be undone
                    </p>
                  </div>
                </div>

                <div class="section-content">
                  <p class="form-hint" style="font-weight: 700; margin-bottom: 1rem">
                    Clear all indexed chunks and chat sessions. Files will
                    remain in the reference folder.
                  </p>

                  <div v-if="resetSuccess" class="success-message">
                    {{ resetSuccess }}
                  </div>
                  <div v-if="resetError" class="error-message">
                    {{ resetError }}
                  </div>

                  <button class="btn btn-danger-action" @click="handleResetClick" :disabled="isResetting">
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
                      stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M3 6h18" />
                      <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
                      <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
                      <line x1="10" x2="10" y1="11" y2="17" />
                      <line x1="14" x2="14" y1="11" y2="17" />
                    </svg>
                    {{ isResetting ? "Clearing..." : "Clear All Data" }}
                  </button>
                </div>
              </section>
            </div>
          </div>
        </main>
      </div>
    </main>
  </div>

  <!-- Create Modal -->
  <Transition name="fade">
    <div v-if="showCreateModal" class="modal-mask" @click.self="showCreateModal = false">
      <div class="modal-container">
        <h2>Create New Study</h2>
        <div class="form-group">
          <label>Project Name</label>
          <input v-model="newProjectName" placeholder="e.g. Photovoltaic Research" autofocus />
        </div>
        <div class="form-group">
          <label>Description (Optional)</label>
          <textarea v-model="newProjectDesc" placeholder="What is this study about?" rows="3"></textarea>
        </div>
        <div class="form-group">
          <label>Initial Content (Optional)</label>
          <div class="file-select-row">
            <span class="file-count" v-if="selectedFilesForCreate.size > 0">
              {{ selectedFilesForCreate.size }} files selected
            </span>
            <span class="file-count placeholder" v-else>
              Start with some references...
            </span>
            <button class="btn-outline-sm" @click="openFileSelectorForCreate">
              Select Files
            </button>
          </div>
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="showCreateModal = false">
            Cancel
          </button>
          <button class="btn-primary" :disabled="!newProjectName.trim() || creating" @click="handleCreate">
            <Loader2 v-if="creating" class="spinner" :size="16" />
            <span>{{ creating ? "Creating..." : "Create Project" }}</span>
          </button>
        </div>
      </div>
    </div>
  </Transition>

  <!-- File Preview Modal -->
  <FilePreviewModal v-model="showPreviewModal" :file="previewFile" />

  <!-- Delete Confirmation Modal -->
  <ConfirmationModal v-model="showDeleteModal" title="Delete File?" :message="fileToDelete
      ? `Delete '${getFileName(fileToDelete.relPath)}'? This will remove it from all projects. This action cannot be undone.`
      : ''
    " confirmText="Delete" @confirm="confirmDelete" @cancel="cancelDelete" />

  <!-- Delete Project Confirmation Modal -->
  <ConfirmationModal v-model="showDeleteProjectModal" title="Delete Project?" :message="projectToDelete
      ? `Delete '${projectToDelete.name}'? This will remove the project and all its notes. Files will remain in the Reference Bank.`
      : ''
    " confirmText="Delete" @confirm="confirmDeleteProject" @cancel="cancelDeleteProject" />

  <!-- Initial File Selector -->
  <BankFileSelectorModal v-model="showFileSelectorForCreate" :selected-files="selectedFilesForCreate"
    @confirm="handleInitialFilesSelected" />

  <!-- Reset Confirmation Modal -->
  <ConfirmationModal v-model="showResetConfirm" title="Clear All Data?"
    message="This will permanently delete all indexed chunks, search indexes, and chat sessions. Your files will remain in the reference folder. This action cannot be undone."
    confirm-text="Clear All Data" cancel-text="Cancel" @confirm="handleResetConfirm" />

  <!-- Reprocess Reference Bank -->
  <ConfirmationModal v-model="showReprocessConfirm" title="Reprocess Reference Bank?"
    message="This will delete all indexed data and rebuild from files in the reference folder. Your files will remain untouched."
    confirm-text="Reprocess" cancel-text="Cancel" @confirm="handleReprocessConfirm" />
</template>

<style scoped>
.project-hub-container {
  height: 100vh;
  background: var(--color-neutral-95);
  color: var(--text-primary);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.hub-header {
  padding: 40px 60px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--bg-panel);
  border-bottom: 1px solid var(--border-color);
}

.header-left .logo {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--accent-color);
  font-weight: 700;
  font-size: 14px;
  margin-bottom: 8px;
}

.header-left h1 {
  margin: 0;
  font-size: 28px;
  font-weight: 800;
}

.header-right {
  display: flex;
  gap: 16px;
  align-items: center;
}

.btn-icon-header {
  background: transparent;
  border: none;
  padding: 10px;
  border-radius: 8px;
  cursor: pointer;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.btn-icon-header:hover {
  background: var(--color-neutral-170);
  color: var(--text-primary);
}

.search-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  background: var(--color-neutral-170);
  padding: 10px 16px;
  border-radius: 99px;
  min-width: 300px;
}

.search-bar input {
  background: transparent;
  border: none;
  font-size: 14px;
  width: 100%;
}

.search-bar input:focus {
  outline: none;
}

.hub-content {
  padding: 60px;
  flex: 1;
  overflow-y: auto;
}

.hub-content.settings-active {
  padding: 0;
}

.project-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 30px;
}

.create-card {
  border: 2px dashed var(--border-card);
  background: transparent;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s;
  min-height: 200px;
}

.create-card:hover {
  border-color: var(--accent-color);
  color: var(--accent-color);
  background: rgba(var(--accent-color-rgb), 0.02);
}

.plus-icon {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background: var(--bg-button);
  display: flex;
  align-items: center;
  justify-content: center;
}

.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  text-align: center;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 20px;
}

.empty-state h2 {
  margin: 0 0 10px 0;
}

.empty-state p {
  color: var(--text-secondary);
  margin-bottom: 30px;
}

/* Modal Styles */
.modal-mask {
  position: fixed;
  inset: 0;
  background: var(--alpha-black-40);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-container {
  background: var(--bg-panel);
  width: 500px;
  padding: 30px;
  border-radius: 16px;
  box-shadow: 0 20px 40px var(--alpha-black-10);
}

.modal-container h2 {
  margin: 0 0 24px 0;
  font-size: 20px;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
}

.form-group input,
.form-group textarea {
  width: 100%;
  padding: 12px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  font-size: 14px;
  background: var(--bg-input);
  color: var(--text-primary);
  transition: all 0.2s;
}

.form-group textarea {
  resize: vertical;
  min-height: 75px;
  max-height: 300px;
}

.form-group input:focus,
.form-group textarea:focus {
  outline: none;
  border-color: var(--accent-bright);
  box-shadow: 0 0 0 3px rgba(var(--accent-color-rgb), 0.1);
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 30px;
}

.btn-primary {
  background: var(--accent-color);
  color: white;
  border: none;
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.btn-secondary {
  background: var(--color-neutral-170);
  color: var(--text-primary);
  border: none;
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
}

.spinner {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Tabs */
.hub-tabs {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 60px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
}

.tabs-left,
.tabs-right {
  display: flex;
  gap: 8px;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-btn:hover {
  color: var(--text-primary);
  background: var(--color-neutral-95);
}

.tab-btn.active {
  color: var(--accent-color);
  border-bottom-color: var(--accent-color);
}

/* Reference Bank */
.bank-content {
  max-width: 1200px;
  margin: 0 auto;
}

.bank-header {
  margin-bottom: 30px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.bank-header-text {
  max-width: 720px;
}

.bank-header-actions {
  display: flex;
  gap: 8px;
}

.bank-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 600;
  background: var(--color-white);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
}

.bank-action-btn:hover:not(:disabled) {
  background: var(--bg-card-hover);
  border-color: var(--accent-bright);
}

.bank-action-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.bank-header h2 {
  margin: 0 0 8px 0;
  font-size: 24px;
  font-weight: 700;
}

.bank-header p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 14px;
}

.file-grid {
  position: relative;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
  margin-top: 24px;
}

.file-list-move {
  transition: transform 360ms ease-out;
}

.file-list-enter-active,
.file-list-leave-active {
  transition:
    opacity 240ms ease,
    transform 240ms ease;
}

.file-list-enter-from,
.file-list-leave-to {
  opacity: 0;
  transform: translateY(14px) scale(0.98);
}

.file-list-leave-active {
  pointer-events: none;
}

.bank-queue-fab {
  position: fixed;
  right: 28px;
  bottom: 28px;
  display: flex;
  flex-direction: column-reverse;
  align-items: flex-end;
  gap: 8px;
  z-index: 900;
}

.queue-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 999px;
  border: 1px solid var(--border-color);
  background: var(--color-white);
  color: var(--text-primary);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 8px 20px var(--alpha-black-10);
  transition: all 0.15s;
}

.queue-toggle:hover {
  background: var(--bg-card-hover);
  border-color: var(--accent-bright);
}

.queue-badge {
  min-width: 18px;
  height: 18px;
  padding: 0 6px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 700;
  background: var(--accent-color);
  color: var(--color-white);
}

.queue-panel {
  width: 280px;
  max-height: 360px;
  overflow-y: auto;
  background: var(--bg-panel);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 12px;
  box-shadow: 0 10px 24px var(--alpha-black-15);
}

.queue-empty {
  font-size: 12px;
  color: var(--text-secondary);
  text-align: center;
  padding: 12px 0;
}

.queue-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.queue-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px;
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: 10px;
}

.queue-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.queue-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: var(--text-secondary);
}

.queue-phase {
  color: var(--text-secondary);
}

.queue-status {
  font-weight: 600;
}

.queue-status.uploading,
.queue-status.processing {
  color: var(--color-info-800);
}

.queue-status.pending {
  color: var(--color-neutral-650);
}

.queue-status.error {
  color: var(--color-danger-700);
}

.queue-status.duplicate {
  color: var(--color-warning-800);
}

.queue-progress {
  height: 4px;
  background: var(--color-neutral-240);
  border-radius: 999px;
  overflow: hidden;
}

.queue-progress-fill {
  height: 100%;
  background: var(--accent-color);
  transition: width 0.2s ease;
}

.queue-progress-text {
  color: var(--text-secondary);
  margin-left: auto;
}

.queue-error {
  font-size: 11px;
  color: var(--color-danger-700);
}

.queue-duplicate {
  font-size: 11px;
  color: var(--color-warning-800);
}

.queue-panel-enter-active,
.queue-panel-leave-active {
  transition:
    opacity 0.18s ease,
    transform 0.18s ease;
}

.queue-panel-enter-from,
.queue-panel-leave-to {
  opacity: 0;
  transform: translateY(12px) scale(0.98);
}

.queue-panel-enter-to,
.queue-panel-leave-from {
  opacity: 1;
  transform: translateY(0) scale(1);
}

.file-card {
  will-change: transform;
}

.project-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 20px;
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
  min-height: 180px;
}

.project-card:hover {
  background: var(--bg-card-hover);
  border-color: var(--accent-bright);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px var(--alpha-black-10);
}

.file-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: 12px;
  transition: all 0.2s;
  cursor: pointer;
}

.file-card:hover {
  border-color: var(--accent-bright);
  box-shadow: 0 2px 8px var(--alpha-black-08);
}

.file-icon {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-neutral-180);
  border-radius: 8px;
  color: var(--accent-color);
}

.file-info {
  flex: 1;
  min-width: 0;
}

.file-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}

.file-meta {
  font-size: 12px;
  color: var(--text-secondary);
  text-transform: uppercase;
}

.file-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.btn-icon.tooltip {
  position: relative;
}

.btn-icon.tooltip::after {
  content: attr(data-tooltip);
  position: absolute;
  bottom: 100%;
  left: 50%;
  transform: translate(-50%, -6px);
  background: var(--bg-panel);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 10px;
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transition:
    opacity 0.15s ease,
    transform 0.15s ease;
  z-index: 2;
}

.btn-icon.tooltip:hover::after {
  opacity: 1;
  transform: translate(-50%, -10px);
}

.file-card:hover .file-actions {
  opacity: 1;
}

/* File Selection in Create Modal */
.file-select-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--color-neutral-95);
  border: 1px solid var(--border-card);
  padding: 8px 12px;
  border-radius: 8px;
}

.file-count {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 500;
}

.file-count.placeholder {
  color: var(--text-secondary);
  font-style: italic;
}

.btn-outline-sm {
  background: var(--bg-card);
  border: 1px solid var(--border-input);
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
  color: var(--text-primary);
}

.btn-outline-sm:hover {
  border-color: var(--accent-color);
  color: var(--accent-color);
}

.file-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.bank-file-item:hover .file-actions {
  opacity: 1;
}

.file-action-btn {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.file-action-btn:hover {
  background: var(--bg-icon-hover);
  color: var(--text-primary);
}

.file-action-btn.delete:hover {
  color: var(--color-red-600);
}

.btn-icon {
  background: transparent;
  border: none;
  padding: 4px;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--text-secondary);
  border-radius: 4px;
  transition: all 0.2s;
}

.btn-icon:hover {
  background: var(--bg-icon-hover);
  color: var(--text-primary);
}

.btn-icon.delete:hover {
  background: var(--bg-icon-hover);
  color: var(--color-red-600);
}

.empty-icon-svg {
  color: var(--color-neutral-400);
  margin-bottom: 16px;
}

.empty-state h3 {
  margin: 0 0 8px 0;
  font-size: 18px;
}

/* Settings Layout */
.settings-layout {
  display: flex;
  height: 100%;
  max-width: 1400px;
  margin: 0 auto;
}

.settings-sidebar {
  width: 280px;
  border-right: 1px solid var(--border-card);
  padding: 40px 0;
  flex-shrink: 0;
}

.settings-nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 0 20px;
}

.settings-nav-item {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  background: transparent;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  text-align: left;
  transition: all 0.2s;
}

.settings-nav-item:hover {
  background: var(--bg-card-hover);
  color: var(--accent-bright);
}

.settings-nav-item.active {
  background: var(--accent-soft, var(--color-accent-50));
  color: var(--accent-color);
  font-weight: 600;
}

.settings-content {
  flex: 1;
  padding: 30px 60px 30px;
  overflow-y: auto;
}

.settings-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  text-align: center;
  color: var(--text-secondary);
}

.settings-placeholder p {
  margin: 8px 0;
  font-size: 14px;
}

/* Settings Container Layout */
.settings-container {
  display: flex;
  height: 100%;
  gap: 0;
}

/* Settings Sidebar */
.settings-sidebar {
  width: 240px;
  border-right: 1px solid var(--border-color);
  background: var(--color-neutral-100);
  padding: 24px 0;
}

.settings-nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 0 12px;
}

.settings-nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border: none;
  background: transparent;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s;
  text-align: left;
}

.settings-nav-item:hover {
  background: var(--color-neutral-150);
  color: var(--text-primary);
}

.settings-nav-item.active {
  background: var(--color-white);
  color: var(--accent-color);
  box-shadow: 0 1px 3px var(--alpha-black-10);
}

.settings-nav-item svg {
  flex-shrink: 0;
  color: currentColor;
}

/* Settings Section */
.settings-section {
  max-width: 800px;
}

.settings-section-title {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 8px 0;
}

.settings-section-desc {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0 0 32px 0;
  line-height: 1.5;
}

/* Settings Group */
.settings-group {
  margin-bottom: 40px;
  padding-bottom: 32px;
  border-bottom: 1px solid var(--border-color);
}

.settings-group:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}

.settings-group-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 16px 0;
}

/* Settings Item */
.settings-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  padding: 16px 0;
}

.settings-item-info {
  flex: 1;
}

.settings-label {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.settings-desc {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0;
  line-height: 1.5;
}

.settings-control {
  display: flex;
  align-items: center;
  gap: 12px;
}

.settings-control :deep(.custom-select-wrapper) {
  width: auto;
  min-width: 200px;
  max-width: 300px;
}

/* Settings Select */
.settings-select {
  padding: 8px 12px;
  border: 1px solid var(--border-input);
  border-radius: 6px;
  font-size: 14px;
  color: var(--text-primary);
  background: var(--color-white);
  cursor: pointer;
  transition: all 0.2s;
}

/* Radio Group */
.radio-group {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.radio-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: var(--text-primary);
  cursor: pointer;
}

.radio-label input[type="radio"] {
  width: 16px;
  height: 16px;
  cursor: pointer;
}

.radio-label:hover {
  color: var(--accent-color);
}

/* Settings Badge */
.settings-badge {
  padding: 4px 8px;
  background: var(--color-neutral-150);
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
}

/* Danger Zone */
.settings-group.danger-zone {
  border-color: var(--color-red-200);
  background: var(--color-red-50);
  padding: 20px;
  border-radius: 8px;
}

.settings-group.danger-zone .settings-group-title {
  color: var(--color-red-700);
}

.btn-danger {
  padding: 8px 16px;
  background: var(--color-red-600);
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-danger:hover {
  background: var(--color-red-700);
}

.btn-secondary {
  padding: 8px 16px;
  background: var(--color-neutral-150);
  color: var(--text-primary);
  border: 1px solid var(--border-card);
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-secondary:hover {
  background: var(--bg-card-hover);
  border-color: var(--accent-bright);
}

.bank-file-item:hover {
  background: var(--bg-card-hover);
  border-color: var(--accent-bright);
}

/* Settings Responsive Layout */
@media (max-width: 1050px) {
  .settings-item {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .settings-item-info {
    width: 100%;
  }

  .settings-control {
    width: 100%;
    justify-content: flex-start;
  }

  .settings-select {
    width: 100%;
    max-width: 300px;
  }
}
</style>

<style scoped>
/* Advanced Settings Styles */
.settings-header {
  margin-bottom: 24px;
}

.loading-settings {
  text-align: center;
  color: var(--text-secondary);
  padding: 40px;
}

.start-settings-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.settings-card {
  border: 1px solid var(--color-neutral-250);
  border-radius: 10px;
  background: var(--bg-card);
}

.section-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px;
  background: var(--color-neutral-100);
  border-bottom: 1px solid var(--color-neutral-250);
  border-radius: 10px 10px 0 0;
}

.section-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 6px;
  background: var(--accent-soft, var(--color-accent-50));
  color: var(--accent-color, var(--color-accent-600));
  flex-shrink: 0;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 2px 0;
}

.section-description {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 0;
}

.section-content {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-label {
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  font-size: 14px;
}

.form-hint {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0;
}

.form-hint a {
  color: var(--accent-color, var(--color-accent-600));
}

.current-key {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: var(--color-neutral-100);
  border-radius: 8px;
  font-size: 13px;
}

.key-status {
  display: flex;
  align-items: center;
  gap: 4px;
  font-weight: 500;
}

.key-status.valid {
  color: var(--color-success-700);
}

.masked-key {
  font-family: monospace;
  font-size: 12px;
  color: var(--text-secondary);
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.btn-link {
  background: none;
  border: none;
  font-size: 13px;
  cursor: pointer;
  padding: 4px 8px;
}

.btn-link.danger {
  color: var(--color-danger-700);
}

.btn-link.danger:hover {
  text-decoration: underline;
}

.input-group {
  display: flex;
  border: 1px solid var(--color-neutral-250);
  border-radius: 8px;
  overflow: hidden;
  transition: all 0.2s;
}

.input-group:focus-within {
  border-color: var(--accent-color);
  box-shadow: 0 0 0 2px var(--alpha-accent-10);
}

.form-input {
  flex: 1;
  padding: 10px 12px;
  border: none;
  font-size: 14px;
  font-family: inherit;
  outline: none;
  background: var(--bg-input);
  color: var(--text-primary);
}

/* Hide browser's native password reveal button */
.form-input::-ms-reveal,
.form-input::-ms-clear {
  display: none;
}

.input-addon {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 12px;
  background: var(--bg-input);
  border: none;
  border-left: 1px solid var(--color-neutral-250);
  cursor: pointer;
  color: var(--text-secondary);
}

.input-addon:hover {
  color: var(--text-primary);
  background: var(--bg-card-hover);
}

.error-message {
  color: var(--color-danger-700);
  font-size: 13px;
}

.success-message {
  color: var(--color-success-700);
  font-size: 13px;
  padding: 10px 12px;
  background: var(--color-success-50);
  border-radius: 8px;
  border: 1px solid var(--color-success-200);
}

.validation-result {
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--bg-panel);
  border: 1px solid var(--border-color);
}

.validation-result .status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
}

.validation-result .status.valid {
  color: var(--color-success-700);
}

.validation-result .status.invalid {
  color: var(--color-danger-700);
}

.balance-panel {
  border: 1px solid var(--color-neutral-250);
  border-radius: 8px;
  background: var(--color-neutral-100);
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.balance-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.balance-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.balance-warning {
  font-size: 12px;
  color: var(--color-danger-700);
  background: var(--color-danger-50);
  border: 1px solid var(--color-danger-200);
  padding: 2px 8px;
  border-radius: 999px;
}

.balance-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.balance-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.balance-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 13px;
  color: var(--text-primary);
}

.balance-currency {
  font-weight: 600;
}

.balance-amount {
  font-variant-numeric: tabular-nums;
}

.balance-meta {
  font-size: 12px;
  color: var(--text-secondary);
}

.api-input-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.api-input-row .input-group {
  flex: 1;
}

.api-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.btn-primary-sm {
  background: var(--accent-color);
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-primary-sm:hover:not(:disabled) {
  background: var(--accent-hover);
}

.btn-primary-sm:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-outline {
  background: transparent;
  color: var(--accent-color);
  border: 1px solid var(--accent-color);
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-outline:hover:not(:disabled) {
  background: var(--accent-soft);
}

.btn-outline:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.llm-setup-intro {
  padding: 12px 14px;
  border: 1px dashed var(--color-neutral-250);
  border-radius: 10px;
  background: var(--color-neutral-100);
}

.llm-setup-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.llm-setup-grid {
  display: grid;
  gap: 16px;
  margin-top: 16px;
}

.llm-setup-step {
  display: grid;
  grid-template-columns: 28px 1fr;
  gap: 12px;
  padding: 14px;
  border: 1px solid var(--color-neutral-250);
  border-radius: 12px;
  background: var(--bg-input);
}

.step-badge {
  width: 26px;
  height: 26px;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--accent-soft, var(--color-accent-50));
  color: var(--accent-color, var(--color-accent-600));
  font-size: 12px;
  font-weight: 600;
}

.step-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
}

.step-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.step-desc {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 0;
}

.llm-config-actions {
  display: flex;
  justify-content: flex-end;
  padding-top: 4px;
  gap: 8px;
}

.model-select-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.model-select-row :deep(.custom-select-wrapper) {
  flex: 1;
  min-width: 0;
}

@media (max-width: 640px) {
  .llm-config-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .model-select-row {
    align-items: stretch;
  }

  .model-select-row .btn {
    width: 100%;
  }
}

/* Danger Zone specific */
.danger-zone-card {
  border-color: var(--color-danger-200);
}

.danger-zone-card .section-header {
  background: var(--color-danger-50);
  border-bottom-color: var(--color-danger-200);
}

.danger-icon {
  background: var(--color-danger-100) !important;
  color: var(--color-danger-700) !important;
}

.danger-zone-card .section-title {
  color: var(--color-danger-700);
}

.danger-zone-card .section-description {
  color: var(--color-danger-600);
}

.btn-danger-action {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: var(--color-danger-600);
  color: white;
  border: none;
  padding: 10px 16px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  width: fit-content;
}

.btn-danger-action:hover:not(:disabled) {
  background: var(--color-danger-700);
}

.btn-danger-action:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Updates Section */
.section-header-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
}

.update-badge {
  font-size: 11px;
  padding: 4px 10px;
  border-radius: 12px;
  font-weight: 500;
  white-space: nowrap;
}

.update-badge.neutral {
  background: var(--color-neutral-150);
  color: var(--text-secondary);
}

.update-badge.current {
  background: var(--color-success-50);
  color: var(--color-success-700);
}

.update-badge.available {
  background: var(--color-warning-100);
  color: var(--color-warning-800);
}

.update-badge.error {
  background: var(--color-danger-50);
  color: var(--color-danger-700);
}

[data-theme="dark"] .update-badge.neutral {
  background: var(--color-neutral-800);
  color: var(--text-secondary);
}

[data-theme="dark"] .update-badge.current {
  background: rgba(16, 185, 129, 0.15);
  color: var(--color-success-400);
}

[data-theme="dark"] .update-badge.available {
  background: rgba(245, 158, 11, 0.15);
  color: var(--color-warning-400);
}

[data-theme="dark"] .update-badge.error {
  background: rgba(239, 68, 68, 0.15);
  color: var(--color-danger-400);
}

.update-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

@media (max-width: 640px) {
  .api-input-row {
    flex-direction: column;
    align-items: stretch;
  }

  .api-actions {
    justify-content: flex-end;
  }
}

/* Preferences Section Styles */
.pref-setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
}

.pref-setting-info {
  flex: 1;
}

.pref-setting-info .form-label {
  margin-bottom: 4px;
}

.pref-setting-info .form-hint {
  margin: 0;
}

.pref-setting-row :deep(.custom-select-wrapper) {
  min-width: 160px;
}

/* Radio Group Vertical */
.radio-group-vertical {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.radio-option {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
  border: 1px solid var(--color-neutral-250);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  background: var(--bg-input);
}

.radio-option:hover {
  border-color: var(--accent-color);
  background: var(--color-neutral-100);
}

.radio-option:has(input:checked) {
  border-color: var(--accent-color);
  background: var(--accent-soft, var(--color-accent-50));
}

.radio-option input[type="radio"] {
  width: 18px;
  height: 18px;
  margin: 0;
  margin-top: 1px;
  cursor: pointer;
  flex-shrink: 0;
  align-self: center;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  appearance: none;
  -webkit-appearance: none;
  border: 2px solid var(--color-neutral-300);
  border-radius: 50%;
  position: relative;
  background: var(--bg-card);
}

.radio-option input[type="radio"]:hover {
  border-color: var(--accent-color);
}

.radio-option input[type="radio"]:checked {
  border-color: var(--accent-color);
  background: var(--bg-card);
}

.radio-option input[type="radio"]:checked::before {
  content: "";
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%) scale(1);
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--accent-color);
  transition: transform 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.radio-option input[type="radio"]:not(:checked)::before {
  content: "";
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%) scale(0);
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--accent-color);
  transition: transform 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.radio-option-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.radio-option-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.radio-option-desc {
  font-size: 12px;
  color: var(--text-secondary);
}

@media (max-width: 1050px) {
  .pref-setting-row {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .pref-setting-row :deep(.custom-select-wrapper) {
    width: 100%;
  }
}

@media (max-width: 640px) {
  .pref-setting-row {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .pref-setting-row :deep(.custom-select-wrapper) {
    width: 100%;
  }
}
</style>
