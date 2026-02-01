<script setup lang="ts">
import { ref, watch } from "vue";
import type { CrawlerConfig } from "../types";
import { updateCrawlerConfig } from "../api/client";
import { Settings, Globe } from "lucide-vue-next";
import BaseToggle from "./BaseToggle.vue";

const props = defineProps<{
  crawlerConfig: CrawlerConfig | null;
  onUpdate: (config: CrawlerConfig) => void;
}>();

const localConfig = ref<CrawlerConfig | null>(
  props.crawlerConfig ? { ...props.crawlerConfig } : null,
);
const isUpdatingFromProp = ref(false);

const engineDescriptions: Record<string, string> = {
  google_scholar: "Google Scholar - Web scraping (user responsibility for ToS)",
  pubmed: "PubMed - NCBI E-utilities API",
  semantic_scholar: "Semantic Scholar - Free API with citation data",
};

watch(
  () => props.crawlerConfig,
  (newConfig) => {
    if (!newConfig) {
      localConfig.value = null;
      return;
    }
    isUpdatingFromProp.value = true;
    localConfig.value = { ...newConfig };
    setTimeout(() => {
      isUpdatingFromProp.value = false;
    }, 0);
  },
  { deep: true },
);

let saveTimeout: ReturnType<typeof setTimeout> | null = null;
watch(
  localConfig,
  async (newConfig) => {
    if (!newConfig || isUpdatingFromProp.value) return;
    if (saveTimeout) clearTimeout(saveTimeout);
    saveTimeout = setTimeout(async () => {
      await autoSave(newConfig);
    }, 300);
  },
  { deep: true },
);

async function autoSave(config: CrawlerConfig) {
  try {
    const saved = await updateCrawlerConfig(config);
    props.onUpdate(saved);
  } catch (error) {
    console.error("Failed to save crawler settings", error);
  }
}
</script>

<template>
  <div class="settings-section-container">
    <div class="settings-header">
      <h2 class="settings-section-title">Web Crawler</h2>
      <p class="settings-section-desc">
        Configure search engines, download settings, and deep crawl options.
      </p>
    </div>

    <div v-if="!localConfig" class="loading-settings">Loading settings...</div>

    <div v-else class="start-settings-content">
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
          <div class="pref-setting-row">
            <div class="pref-setting-info">
              <label class="form-label">Enable Crawler</label>
              <p class="form-hint">
                Enable or disable the web crawler functionality
              </p>
            </div>
            <div class="setting-control">
              <BaseToggle v-model="localConfig.enabled" />
            </div>
          </div>

          <div class="pref-setting-row">
            <div class="pref-setting-info">
              <label class="form-label">Auto-Download</label>
              <p class="form-hint">
                Automatically trigger download flow after search (still requires
                confirmation)
              </p>
            </div>
            <div class="setting-control">
              <BaseToggle v-model="localConfig.auto_download" />
            </div>
          </div>

          <div class="pref-setting-row">
            <div class="pref-setting-info">
              <label class="form-label">Max Results per Engine</label>
              <p class="form-hint">
                Maximum number of results to fetch from each engine
              </p>
            </div>
            <div class="setting-control">
              <div class="input-group" style="width: 120px">
                <input
                  type="number"
                  v-model.number="localConfig.max_results_per_engine"
                  min="5"
                  max="100"
                  class="form-input"
                />
              </div>
            </div>
          </div>

          <div class="pref-setting-row">
            <div class="pref-setting-info">
              <label class="form-label">Global Timeout (seconds)</label>
              <p class="form-hint">
                Default timeout for all crawler operations
              </p>
            </div>
            <div class="setting-control">
              <div class="input-group" style="width: 120px">
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
        </div>
      </section>

      <section class="settings-card">
        <div class="section-header">
          <div class="section-icon">
            <Globe :size="16" />
          </div>
          <div>
            <h4 class="section-title">Engine Settings</h4>
            <p class="section-description">
              Configure individual search engines
            </p>
          </div>
        </div>

        <div class="section-content">
          <div
            v-for="(engineConfig, engineName) in localConfig.engines"
            :key="engineName"
            class="llm-setup-step full-width"
          >
            <div class="step-body">
              <div class="step-title">{{ engineName }}</div>
              <p class="step-desc">
                {{ engineDescriptions[engineName] || "" }}
              </p>

              <div
                style="
                  display: flex;
                  flex-direction: column;
                  gap: 16px;
                  margin-top: 8px;
                "
              >
                <div class="pref-setting-row">
                  <div class="pref-setting-info">
                    <label class="form-label">Enabled</label>
                  </div>
                  <div class="setting-control">
                    <BaseToggle v-model="engineConfig.enabled" />
                  </div>
                </div>

                <div class="pref-setting-row">
                  <div class="pref-setting-info">
                    <label class="form-label">Rate Limit (req/min)</label>
                  </div>
                  <div class="setting-control">
                    <div class="input-group" style="width: 120px">
                      <input
                        type="number"
                        v-model.number="engineConfig.rate_limit"
                        min="1"
                        max="60"
                        class="form-input"
                      />
                    </div>
                  </div>
                </div>

                <div class="pref-setting-row">
                  <div class="pref-setting-info">
                    <label class="form-label">Timeout (seconds)</label>
                  </div>
                  <div class="setting-control">
                    <div class="input-group" style="width: 120px">
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
          </div>
        </div>
      </section>
    </div>
  </div>
</template>
