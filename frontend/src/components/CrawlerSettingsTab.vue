<script setup lang="ts">
import { ref, watch } from "vue";
import type { CrawlerConfig } from "../types";
import { updateCrawlerConfig } from "../api/client";
import { Settings, Globe, Check } from "lucide-vue-next";
import BaseToggle from "./BaseToggle.vue";

const props = defineProps<{
  config: CrawlerConfig;
}>();

const emit = defineEmits<{
  (e: "update", config: CrawlerConfig): void;
}>();

const localConfig = ref<CrawlerConfig>({ ...props.config });
const saveSuccess = ref(false);
const saveError = ref<string | null>(null);
const isUpdatingFromProp = ref(false);

const engineDescriptions: Record<string, string> = {
  google_scholar: "Google Scholar - Web scraping (user responsibility for ToS)",
  pubmed: "PubMed - NCBI E-utilities API",
  semantic_scholar: "Semantic Scholar - Free API with citation data",
};

watch(
  () => props.config,
  (newConfig) => {
    isUpdatingFromProp.value = true;
    localConfig.value = { ...newConfig };
    // Reset flag after Vue processes the change
    setTimeout(() => {
      isUpdatingFromProp.value = false;
    }, 0);
  },
  { deep: true },
);

// Auto-save on any config change (only from user interaction)
let saveTimeout: ReturnType<typeof setTimeout> | null = null;
watch(
  localConfig,
  async (newConfig) => {
    // Skip if change came from prop update
    if (isUpdatingFromProp.value) return;

    // Debounce saves to avoid too many API calls
    if (saveTimeout) clearTimeout(saveTimeout);
    saveTimeout = setTimeout(async () => {
      await autoSave(newConfig);
    }, 300);
  },
  { deep: true },
);

async function autoSave(config: CrawlerConfig) {
  saveError.value = null;
  try {
    const saved = await updateCrawlerConfig(config);
    emit("update", saved);
    showSaveSuccess();
  } catch (e: any) {
    saveError.value = e.message || "Failed to save settings";
  }
}

function showSaveSuccess() {
  saveSuccess.value = true;
  setTimeout(() => {
    saveSuccess.value = false;
  }, 2000);
}
</script>

<template>
  <div class="crawler-settings">
    <!-- Save Indicator -->
    <Transition name="fade">
      <div v-if="saveSuccess" class="save-indicator visible">
        <Check :size="14" />
        Saved
      </div>
    </Transition>
    <Transition name="fade">
      <div v-if="saveError" class="save-indicator visible error">
        {{ saveError }}
      </div>
    </Transition>

    <!-- Global Settings -->
    <section class="settings-card">
      <div class="section-header">
        <div class="section-icon">
          <Settings :size="16" />
        </div>
        <div>
          <h4 class="section-title">Global Settings</h4>
          <p class="section-description">
            Configure crawler behavior and limits
          </p>
        </div>
      </div>

      <div class="section-content">
        <div class="setting-row">
          <div class="setting-info">
            <label class="setting-label">Enable Crawler</label>
            <p class="setting-hint">
              Enable or disable the web crawler functionality
            </p>
          </div>
          <div class="setting-control">
            <BaseToggle v-model="localConfig.enabled" />
          </div>
        </div>

        <div class="setting-row">
          <div class="setting-info">
            <label class="setting-label">Auto-Download</label>
            <p class="setting-hint">
              Automatically trigger download flow after search (still requires
              confirmation)
            </p>
          </div>
          <div class="setting-control">
            <BaseToggle v-model="localConfig.auto_download" />
          </div>
        </div>

        <div class="setting-row">
          <div class="setting-info">
            <label class="setting-label">Max Results per Engine</label>
            <p class="setting-hint">
              Maximum number of results to fetch from each engine
            </p>
          </div>
          <div class="setting-control setting-control--sm">
            <input
              type="number"
              v-model.number="localConfig.max_results_per_engine"
              min="5"
              max="100"
              class="form-input"
            />
          </div>
        </div>

        <div class="setting-row">
          <div class="setting-info">
            <label class="setting-label">Global Timeout (seconds)</label>
            <p class="setting-hint">Default timeout for all crawler operations</p>
          </div>
          <div class="setting-control setting-control--sm">
            <input
              type="number"
              v-model.number="localConfig.timeout_seconds"
              min="5"
              max="120"
              class="form-input"
            />
          </div>
        </div>
      </div>
    </section>

    <!-- Engine Settings -->
    <section class="settings-card">
      <div class="section-header">
        <div class="section-icon">
          <Globe :size="16" />
        </div>
        <div>
          <h4 class="section-title">Engine Settings</h4>
          <p class="section-description">Configure individual search engines</p>
        </div>
      </div>

      <div class="section-content">
        <div
          v-for="(engineConfig, engineName) in localConfig.engines"
          :key="engineName"
          class="settings-card-nested"
        >
          <div class="nested-header">
            <h4 class="nested-title">{{ engineName }}</h4>
            <p class="nested-desc">
              {{ engineDescriptions[engineName] || "" }}
            </p>
          </div>

          <div class="nested-controls">
            <div class="setting-row">
              <div class="setting-info">
                <label class="setting-label">Enabled</label>
              </div>
              <div class="setting-control">
                <BaseToggle v-model="engineConfig.enabled" />
              </div>
            </div>

            <div class="setting-row">
              <div class="setting-info">
                <label class="setting-label">Rate Limit (req/min)</label>
              </div>
              <div class="setting-control setting-control--sm">
                <input
                  type="number"
                  v-model.number="engineConfig.rate_limit"
                  min="1"
                  max="60"
                  class="form-input"
                />
              </div>
            </div>

            <div class="setting-row">
              <div class="setting-info">
                <label class="setting-label">Timeout (seconds)</label>
              </div>
              <div class="setting-control setting-control--sm">
                <input
                  type="number"
                  v-model.number="engineConfig.timeout"
                  min="5"
                  max="120"
                  class="form-input"
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.crawler-settings {
  display: flex;
  flex-direction: column;
  gap: 24px;
  position: relative;
}

/* Floating save indicator - top right of settings content */
.crawler-settings > .save-indicator {
  position: fixed;
  top: 180px;
  right: 80px;
  z-index: 100;
  box-shadow: 0 2px 8px var(--alpha-black-10);
}

/* Nested card spacing */
.settings-card-nested + .settings-card-nested {
  margin-top: 12px;
}

/* Form input styling for number inputs */
.form-input {
  width: 100%;
  padding: 8px 12px;
  font-size: 14px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: var(--bg-panel);
  color: var(--text-primary);
}

.form-input:focus {
  outline: none;
  border-color: var(--accent-color);
}

/* Fade transition */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
