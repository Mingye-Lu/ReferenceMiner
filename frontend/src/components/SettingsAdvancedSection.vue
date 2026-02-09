<script setup lang="ts">
import { ref, computed, watch } from "vue";
import type { BalanceInfo, UpdateCheck, OcrConfig, OcrModelInfo } from "../types";
import { ArrowUpRight, Check, Key, Trash, Trash2, X, ScanText, Download, Pause, Play } from "lucide-vue-next";
import CustomSelect from "./CustomSelect.vue";

const DEFAULT_HUGGING_FACE_BASE_URL = "https://huggingface.co";

interface ProviderOption {
  value: string;
  label: string;
}

interface ProviderLink {
  url: string;
  label: string;
}

interface ProviderKey {
  hasKey: boolean;
  maskedKey: string | null;
}

interface ModelOption {
  value: string;
  label: string;
}

const props = defineProps<{
  isLoadingSettings: boolean;
  isSaving: boolean;
  isSavingLlm: boolean;
  isValidating: boolean;
  isCheckingUpdate: boolean;
  isResetting: boolean;
  validationStatus: "none" | "valid" | "invalid";
  validationError: string;
  apiKeyStatusMessage: string;
  balanceInfos: BalanceInfo[];
  balanceAvailable: boolean | null;
  saveError: string;
  llmSaveError: string;
  llmSaveSuccess: string;
  resetError: string;
  resetSuccess: string;
  baseUrlInput: string;
  modelInput: string;
  updateInfo: UpdateCheck | null;
  updateError: string;
  currentVersionLabel: string;
  lastCheckedLabel: string;
  updateBadgeText: string;
  updateBadgeClass: string;
  providerOptions: ProviderOption[];
  selectedProvider: string;
  currentProviderLink: ProviderLink;
  currentProviderKey: ProviderKey;
  showApiKey: boolean;
  apiKeyInput: string;
  modelOptions: ModelOption[];
  isLoadingModels: boolean;
  onSetProvider: (value: string) => void;
  onValidate: () => void;
  onSaveApiKey: () => void;
  onDeleteApiKey: () => void;
  onLoadModels: () => void;
  onSaveLlmSettings: () => void;
  onUpdateCheck: () => void;
  onResetClick: () => void;
  onToggleShowApiKey: () => void;
  onApiKeyInput: (value: string) => void;
  onBaseUrlInput: (value: string) => void;
  onModelInput: (value: string) => void;
  ocrConfig: OcrConfig;
  ocrModels: Record<string, OcrModelInfo>;
  isSavingOcr: boolean;
  isDownloadingOcr: boolean;
  onSaveOcrSettings: (config: OcrConfig) => void;
  onDownloadOcrModel: (model: string) => void;
  downloadProgress: number | null;
  downloadState: string; // idle, downloading, paused, cancelled, completed
  onDeleteOcrModel: (model: string) => void;
  onPauseOcrDownload?: (model: string) => void;
  onResumeOcrDownload?: (model: string) => void;
  onCancelOcrDownload?: (model: string) => void;
  onOcrModelChange?: (model: string) => void;
}>();

const onInput = (event: Event, handler: (value: string) => void) => {
  const target = event.target as HTMLInputElement;
  handler(target.value);
};

// OCR Logic
// Initialize with default values to avoid accessing undefined properties
const localOcrConfig = ref<OcrConfig>({
  model: "paddle-mobile",
  base_url: DEFAULT_HUGGING_FACE_BASE_URL,
  api_key: "",
});

watch(
  () => props.ocrConfig,
  (newVal) => {
    if (newVal) {
      localOcrConfig.value = {
        ...newVal,
        base_url: newVal.base_url?.trim() || DEFAULT_HUGGING_FACE_BASE_URL,
      };
    }
  },
  { immediate: true, deep: true },
);

const ocrModelOptions = computed(() => {
  if (!props.ocrModels) return [];
  return Object.entries(props.ocrModels).map(([key, info]) => ({
    value: key,
    label: info.label,
  }));
});

const currentOcrModelInfo = computed(() => {
  if (!props.ocrModels || !localOcrConfig.value.model) return null;
  return props.ocrModels[localOcrConfig.value.model];
});

const isExternalOcr = computed(
  () => localOcrConfig.value.model === "external",
);

const hasDownloadProgress = computed(
  () => props.downloadProgress !== null && props.downloadProgress >= 0,
);

const isDownloadPaused = computed(() => props.downloadState === "paused");

const isDownloadActive = computed(
  () => hasDownloadProgress.value && (props.downloadProgress ?? 0) < 100,
);

const canDownloadCurrentModel = computed(() => {
  if (isExternalOcr.value || !currentOcrModelInfo.value) return false;
  return (
    currentOcrModelInfo.value.is_downloadable &&
    !currentOcrModelInfo.value.installed &&
    !hasDownloadProgress.value
  );
});

const ocrStatusLabel = computed(() => {
  if (isExternalOcr.value) return "External API";
  if (isDownloadPaused.value) return "Download paused";
  if (isDownloadActive.value) return "Downloading";
  if (currentOcrModelInfo.value?.installed) return "Installed";
  if (currentOcrModelInfo.value?.is_downloadable) return "Not downloaded";
  return "Manual setup";
});

const ocrStatusClass = computed(() => {
  if (isExternalOcr.value) return "neutral";
  if (isDownloadPaused.value) return "warning";
  if (isDownloadActive.value) return "info";
  if (currentOcrModelInfo.value?.installed) return "success";
  if (currentOcrModelInfo.value?.is_downloadable) return "warning";
  return "neutral";
});

// Watch for model changes to notify parent to clear download state
watch(
  () => localOcrConfig.value.model,
  (newModel) => {
    props.onOcrModelChange?.(newModel);
  },
);

function saveOcr() {
  props.onSaveOcrSettings(localOcrConfig.value);
}

function downloadOcr() {
  props.onDownloadOcrModel(localOcrConfig.value.model);
}
</script>

<template>
  <div class="settings-section-container">
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
            <Key :size="16" />
          </div>
          <div>
            <h4 class="section-title">API Configuration</h4>
            <p class="section-description">
              Configure your provider, API key, and model for AI-powered answers
            </p>
          </div>
        </div>

        <div class="section-content">
          <div class="llm-setup-intro">
            <div class="llm-setup-title">Quick setup</div>
            <p class="form-hint">
              Choose a provider, add your API key, then load and save a model.
              Presets: ChatGPT, Gemini, Anthropic, DeepSeek.
            </p>
          </div>

          <div class="llm-setup-grid">
            <div class="llm-setup-step">
              <div class="step-badge">1</div>
              <div class="step-body">
                <div class="step-title">Provider preset</div>
                <p class="step-desc">
                  ChatGPT, Gemini, Anthropic, DeepSeek, or a custom endpoint.
                </p>
                <CustomSelect :model-value="selectedProvider" :options="providerOptions" @update:model-value="
                  (value) => onSetProvider(value as string)
                " />
              </div>
            </div>

            <div class="llm-setup-step">
              <div class="step-badge">2</div>
              <div class="step-body">
                <div class="step-title">API key</div>
                <p class="step-desc">
                  Stored per provider. If empty, validation will use any stored
                  key on the server.
                </p>
                <p v-if="currentProviderLink.url" class="form-hint">
                  Get your key from
                  <a :href="currentProviderLink.url" target="_blank" rel="noopener noreferrer">{{
                    currentProviderLink.label }}</a>
                </p>

                <div class="current-key" v-if="currentProviderKey.hasKey">
                  <span class="key-status valid">
                    <Check :size="14" />
                    Key configured
                  </span>
                  <span class="masked-key">{{
                    currentProviderKey.maskedKey
                  }}</span>
                  <button class="btn-link danger" @click="onDeleteApiKey" :disabled="isSaving">
                    Remove
                  </button>
                </div>

                <div class="api-input-row">
                  <div class="input-group">
                    <input :value="apiKeyInput" :type="showApiKey ? 'text' : 'password'" class="form-input"
                      :placeholder="currentProviderKey.hasKey
                        ? 'Enter new key to replace'
                        : 'Enter your API key'
                        " @input="(event) => onInput(event, onApiKeyInput)" />
                    <button class="input-addon" @click="onToggleShowApiKey" type="button">
                      <svg v-if="showApiKey" xmlns="http://www.w3.org/2000/svg" width="16" height="16"
                        viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"
                        stroke-linejoin="round">
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
                    <button class="btn btn-outline" @click="onValidate" :disabled="isValidating">
                      {{ isValidating ? "Validating..." : "Validate" }}
                    </button>
                    <button class="btn btn-primary-sm" @click="onSaveApiKey" :disabled="isSaving || !apiKeyInput">
                      {{ isSaving ? "Saving..." : "Save" }}
                    </button>
                  </div>
                </div>

                <div v-if="saveError" class="error-message">
                  {{ saveError }}
                </div>

                <div class="validation-result" v-if="validationStatus !== 'none'">
                  <span v-if="validationStatus === 'valid'" class="status valid">
                    <Check :size="14" />
                    {{ apiKeyStatusMessage }}
                  </span>
                  <span v-else class="status invalid">
                    <X :size="14" />
                    Invalid:
                    {{ validationError || "API key verification failed" }}
                  </span>
                </div>

                <div v-if="balanceInfos.length" class="balance-panel">
                  <div class="balance-header">
                    <span class="balance-title">Remaining balance</span>
                    <span v-if="balanceAvailable === false" class="balance-warning">Insufficient for API calls</span>
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
                  Confirm the base URL, load models, then save your selection.
                </p>

                <label class="form-label">Base URL</label>
                <div class="input-group">
                  <input :value="baseUrlInput" class="form-input" placeholder="https://api.openai.com/v1"
                    @input="(event) => onInput(event, onBaseUrlInput)" />
                </div>

                <label class="form-label">Model</label>
                <div v-if="modelOptions.length" class="model-select-row">
                  <CustomSelect :model-value="modelInput" :options="modelOptions" @update:model-value="
                    (value) => onModelInput(value as string)
                  " />
                  <button class="btn btn-outline" @click="onLoadModels" :disabled="isLoadingModels">
                    {{ isLoadingModels ? "Loading..." : "Reload models" }}
                  </button>
                </div>
                <div v-else class="input-group">
                  <input :value="modelInput" class="form-input" placeholder="gpt-4o-mini"
                    @input="(event) => onInput(event, onModelInput)" />
                </div>

                <div class="llm-config-actions">
                  <button class="btn btn-outline" @click="onLoadModels" :disabled="isLoadingModels">
                    {{ isLoadingModels ? "Loading..." : "Load models" }}
                  </button>
                  <button class="btn btn-primary-sm" @click="onSaveLlmSettings" :disabled="isSavingLlm">
                    {{ isSavingLlm ? "Saving..." : "Save Endpoint & Model" }}
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

      <!-- OCR Configuration Section -->
      <section class="settings-card">
        <div class="section-header">
          <div class="section-icon">
            <ScanText :size="16" />
          </div>
          <div>
            <h4 class="section-title">OCR Configuration</h4>
            <p class="section-description">
              Configure Optical Character Recognition models for text extraction.
            </p>
          </div>
        </div>

        <div class="section-content">
          <div class="ocr-layout">
            <div class="ocr-main-grid">
              <div class="ocr-left-column">
                <div class="ocr-step-card">
                  <div class="step-badge">1</div>
                  <div class="step-body">
                    <div class="step-title">Select Model</div>
                    <p class="step-desc">
                      Choose a local model or switch to an external OCR API.
                    </p>
                    <CustomSelect
                      :model-value="localOcrConfig.model"
                      :options="ocrModelOptions"
                      @update:model-value="(val) => (localOcrConfig.model = val as string)"
                    />
                  </div>
                </div>

                <div class="ocr-step-card ocr-step-card-compact">
                  <div class="step-badge">2</div>
                  <div class="step-body">
                    <div class="step-title">Hugging Face Base URL</div>
                    <p class="step-desc">
                      Defaults to the official Hugging Face website for model downloads.
                    </p>
                    <div class="input-group">
                      <input
                        v-model="localOcrConfig.base_url"
                        class="form-input"
                        :placeholder="DEFAULT_HUGGING_FACE_BASE_URL"
                      />
                    </div>
                  </div>
                </div>
              </div>

              <div class="ocr-summary-card">
                <div class="ocr-summary-header">
                  <div>
                    <div class="ocr-summary-title">Model Summary</div>
                    <p class="step-desc">
                      {{ currentOcrModelInfo?.label || "Selected OCR model" }}
                    </p>
                  </div>
                  <span class="ocr-status-badge" :class="ocrStatusClass">{{
                    ocrStatusLabel
                  }}</span>
                </div>

                <div class="ocr-metadata-grid">
                  <div class="info-row">
                    <span class="info-label">Model</span>
                    <span class="info-value">{{
                      currentOcrModelInfo?.label || localOcrConfig.model
                    }}</span>
                  </div>
                  <div class="info-row">
                    <span class="info-label">Size</span>
                    <span class="info-value">{{
                      currentOcrModelInfo?.size || "-"
                    }}</span>
                  </div>
                  <div class="info-row">
                    <span class="info-label">Overhead</span>
                    <span class="info-value">{{
                      currentOcrModelInfo?.overhead || "-"
                    }}</span>
                  </div>
                  <div class="info-row">
                    <span class="info-label">Source</span>
                    <span class="info-value">{{
                      isExternalOcr ? "External" : "Local"
                    }}</span>
                  </div>
                </div>

                <div v-if="!isExternalOcr && hasDownloadProgress" class="download-progress-panel">
                  <div class="download-progress-label">
                    <span>Download progress</span>
                    <span>{{ Math.min(downloadProgress ?? 0, 100) }}%</span>
                  </div>
                  <div class="progress-bar">
                    <div
                      class="progress-fill"
                      :style="{ width: Math.min(downloadProgress ?? 0, 100) + '%' }"
                    ></div>
                  </div>
                </div>

                <p
                  v-if="
                    !isExternalOcr &&
                    currentOcrModelInfo &&
                    !currentOcrModelInfo.is_downloadable
                  "
                  class="download-hint"
                >
                  This model requires manual setup or external credentials.
                </p>
              </div>
            </div>

            <div v-if="isExternalOcr" class="ocr-external-panel">
              <div class="ocr-step-card">
                <div class="step-badge">3</div>
                <div class="step-body">
                  <div class="step-title">External OCR Setup</div>
                  <p class="step-desc">
                    Add your external OCR API key.
                  </p>
                  <label class="form-label">API Key</label>
                  <div class="input-group">
                    <input
                      v-model="localOcrConfig.api_key"
                      type="password"
                      class="form-input"
                      placeholder="Enter API Key"
                    />
                  </div>
                </div>
              </div>
            </div>

            <div class="ocr-footer-actions">
              <div class="ocr-footer-left">
                <button
                  v-if="canDownloadCurrentModel"
                  class="btn btn-outline"
                  @click="downloadOcr"
                >
                  <Download :size="14" />
                  Download Model
                </button>

                <button
                  v-if="!isExternalOcr && currentOcrModelInfo?.installed"
                  class="btn btn-outline ocr-btn-danger"
                  @click="onDeleteOcrModel(localOcrConfig.model)"
                >
                  <Trash2 :size="14" />
                  Remove Model
                </button>

                <button
                  v-if="!isExternalOcr && isDownloadActive && !isDownloadPaused"
                  class="btn btn-outline"
                  @click="onPauseOcrDownload?.(localOcrConfig.model)"
                >
                  <Pause :size="14" />
                  Pause
                </button>

                <template v-if="!isExternalOcr && isDownloadPaused">
                  <button
                    class="btn btn-outline"
                    @click="onResumeOcrDownload?.(localOcrConfig.model)"
                  >
                    <Play :size="14" />
                    Resume
                  </button>
                  <button
                    class="btn btn-outline"
                    @click="onCancelOcrDownload?.(localOcrConfig.model)"
                  >
                    <X :size="14" />
                    Cancel
                  </button>
                </template>
              </div>

              <button
                class="btn btn-primary-sm"
                @click="saveOcr"
                :disabled="isSavingOcr"
              >
                {{ isSavingOcr ? "Saving..." : "Save Configuration" }}
              </button>
            </div>
          </div>
        </div>
      </section>

      <section class="settings-card">
        <div class="section-header">
          <div class="section-icon">
            <ArrowUpRight :size="16" />
          </div>
          <div>
            <h4 class="section-title">Updates</h4>
            <p class="section-description">Version {{ currentVersionLabel }}</p>
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
                <template v-else>Check GitHub for new releases</template>
              </p>
            </div>
            <div class="update-actions">
              <a v-if="updateInfo?.isUpdateAvailable && updateInfo?.latest?.url" class="btn btn-primary-sm"
                :href="updateInfo.latest.url" target="_blank" rel="noopener noreferrer">Download</a>
              <button class="btn btn-outline" @click="onUpdateCheck" :disabled="isCheckingUpdate">
                {{ isCheckingUpdate ? "Checking..." : "Check" }}
              </button>
            </div>
          </div>
          <div v-if="updateError" class="error-message">{{ updateError }}</div>
        </div>
      </section>

      <!-- Danger Zone Section -->
      <section class="settings-card danger-zone-card">
        <div class="section-header">
          <div class="section-icon danger-icon">
            <Trash :size="16" />
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
            Clear all indexed chunks and chat sessions. Files will remain in the
            reference folder.
          </p>

          <div v-if="resetSuccess" class="success-message">
            {{ resetSuccess }}
          </div>
          <div v-if="resetError" class="error-message">{{ resetError }}</div>

          <button class="btn btn-danger-action" @click="onResetClick" :disabled="isResetting">
            <Trash2 :size="14" />
            {{ isResetting ? "Clearing..." : "Clear All Data" }}
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.ocr-layout {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.ocr-main-grid {
  display: grid;
  grid-template-columns: minmax(320px, 1.2fr) minmax(260px, 1fr);
  gap: 14px;
}

.ocr-left-column {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ocr-step-card {
  display: grid;
  grid-template-columns: 28px 1fr;
  gap: 12px;
  padding: 14px;
  border: 1px solid var(--color-neutral-250);
  border-radius: 12px;
  background: var(--bg-input);
}

.ocr-summary-card {
  border: 1px solid var(--color-neutral-250);
  border-radius: 12px;
  background: var(--bg-input);
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ocr-step-card-compact {
  padding-top: 12px;
  padding-bottom: 12px;
}

.ocr-summary-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.ocr-summary-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.ocr-status-badge {
  font-size: 11px;
  font-weight: 600;
  border-radius: 999px;
  padding: 4px 10px;
  white-space: nowrap;
}

.ocr-status-badge.success {
  background: var(--color-success-50);
  color: var(--color-success-700);
}

.ocr-status-badge.warning {
  background: var(--color-warning-100);
  color: var(--color-warning-800);
}

.ocr-status-badge.info {
  background: var(--accent-soft);
  color: var(--accent-color);
}

.ocr-status-badge.neutral {
  background: var(--color-neutral-150);
  color: var(--text-secondary);
}

.ocr-metadata-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 12px;
}

.info-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-label {
  font-size: 11px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.info-value {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 600;
}

.download-progress-panel {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.download-progress-label {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--text-secondary);
}

.progress-bar {
  width: 100%;
  height: 7px;
  background: var(--bg-canvas-2);
  border-radius: 999px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--accent-color);
  transition: width 0.3s ease;
  min-width: 2px;
}

.download-hint {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 0;
}

.ocr-external-panel {
  display: flex;
  flex-direction: column;
}

.ocr-footer-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-top: 1px solid var(--border-color);
  padding-top: 12px;
}

.ocr-footer-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.ocr-btn-danger {
  color: var(--color-danger-700);
  border-color: var(--color-danger-400);
}

.ocr-btn-danger:hover:not(:disabled) {
  background: var(--color-danger-50);
}

@media (max-width: 1050px) {
  .ocr-main-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .ocr-metadata-grid {
    grid-template-columns: 1fr;
  }

  .ocr-footer-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .ocr-footer-left {
    width: 100%;
  }

  .ocr-footer-left .btn {
    width: 100%;
    justify-content: center;
  }
}
</style>
