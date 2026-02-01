<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from "vue";
import { useRouter } from "vue-router";
import {
  fetchProjects,
  createProject,
  fetchBankManifest,
  fetchFileStats,
  deleteFileStream,
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
  saveCitationCopyFormat,
  fetchCrawlerConfig,
  updateCrawlerConfig,
} from "../api/client";
import type {
  Project,
  ManifestEntry,
  BalanceInfo,
  Settings as AppSettings,
  UpdateCheck,
  CitationCopyFormat,
  BibliographyAuthor,
  CrawlerConfig,
} from "../types";
import ProjectCard from "./ProjectCard.vue";
import FileUploader from "./FileUploader.vue";
import FilePreviewModal from "./FilePreviewModal.vue";
import ConfirmationModal from "./ConfirmationModal.vue";
import CustomSelect from "./CustomSelect.vue";
import BankFileSelectorModal from "./BankFileSelectorModal.vue";
import CrawlerSearchModal from "./CrawlerSearchModal.vue";
import SettingsAdvancedSection from "./SettingsAdvancedSection.vue";
import SettingsCrawlerSection from "./SettingsCrawlerSection.vue";
import SettingsPreferencesSection from "./SettingsPreferencesSection.vue";
import {
  Plus,
  Search,
  Loader2,
  Upload,
  FileText,
  Trash2,
  Settings,
  X,
  RefreshCw,
  Globe,
  LayoutGrid,
} from "lucide-vue-next";
import { type Theme, getStoredTheme, setTheme } from "../utils/theme";
import { getFileName } from "../utils";
import { usePdfSettings } from "../composables/usePdfSettings";
import { useQueue } from "../composables/useQueue";

const router = useRouter();
const isDev = import.meta.env.DEV;
const activeTab = ref<"projects" | "bank" | "settings">("projects");
const settingsSection = ref<"preferences" | "crawler" | "advanced">(
  "preferences",
);
const currentTheme = ref<Theme>("system");
const projects = ref<Project[]>([]);
const bankFiles = ref<ManifestEntry[]>([]);
const loading = ref(true);
const bankLoading = ref(false);
const searchQuery = ref("");

// Bank filter & sort state
const bankSearchQuery = ref("");
const bankFileStats = ref<
  Record<string, { usage_count: number; last_used: number }>
>({});
const bankFilters = ref({
  fileTypes: new Set<string>(),
  years: new Set<string>(),
  language: null as string | null,
});
const bankSortBy = ref<"usage" | "name" | "year" | "added">("usage");
const bankSortOrder = ref<"asc" | "desc">("desc");

const bankSortOptions = [
  { value: "usage", label: "Usage" },
  { value: "name", label: "Name" },
  { value: "year", label: "Year" },
  { value: "added", label: "Date Added" },
];
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

// Crawler Settings
const showCrawlerModal = ref(false);
const crawlerConfig = ref<CrawlerConfig | null>(null);

// Display Settings
const filesPerPage = ref(7);
const notesPerPage = ref(4);
const chatsPerPage = ref(0); // 0 = unlimited
const citationCopyFormat = ref<CitationCopyFormat>("apa");
const isSavingCitation = ref(false);

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
const { launchQueueEject } = useQueue();

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

const citationFormatOptions = [
  { value: "apa", label: "APA (Author, Year)" },
  { value: "mla", label: "MLA (Author Page)" },
  { value: "chicago", label: "Chicago (Author Year, Page)" },
  { value: "gbt7714", label: "GB/T 7714 [n]" },
  { value: "numeric", label: "Numeric [1]" },
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
    const [manifest, stats] = await Promise.all([
      fetchBankManifest(),
      fetchFileStats(),
    ]);
    bankFiles.value = manifest;
    bankFileStats.value = stats;
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

// Bank helper functions
function formatAuthors(
  authors: BibliographyAuthor[] | string | undefined,
): string {
  if (!authors) return "";
  if (typeof authors === "string") return authors;
  const names = authors
    .map((a) => {
      if (a.literal) return a.literal;
      if (a.family && a.given) return `${a.given} ${a.family}`;
      return a.family || a.given || "";
    })
    .filter(Boolean);
  if (names.length === 0) return "";
  if (names.length <= 2) return names.join(" & ");
  return `${names[0]} et al.`;
}

function truncateText(str: string | undefined | null, len: number): string {
  if (!str || str.length <= len) return str || "";
  return str.slice(0, len) + "...";
}

// Bank filter computed properties
const availableBankTypes = computed(() => {
  const types = new Set(bankFiles.value.map((f) => f.fileType));
  return Array.from(types).sort();
});

const availableBankYears = computed(() => {
  const years = new Set<string>();
  bankFiles.value.forEach((f) => {
    if (f.bibliography?.year) years.add(f.bibliography.year.toString());
  });
  return Array.from(years).sort().reverse().slice(0, 5);
});

const hasActiveBankFilters = computed(() => {
  return (
    bankFilters.value.fileTypes.size > 0 ||
    bankFilters.value.years.size > 0 ||
    bankFilters.value.language !== null
  );
});

function toggleBankFilter(filterKey: "fileTypes" | "years", value: string) {
  const filterSet = bankFilters.value[filterKey];
  if (filterSet.has(value)) {
    filterSet.delete(value);
  } else {
    filterSet.add(value);
  }
  bankFilters.value[filterKey] = new Set(filterSet);
}

function clearAllBankFilters() {
  bankFilters.value.fileTypes.clear();
  bankFilters.value.years.clear();
  bankFilters.value.language = null;
  bankFilters.value = { ...bankFilters.value };
  bankSearchQuery.value = "";
}

function sortBankFiles(files: ManifestEntry[]): ManifestEntry[] {
  return [...files].sort((a, b) => {
    const multiplier = bankSortOrder.value === "asc" ? 1 : -1;

    switch (bankSortBy.value) {
      case "usage": {
        const usageA = bankFileStats.value[a.relPath]?.usage_count || 0;
        const usageB = bankFileStats.value[b.relPath]?.usage_count || 0;
        if (usageA !== usageB) return (usageB - usageA) * multiplier;

        const timeA = bankFileStats.value[a.relPath]?.last_used || 0;
        const timeB = bankFileStats.value[b.relPath]?.last_used || 0;
        if (timeA !== timeB) return (timeB - timeA) * multiplier;
        break;
      }
      case "name":
        return (
          getFileName(a.relPath).localeCompare(getFileName(b.relPath)) *
          multiplier
        );
      case "year": {
        const yearA = a.bibliography?.year || 0;
        const yearB = b.bibliography?.year || 0;
        if (yearA !== yearB) return (yearB - yearA) * multiplier;
        break;
      }
      case "added": {
        const timeA = bankFileStats.value[a.relPath]?.last_used || 0;
        const timeB = bankFileStats.value[b.relPath]?.last_used || 0;
        return (timeB - timeA) * multiplier;
      }
    }

    // Default fallback: sort by file type then name
    if (a.fileType !== b.fileType) {
      return a.fileType.localeCompare(b.fileType);
    }
    return getFileName(a.relPath).localeCompare(getFileName(b.relPath));
  });
}

const sortedBankFiles = computed(() => {
  let files = bankFiles.value;

  // Text search (title, authors, filename)
  if (bankSearchQuery.value.trim()) {
    const query = bankSearchQuery.value.toLowerCase();
    files = files.filter((f) => {
      const name = getFileName(f.relPath).toLowerCase();
      const title = (f.bibliography?.title || "").toLowerCase();
      const authors = formatAuthors(f.bibliography?.authors).toLowerCase();
      return (
        name.includes(query) || title.includes(query) || authors.includes(query)
      );
    });
  }

  // File type filter
  if (bankFilters.value.fileTypes.size > 0) {
    files = files.filter((f) => bankFilters.value.fileTypes.has(f.fileType));
  }

  // Year filter
  if (bankFilters.value.years.size > 0) {
    files = files.filter((f) => {
      const year = f.bibliography?.year?.toString();
      return year && bankFilters.value.years.has(year);
    });
  }

  // Language filter
  if (bankFilters.value.language) {
    files = files.filter(
      (f) => f.bibliography?.language === bankFilters.value.language,
    );
  }

  return sortBankFiles(files);
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
    await deleteFileStream(relPath, {
      onComplete: async () => {
        await loadBankFiles();
        if (previewFile.value?.relPath === relPath) {
          previewFile.value = null;
        }
      },
      onError: (_code: string, message: string) => {
        console.error("Failed to delete file:", message);
      },
    });
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

async function handleReprocessConfirm(event?: MouseEvent) {
  if (event?.currentTarget instanceof HTMLElement) {
    const rect = event.currentTarget.getBoundingClientRect();
    launchQueueEject(rect.left + rect.width / 2, rect.top + rect.height / 2);
  }
  if (isReprocessing.value) return;
  try {
    isReprocessing.value = true;
    await reprocessReferenceBankStream({
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

async function handleReprocessFile(file: ManifestEntry, event?: MouseEvent) {
  if (event?.currentTarget instanceof HTMLElement) {
    const rect = event.currentTarget.getBoundingClientRect();
    launchQueueEject(rect.left + rect.width / 2, rect.top + rect.height / 2);
  }
  if (isReprocessing.value) return;
  try {
    isReprocessing.value = true;
    await reprocessReferenceFileStream(file.relPath, {
      onComplete: async () => {
        await loadBankFiles();
      },
      onError: (_code, message) => {
        console.error("Failed to reprocess file:", message);
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

async function handleCrawlerConfigUpdate(config: CrawlerConfig) {
  try {
    await updateCrawlerConfig(config);
    crawlerConfig.value = config;
  } catch (e) {
    console.error("Failed to save crawler config:", e);
  }
}

async function handleCrawlerDownloadComplete(entries: ManifestEntry[]) {
  // Add downloaded entries to bank files
  entries.forEach((entry) => upsertBankFile(entry));
  // Reload bank files to show new downloads
  await loadBankFiles();
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
        citationCopyFormat: "apa",
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

function toggleShowApiKey() {
  showApiKey.value = !showApiKey.value;
}

function updateApiKeyInput(value: string) {
  apiKeyInput.value = value;
}

function updateBaseUrlInput(value: string) {
  baseUrlInput.value = value;
}

function updateModelInput(value: string) {
  modelInput.value = value;
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

async function handleCitationFormatChange(format: string) {
  citationCopyFormat.value = format as CitationCopyFormat;
  isSavingCitation.value = true;
  try {
    await saveCitationCopyFormat(format);
    // Notify other components
    window.dispatchEvent(
      new CustomEvent("settingChanged", {
        detail: { key: "citationCopyFormat", value: format },
      }),
    );
  } catch (e) {
    console.error("Failed to save citation format:", e);
  } finally {
    isSavingCitation.value = false;
  }
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
    const [settingsData, version, crawlerData] = await Promise.all([
      getSettings(),
      fetchVersion().catch(() => ""),
      fetchCrawlerConfig().catch(() => null),
    ]);
    settings.value = settingsData;
    currentVersion.value = version;
    citationCopyFormat.value = settingsData.citationCopyFormat || "apa";
    syncLlmInputs(settingsData);
    if (crawlerData) {
      crawlerConfig.value = crawlerData;
    }
  } catch (e) {
    console.error("Failed to load settings:", e);
  } finally {
    isLoadingSettings.value = false;
  }
});

onUnmounted(() => {});
</script>

<template>
  <div class="project-hub-container">
    <header class="hub-header">
      <div class="header-left">
        <div class="logo">
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
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
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'projects' }"
          @click="activeTab = 'projects'"
        >
          <Search :size="16" />
          <span>Projects</span>
        </button>
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'bank' }"
          @click="switchToBank"
        >
          <FileText :size="16" />
          <span>Reference Bank</span>
        </button>
      </div>
      <div class="tabs-right">
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'settings' }"
          @click="activeTab = 'settings'"
        >
          <Settings :size="16" />
          <span>Settings</span>
        </button>
      </div>
    </div>

    <main
      class="hub-content"
      :class="{ 'settings-active': activeTab === 'settings' }"
    >
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
          <ProjectCard
            v-for="p in projects"
            :key="p.id"
            :project="p"
            @open="openProject"
            @delete="handleDeleteProject"
          />

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
            <button class="bank-action-btn" @click="showCrawlerModal = true">
              <Search :size="14" />
              <span>Search Online</span>
            </button>
            <button
              class="bank-action-btn"
              :disabled="isReprocessing || bankLoading"
              @click="
                handleReprocessConfirm($event);
                showReprocessConfirm = true;
              "
            >
              <Loader2 v-if="isReprocessing" class="spinner" :size="14" />
              <span>{{
                isReprocessing ? "Reprocessing..." : "Reprocess All"
              }}</span>
            </button>
          </div>
        </div>

        <FileUploader
          upload-mode="bank"
          @upload-complete="handleUploadComplete"
        />

        <!-- Search & Filter Section -->
        <div v-if="bankFiles.length > 0" class="bank-search-section">
          <div class="bank-search-wrapper">
            <Search :size="16" class="bank-search-icon" />
            <input
              v-model="bankSearchQuery"
              type="text"
              placeholder="Search by title, author, or filename..."
              class="bank-search-input"
            />
          </div>

          <!-- Filter Chips -->
          <div class="bank-filter-chips">
            <!-- File Type Chips -->
            <button
              v-for="type in availableBankTypes"
              :key="type"
              class="bank-filter-chip"
              :class="{ active: bankFilters.fileTypes.has(type) }"
              @click="toggleBankFilter('fileTypes', type)"
            >
              {{ type.toUpperCase() }}
            </button>

            <!-- Year Chips -->
            <button
              v-for="year in availableBankYears"
              :key="year"
              class="bank-filter-chip"
              :class="{ active: bankFilters.years.has(year) }"
              @click="toggleBankFilter('years', year)"
            >
              {{ year }}
            </button>

            <!-- Language Toggle -->
            <button
              class="bank-filter-chip"
              :class="{ active: bankFilters.language === 'zh' }"
              @click="
                bankFilters.language =
                  bankFilters.language === 'zh' ? null : 'zh'
              "
            >
              中文
            </button>

            <!-- Clear All Filters -->
            <button
              v-if="hasActiveBankFilters || bankSearchQuery"
              class="bank-filter-chip clear-filters"
              @click="clearAllBankFilters"
            >
              <X :size="12" />
              Clear
            </button>
          </div>

          <!-- Sort Controls & File Count -->
          <div class="bank-controls-row">
            <div class="bank-sort-controls">
              <span>Sort:</span>
              <CustomSelect
                v-model="bankSortBy"
                :options="bankSortOptions"
                class="bank-sort-select"
              />
            </div>
            <div class="bank-file-count">
              {{ sortedBankFiles.length }}
              <span v-if="sortedBankFiles.length !== bankFiles.length">
                of {{ bankFiles.length }}
              </span>
              file{{ sortedBankFiles.length === 1 ? "" : "s" }}
            </div>
          </div>
        </div>

        <div v-if="bankLoading" class="loading-state">
          <Loader2 class="spinner" :size="32" />
          <p>Loading files...</p>
        </div>

        <div v-else-if="bankFiles.length === 0" class="empty-state">
          <Upload :size="48" class="empty-icon-svg" />
          <h3>No files in Reference Bank</h3>
          <p>Upload files using the button above to get started.</p>
        </div>

        <div
          v-else-if="sortedBankFiles.length === 0"
          class="empty-state empty-state-compact"
        >
          <FileText :size="36" class="empty-icon-svg" />
          <p>No files match your search or filters</p>
        </div>

        <TransitionGroup
          v-else
          name="file-list"
          tag="div"
          class="file-grid"
          @before-leave="handleBeforeLeave"
        >
          <div
            v-for="file in sortedBankFiles"
            :key="file.relPath"
            class="file-card"
            @click="handlePreview(file)"
          >
            <div class="file-icon">
              <FileText :size="24" />
            </div>
            <div class="file-info">
              <div class="file-name" :title="getFileName(file.relPath)">
                {{ getFileName(file.relPath) }}
              </div>
              <div
                v-if="file.bibliography?.title"
                class="file-title"
                :title="file.bibliography.title"
              >
                {{ truncateText(file.bibliography.title, 60) }}
              </div>
              <div
                v-if="file.bibliography?.authors || file.bibliography?.year"
                class="file-authors"
              >
                {{ formatAuthors(file.bibliography?.authors) }}
                <span
                  v-if="
                    formatAuthors(file.bibliography?.authors) &&
                    file.bibliography?.year
                  "
                >
                  ·
                </span>
                {{ file.bibliography?.year }}
              </div>
              <div class="file-meta">
                {{ file.fileType }} ·
                {{ Math.round((file.sizeBytes || 0) / 1024) }}KB
                <span
                  v-if="bankFileStats[file.relPath]?.usage_count"
                  class="usage-badge"
                >
                  {{ bankFileStats[file.relPath].usage_count }} project{{
                    bankFileStats[file.relPath].usage_count > 1 ? "s" : ""
                  }}
                </span>
              </div>
            </div>
            <div class="file-actions">
              <button
                class="btn-icon tooltip"
                data-tooltip="Reprocess file"
                @click.stop="handleReprocessFile(file, $event)"
              >
                <RefreshCw :size="16" />
              </button>
              <button
                class="btn-icon delete tooltip"
                data-tooltip="Delete file"
                @click.stop="requestDelete(file)"
              >
                <Trash2 :size="16" />
              </button>
            </div>
          </div>
        </TransitionGroup>
      </div>

      <!-- Settings Tab -->
      <div v-else-if="activeTab === 'settings'" class="settings-container">
        <aside class="settings-sidebar">
          <nav class="settings-nav">
            <button
              class="settings-nav-item"
              :class="{ active: settingsSection === 'preferences' }"
              @click="settingsSection = 'preferences'"
            >
              <Settings :size="18" />
              <span>Preferences</span>
            </button>
            <button
              class="settings-nav-item"
              :class="{ active: settingsSection === 'crawler' }"
              @click="settingsSection = 'crawler'"
            >
              <Globe :size="18" />
              <span>Crawler</span>
            </button>
            <button
              class="settings-nav-item"
              :class="{ active: settingsSection === 'advanced' }"
              @click="settingsSection = 'advanced'"
            >
              <LayoutGrid :size="18" />
              <span>Advanced</span>
            </button>
          </nav>
        </aside>

        <main class="settings-content">
          <SettingsPreferencesSection
            v-if="settingsSection === 'preferences'"
            :current-theme="currentTheme"
            :theme-options="themeOptions"
            :on-theme-change="setTheme"
            :view-mode="viewMode"
            :pdf-view-options="pdfViewOptions"
            :on-view-mode-change="setViewMode"
            :citation-copy-format="citationCopyFormat"
            :citation-format-options="citationFormatOptions"
            :is-saving-citation="isSavingCitation"
            :on-citation-format-change="handleCitationFormatChange"
            :files-per-page="filesPerPage"
            :notes-per-page="notesPerPage"
            :chats-per-page="chatsPerPage"
            :on-display-setting-change="saveDisplaySetting"
          />

          <SettingsCrawlerSection
            v-else-if="settingsSection === 'crawler'"
            :crawler-config="crawlerConfig"
            :on-update="handleCrawlerConfigUpdate"
          />

          <SettingsAdvancedSection
            v-else-if="settingsSection === 'advanced'"
            :is-loading-settings="isLoadingSettings"
            :is-saving="isSaving"
            :is-saving-llm="isSavingLlm"
            :is-validating="isValidating"
            :is-checking-update="isCheckingUpdate"
            :is-resetting="isResetting"
            :validation-status="validationStatus"
            :validation-error="validationError"
            :api-key-status-message="apiKeyStatusMessage"
            :balance-infos="balanceInfos"
            :balance-available="balanceAvailable"
            :save-error="saveError"
            :llm-save-error="llmSaveError"
            :llm-save-success="llmSaveSuccess"
            :reset-error="resetError"
            :reset-success="resetSuccess"
            :base-url-input="baseUrlInput"
            :model-input="modelInput"
            :update-info="updateInfo"
            :update-error="updateError"
            :current-version-label="currentVersionLabel"
            :last-checked-label="lastCheckedLabel"
            :update-badge-text="updateBadgeText"
            :update-badge-class="updateBadgeClass"
            :provider-options="providerOptions"
            :selected-provider="selectedProvider"
            :current-provider-link="currentProviderLink"
            :current-provider-key="currentProviderKey"
            :show-api-key="showApiKey"
            :api-key-input="apiKeyInput"
            :model-options="modelOptions"
            :is-loading-models="isLoadingModels"
            :on-set-provider="setProvider"
            :on-validate="handleValidate"
            :on-save-api-key="handleSave"
            :on-delete-api-key="handleDeleteApiKey"
            :on-load-models="handleLoadModels"
            :on-save-llm-settings="handleSaveLlmSettings"
            :on-update-check="handleUpdateCheck"
            :on-reset-click="handleResetClick"
            :on-toggle-show-api-key="toggleShowApiKey"
            :on-api-key-input="updateApiKeyInput"
            :on-base-url-input="updateBaseUrlInput"
            :on-model-input="updateModelInput"
          />
        </main>
      </div>
    </main>
  </div>

  <!-- Create Modal -->
  <Transition name="fade">
    <div
      v-if="showCreateModal"
      class="modal-mask"
      @click.self="showCreateModal = false"
    >
      <div class="modal-container">
        <h2>Create New Study</h2>
        <div class="form-group">
          <label>Project Name</label>
          <input
            v-model="newProjectName"
            placeholder="e.g. Photovoltaic Research"
            autofocus
          />
        </div>
        <div class="form-group">
          <label>Description (Optional)</label>
          <textarea
            v-model="newProjectDesc"
            placeholder="What is this study about?"
            rows="3"
          ></textarea>
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
          <button
            class="btn-primary"
            :disabled="!newProjectName.trim() || creating"
            @click="handleCreate"
          >
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
  <ConfirmationModal
    v-model="showDeleteModal"
    title="Delete File?"
    :message="
      fileToDelete
        ? `Delete '${getFileName(fileToDelete.relPath)}'? This will remove it from all projects. This action cannot be undone.`
        : ''
    "
    confirmText="Delete"
    @confirm="confirmDelete"
    @cancel="cancelDelete"
  />

  <!-- Delete Project Confirmation Modal -->
  <ConfirmationModal
    v-model="showDeleteProjectModal"
    title="Delete Project?"
    :message="
      projectToDelete
        ? `Delete '${projectToDelete.name}'? This will remove the project and all its notes. Files will remain in the Reference Bank.`
        : ''
    "
    confirmText="Delete"
    @confirm="confirmDeleteProject"
    @cancel="cancelDeleteProject"
  />

  <!-- Initial File Selector -->
  <BankFileSelectorModal
    v-model="showFileSelectorForCreate"
    :selected-files="selectedFilesForCreate"
    @confirm="handleInitialFilesSelected"
  />

  <!-- Reset Confirmation Modal -->
  <ConfirmationModal
    v-model="showResetConfirm"
    title="Clear All Data?"
    message="This will permanently delete all indexed chunks, search indexes, and chat sessions. Your files will remain in the reference folder. This action cannot be undone."
    confirm-text="Clear All Data"
    cancel-text="Cancel"
    @confirm="handleResetConfirm"
  />

  <!-- Reprocess Reference Bank -->
  <ConfirmationModal
    v-model="showReprocessConfirm"
    title="Reprocess Reference Bank?"
    message="This will delete all indexed data and rebuild from files in reference folder. Your files will remain untouched."
    confirm-text="Reprocess"
    cancel-text="Cancel"
    @confirm="handleReprocessConfirm"
    @cancel="showReprocessConfirm = false"
  />

  <!-- Crawler Search Modal -->
  <CrawlerSearchModal
    v-model="showCrawlerModal"
    @download-complete="handleCrawlerDownloadComplete"
  />
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
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  margin-top: 24px;
}

@media (max-width: 1200px) {
  .file-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .file-grid {
    grid-template-columns: minmax(0, 1fr);
  }
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
  position: relative;
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
  background: var(--accent-soft);
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

/* Bank Search & Filter Section */
.bank-search-section {
  margin-top: 24px;
  padding: 16px 20px;
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: 12px;
}

.bank-search-wrapper {
  position: relative;
  margin-bottom: 12px;
}

.bank-search-icon {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-secondary);
}

.bank-search-input {
  width: 100%;
  padding: 10px 12px 10px 36px;
  border: 1px solid var(--border-card);
  border-radius: 8px;
  font-size: 14px;
  background: var(--bg-input);
  color: var(--text-primary);
  transition: border-color 0.2s;
}

.bank-search-input:focus {
  outline: none;
  border-color: var(--border-input-focus);
  box-shadow: 0 0 0 3px rgba(var(--accent-color-rgb), 0.1);
}

.bank-search-input::placeholder {
  color: var(--text-secondary);
}

/* Filter Chips */
.bank-filter-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.bank-filter-chip {
  padding: 4px 10px;
  background: var(--color-neutral-100);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s;
}

.bank-filter-chip:hover {
  background: var(--color-neutral-150);
  border-color: var(--border-card-hover, var(--border-color));
}

.bank-filter-chip.active {
  background: var(--accent-soft, rgba(var(--accent-color-rgb), 0.1));
  border-color: var(--accent-color);
  color: var(--accent-color);
}

.bank-filter-chip.clear-filters {
  background: var(--color-danger-50);
  border-color: var(--color-danger-200);
  color: var(--color-danger-600);
  display: flex;
  align-items: center;
  gap: 4px;
}

.bank-filter-chip.clear-filters:hover {
  background: var(--color-danger-100);
}

/* Controls Row */
.bank-controls-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.bank-sort-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-secondary);
}

.bank-sort-select {
  min-width: 110px;
}

.bank-sort-select :deep(.custom-select-trigger) {
  padding: 5px 10px;
  min-width: 110px;
  border-radius: 6px;
}

.bank-sort-select :deep(.custom-select-label) {
  font-size: 12px;
}

.bank-sort-select :deep(.custom-options) {
  min-width: 110px;
}

.bank-sort-select :deep(.custom-option) {
  padding: 8px 10px;
  font-size: 12px;
}

.bank-file-count {
  font-size: 13px;
  color: var(--text-secondary);
}

/* Enhanced File Card Metadata */
.file-title {
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-style: italic;
  margin-top: 2px;
}

.file-authors {
  font-size: 11px;
  color: var(--text-tertiary, var(--text-secondary));
  margin-top: 1px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
}

.usage-badge {
  background: var(--color-neutral-120);
  color: var(--text-secondary);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
  text-transform: none;
}

/* Empty state for filtered results */
.empty-state-compact {
  padding: 40px 20px;
  min-height: auto;
}

.empty-state-compact p {
  margin: 0;
  font-size: 14px;
}

/* Dark mode adjustments for bank section */
[data-theme="dark"] .bank-search-section {
  background: var(--color-neutral-105);
  border-color: var(--color-neutral-150);
}

[data-theme="dark"] .bank-search-input {
  background: var(--color-neutral-150);
  border-color: var(--color-neutral-200);
}

[data-theme="dark"] .bank-search-input:focus {
  border-color: var(--border-input-focus);
  box-shadow: 0 0 0 3px rgba(var(--accent-color-rgb), 0.15);
}

[data-theme="dark"] .bank-filter-chip {
  background: var(--color-neutral-150);
  border-color: var(--color-neutral-200);
}

[data-theme="dark"] .bank-filter-chip:hover {
  background: var(--color-neutral-200);
}

[data-theme="dark"] .bank-filter-chip.active {
  background: var(--accent-soft);
  border-color: var(--accent-color);
  color: var(--accent-color);
}

[data-theme="dark"] .bank-filter-chip.clear-filters {
  background: var(--color-danger-50);
  border-color: var(--color-danger-200);
  color: var(--color-danger-400);
}

[data-theme="dark"] .bank-filter-chip.clear-filters:hover {
  background: var(--color-danger-100);
}

[data-theme="dark"] .usage-badge {
  background: var(--color-neutral-150);
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
  position: relative;
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

/* Note: .settings-card, .section-header, .section-icon, .section-title,
   .section-description, .section-content are defined globally in style.css */

/* Form label/hint overrides for this component */
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

/* Note: .danger-zone-card styles are defined globally in style.css */

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

/* Note: .setting-control .custom-select-wrapper width is set globally in style.css */

/* Radio Inline Group (horizontal) */
.radio-inline-group {
  display: flex;
  gap: 16px;
}

.radio-inline-option {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border: 1px solid var(--color-neutral-250);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  background: var(--bg-input);
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.radio-inline-option:hover {
  border-color: var(--accent-color);
  background: var(--color-neutral-100);
}

.radio-inline-option:has(input:checked) {
  border-color: var(--accent-color);
  background: var(--accent-soft, var(--color-accent-50));
  color: var(--accent-color);
}

.radio-inline-option input[type="radio"] {
  width: 14px;
  height: 14px;
  margin: 0;
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  appearance: none;
  -webkit-appearance: none;
  border: 2px solid var(--color-neutral-300);
  border-radius: 50%;
  position: relative;
  background: var(--bg-card);
}

.radio-inline-option input[type="radio"]:hover {
  border-color: var(--accent-color);
}

.radio-inline-option input[type="radio"]:checked {
  border-color: var(--accent-color);
  background: var(--bg-card);
}

.radio-inline-option input[type="radio"]:checked::before {
  content: "";
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%) scale(1);
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent-color);
  transition: transform 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.radio-inline-option input[type="radio"]:not(:checked)::before {
  content: "";
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%) scale(0);
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent-color);
  transition: transform 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

@media (max-width: 640px) {
  .radio-inline-group {
    flex-direction: column;
    gap: 8px;
  }
}
</style>
