<script setup lang="ts">
import { ref, computed, watch } from "vue";
import type { BalanceInfo, UpdateCheck, OcrConfig, OcrModelInfo } from "../types";
import { ArrowUpRight, Check, Key, Trash, Trash2, X, ScanText, Download, Pause, Play } from "lucide-vue-next";
import CustomSelect from "./CustomSelect.vue";

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
  base_url: "",
  api_key: "",
});

watch(
  () => props.ocrConfig,
  (newVal) => {
    if (newVal) {
      localOcrConfig.value = { ...newVal };
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
          <div class="llm-setup-grid">
            <!-- Step 1: Select Model -->
            <div class="llm-setup-step">
              <div class="step-badge">1</div>
              <div class="step-body">
                <div class="step-title">Select Model</div>
                <p class="step-desc">
                  Choose a local model or an external API.
                </p>
                <CustomSelect :model-value="localOcrConfig.model" :options="ocrModelOptions" @update:model-value="
                  (val) => (localOcrConfig.model = val as string)
                " />
              </div>
            </div>

            <!-- Step 2: Configure & Save -->
            <div class="llm-setup-step">
              <div class="step-badge">2</div>
              <div class="step-body">
                <div class="step-title">Setup & Save</div>
                <p class="step-desc">
                  {{
                    isExternalOcr
                      ? "Configure API details."
                      : "Download the model if required."
                  }}
                </p>

                <!-- Local Model Info -->
                <div v-if="!isExternalOcr && currentOcrModelInfo" class="model-info-panel">
                  <div class="info-grid">
                    <div class="info-row">
                      <span class="info-label">Size</span>
                      <span class="info-value">{{
                        currentOcrModelInfo.size
                      }}</span>
                    </div>
                    <div class="info-row">
                      <span class="info-label">Overhead</span>
                      <span class="info-value">{{
                        currentOcrModelInfo.overhead
                      }}</span>
                    </div>
                  </div>

                  <div class="action-row">
                    <!-- Progress Bar (shown when downloadProgress is set, persists after completion until model switch) -->
                    <div v-if="downloadProgress !== null" class="download-progress">
                      <div class="progress-bar">
                        <div class="progress-fill" :style="{ width: Math.min(downloadProgress, 100) + '%' }">
                        </div>
                      </div>
                      <span class="progress-text">{{ downloadProgress }}%</span>

                      <!-- Download control buttons based on state -->
                      <!-- Show pause when actively downloading (progress 0-99 and not paused) -->
                      <button v-if="downloadProgress >= 0 && downloadProgress < 100 && downloadState !== 'paused'"
                        class="btn-icon pause" @click="onPauseOcrDownload?.(localOcrConfig.model)" title="Pause">
                        <Pause :size="16" />
                      </button>

                      <!-- Show resume and cancel when paused -->
                      <template v-if="downloadState === 'paused'">
                        <button class="btn-icon resume" @click="onResumeOcrDownload?.(localOcrConfig.model)"
                          title="Resume">
                          <Play :size="16" />
                        </button>
                        <button class="btn-icon cancel" @click="onCancelOcrDownload?.(localOcrConfig.model)"
                          title="Cancel">
                          <X :size="16" />
                        </button>
                      </template>
                    </div>

                    <template v-if="currentOcrModelInfo.is_downloadable">
                      <button v-if="currentOcrModelInfo.installed" class="btn-icon delete"
                        @click="onDeleteOcrModel(localOcrConfig.model)" title="Delete Model">
                        <Trash2 :size="16" />
                      </button>
                      <!-- Hide download button when progress is showing -->
                      <button v-else-if="downloadProgress === null" class="btn-outline" @click="downloadOcr">
                        <Download :size="14" />
                        Download Model
                      </button>
                    </template>
                    <div v-else class="download-hint">
                      Model requires manual setup or API key.
                    </div>
                  </div>
                </div>

                <!-- External Config -->
                <div v-if="isExternalOcr" class="external-config">
                  <label class="form-label">Base URL</label>
                  <div class="input-group">
                    <input v-model="localOcrConfig.base_url" class="form-input"
                      placeholder="https://api.ocr-provider.com/v1" />
                  </div>
                  <label class="form-label">API Key</label>
                  <div class="input-group">
                    <input v-model="localOcrConfig.api_key" type="password" class="form-input"
                      placeholder="Enter API Key" />
                  </div>
                </div>

                <div class="llm-config-actions">
                  <button class="btn btn-primary-sm" @click="saveOcr" :disabled="isSavingOcr">
                    {{ isSavingOcr ? "Saving..." : "Save Configuration" }}
                  </button>
                </div>
              </div>
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
.model-info-panel {
  background: var(--bg-canvas);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 12px;
  margin-top: 12px;
}

.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 12px;
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
  font-weight: 500;
}

.external-config {
  border-top: 1px dashed var(--border-color);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.action-row {
  display: flex;
  justify-content: flex-end;
  align-items: center;
}

.download-hint {
  font-size: 13px;
  color: var(--text-tertiary);
  font-style: italic;
}

.download-progress {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-right: 12px;
  flex: 1;
}

.progress-bar {
  flex: 1;
  height: 6px;
  background: var(--bg-canvas-2);
  /* Distinct from input bg */
  border-radius: 3px;
  overflow: hidden;
  position: relative;
  /* Ensure stacking context */
}

.progress-fill {
  height: 100%;
  background: var(--accent-color);
  transition: width 0.3s ease;
  min-width: 2px;
  /* Ensure visible even when small */
}

.progress-text {
  font-size: 12px;
  color: var(--text-primary);
  /* Ensure contrast */
  font-family: monospace;
  width: 40px;
  /* Increased width */
  text-align: right;
  font-weight: 500;
}

.download-success {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--color-success);
  font-size: 13px;
  font-weight: 500;
  margin-right: 12px;
}

.btn-icon.pause,
.btn-icon.resume {
  color: var(--text-secondary);
}

.btn-icon.pause:hover {
  color: var(--color-warning, #f59e0b);
}

.btn-icon.resume:hover {
  color: var(--color-success, #10b981);
}
</style>
