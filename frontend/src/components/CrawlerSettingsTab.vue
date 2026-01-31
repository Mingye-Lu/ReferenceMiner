<script setup lang="ts">
import { ref, watch } from "vue";
import type { CrawlerConfig } from "../types";
import { updateCrawlerConfig } from "../api/client";

const props = defineProps<{
  config: CrawlerConfig;
}>();

const emit = defineEmits<{
  (e: "update", config: CrawlerConfig): void;
}>();

const localConfig = ref<CrawlerConfig>({ ...props.config });
const isSaving = ref(false);
const saveError = ref<string | null>(null);
const saveSuccess = ref(false);

const engineDescriptions: Record<string, string> = {
  google_scholar: "Google Scholar - Web scraping (user responsibility for ToS)",
  pubmed: "PubMed - NCBI E-utilities API",
  semantic_scholar: "Semantic Scholar - Free API with citation data",
};

watch(
  () => props.config,
  (newConfig) => {
    localConfig.value = { ...newConfig };
  },
  { deep: true }
);

async function handleSave() {
  isSaving.value = true;
  saveError.value = null;
  saveSuccess.value = false;

  try {
    const saved = await updateCrawlerConfig(localConfig.value);
    emit("update", saved);
    saveSuccess.value = true;
    setTimeout(() => {
      saveSuccess.value = false;
    }, 3000);
  } catch (e: any) {
    saveError.value = e.message || "Failed to save settings";
  } finally {
    isSaving.value = false;
  }
}

function resetToDefaults() {
  localConfig.value = {
    enabled: true,
    auto_download: false,
    max_results_per_engine: 20,
    timeout_seconds: 30,
    engines: {
      google_scholar: {
        enabled: true,
        rate_limit: 5,
        timeout: 30,
      },
      pubmed: {
        enabled: true,
        rate_limit: 10,
        timeout: 30,
      },
      semantic_scholar: {
        enabled: true,
        rate_limit: 10,
        timeout: 30,
      },
    },
  };
}
</script>

<template>
  <div class="crawler-settings">
    <!-- Global Settings -->
    <section class="settings-section">
      <h3 class="section-title">Global Settings</h3>
      
      <div class="setting-row">
        <div class="setting-info">
          <label class="setting-label">Enable Crawler</label>
          <p class="setting-hint">
            Enable or disable the web crawler functionality
          </p>
        </div>
        <div class="setting-control">
          <input
            type="checkbox"
            v-model="localConfig.enabled"
            class="toggle-checkbox"
          />
        </div>
      </div>

      <div class="setting-row">
        <div class="setting-info">
          <label class="setting-label">Auto-Download</label>
          <p class="setting-hint">
            Automatically trigger download flow after search (still requires confirmation)
          </p>
        </div>
        <div class="setting-control">
          <input
            type="checkbox"
            v-model="localConfig.auto_download"
            class="toggle-checkbox"
          />
        </div>
      </div>

      <div class="setting-row">
        <div class="setting-info">
          <label class="setting-label">Max Results per Engine</label>
          <p class="setting-hint">
            Maximum number of results to fetch from each engine
          </p>
        </div>
        <div class="setting-control">
          <input
            type="number"
            v-model.number="localConfig.max_results_per_engine"
            min="5"
            max="100"
            class="number-input"
          />
        </div>
      </div>

      <div class="setting-row">
        <div class="setting-info">
          <label class="setting-label">Global Timeout (seconds)</label>
          <p class="setting-hint">
            Default timeout for all crawler operations
          </p>
        </div>
        <div class="setting-control">
          <input
            type="number"
            v-model.number="localConfig.timeout_seconds"
            min="5"
            max="120"
            class="number-input"
          />
        </div>
      </div>
    </section>

    <!-- Engine Settings -->
    <section class="settings-section">
      <h3 class="section-title">Engine Settings</h3>
      
      <div
        v-for="(engineConfig, engineName) in localConfig.engines"
        :key="engineName"
        class="engine-card"
      >
        <div class="engine-header">
          <h4 class="engine-name">{{ engineName }}</h4>
          <p class="engine-desc">{{ engineDescriptions[engineName] || "" }}</p>
        </div>

        <div class="engine-controls">
          <div class="setting-row compact">
            <div class="setting-info">
              <label class="setting-label">Enabled</label>
            </div>
            <div class="setting-control">
              <input
                type="checkbox"
                v-model="engineConfig.enabled"
                class="toggle-checkbox"
              />
            </div>
          </div>

          <div class="setting-row compact">
            <div class="setting-info">
              <label class="setting-label">Rate Limit (req/min)</label>
            </div>
            <div class="setting-control">
              <input
                type="number"
                v-model.number="engineConfig.rate_limit"
                min="1"
                max="60"
                class="number-input small"
              />
            </div>
          </div>

          <div class="setting-row compact">
            <div class="setting-info">
              <label class="setting-label">Timeout (seconds)</label>
            </div>
            <div class="setting-control">
              <input
                type="number"
                v-model.number="engineConfig.timeout"
                min="5"
                max="120"
                class="number-input small"
              />
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Save Actions -->
    <div class="save-actions">
      <div v-if="saveError" class="error-message">
        {{ saveError }}
      </div>
      <div v-if="saveSuccess" class="success-message">
        Settings saved successfully
      </div>
      <div class="action-buttons">
        <button class="btn-secondary" @click="resetToDefaults">
          Reset to Defaults
        </button>
        <button class="btn-primary" @click="handleSave" :disabled="isSaving">
          <span v-if="isSaving">Saving...</span>
          <span v-else>Save Settings</span>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.crawler-settings {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.settings-section {
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: 12px;
  padding: 20px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 16px 0;
}

.setting-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid var(--border-color);
}

.setting-row:last-child {
  border-bottom: none;
}

.setting-row.compact {
  padding: 8px 0;
}

.setting-info {
  flex: 1;
}

.setting-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  display: block;
  margin-bottom: 4px;
}

.setting-hint {
  font-size: 11px;
  color: var(--text-secondary);
  margin: 0;
}

.setting-control {
  display: flex;
  align-items: center;
}

.toggle-checkbox {
  width: 40px;
  height: 24px;
  background: var(--color-neutral-240);
  border-radius: 12px;
  appearance: none;
  cursor: pointer;
  position: relative;
  transition: background 0.2s;
}

.toggle-checkbox:checked {
  background: var(--accent-color);
}

.toggle-checkbox::before {
  content: "";
  position: absolute;
  width: 20px;
  height: 20px;
  background: white;
  border-radius: 50%;
  top: 2px;
  left: 2px;
  transition: transform 0.2s;
}

.toggle-checkbox:checked::before {
  transform: translateX(16px);
}

.number-input {
  width: 100px;
  padding: 6px 10px;
  font-size: 13px;
  background: var(--bg-panel);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  color: var(--text-primary);
}

.number-input.small {
  width: 80px;
}

.engine-card {
  background: var(--bg-panel);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 12px;
}

.engine-header {
  margin-bottom: 12px;
}

.engine-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 4px 0;
}

.engine-desc {
  font-size: 11px;
  color: var(--text-secondary);
  margin: 0;
}

.engine-controls {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.save-actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: flex-end;
}

.error-message {
  align-self: stretch;
  padding: 10px 14px;
  background: rgba(211, 47, 47, 0.1);
  border: 1px solid var(--color-danger-400);
  border-radius: 6px;
  font-size: 12px;
  color: var(--color-danger-800);
}

.success-message {
  align-self: stretch;
  padding: 10px 14px;
  background: rgba(76, 175, 80, 0.1);
  border: 1px solid var(--color-success-600);
  border-radius: 6px;
  font-size: 12px;
  color: var(--color-success-700);
}

.action-buttons {
  display: flex;
  gap: 12px;
}

.btn-primary {
  padding: 8px 20px;
  font-size: 13px;
  font-weight: 500;
  background: var(--accent-color);
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: opacity 0.2s;
}

.btn-primary:hover:not(:disabled) {
  opacity: 0.9;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  padding: 8px 20px;
  font-size: 13px;
  font-weight: 500;
  background: transparent;
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-secondary:hover {
  background: var(--bg-card-hover);
  border-color: var(--accent-bright);
}
</style>
