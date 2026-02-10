<script setup lang="ts">
import { ref, watch, computed, nextTick } from "vue";
import type {
  CrawlerConfig,
  CrawlerPreset,
  CrawlerPresetName,
  ConnectionStatus,
} from "../types";
import { updateCrawlerConfig } from "../api/client";
import {
  Settings,
  Globe,
  Check,
  X,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  ScanText,
} from "lucide-vue-next";
import BaseToggle from "./BaseToggle.vue";

const props = defineProps<{
  crawlerConfig: CrawlerConfig | null;
  onUpdate: (config: CrawlerConfig) => void;
  isOcrReady: boolean;
}>();

const localConfig = ref<CrawlerConfig | null>(
  props.crawlerConfig ? { ...props.crawlerConfig } : null,
);
const isUpdatingFromProp = ref(false);

const engineDescriptions: Record<string, string> = {
  airiti:
    "Airiti Library - Chinese journals and theses platform (Taiwan focus)",
  google_scholar:
    "Google Scholar - Broad academic search across all disciplines",
  pubmed: "PubMed - Biomedical and life sciences literature database",
  semantic_scholar:
    "Semantic Scholar - AI-powered search with citation analysis",
  arxiv:
    "ArXiv - Preprint repository for computer science, physics, and mathematics",
  crossref: "Crossref - Comprehensive metadata for scholarly works with DOIs",
  openalex:
    "OpenAlex - Open scholarly catalog with 200M+ works and citation data",
  core: "CORE - Open access research papers with full-text search",
  europe_pmc:
    "Europe PMC - Life sciences literature with open access full text",
  biorxiv_medrxiv: "bioRxiv/medRxiv - Biology and medical research preprints",
  nstl: "NSTL - China National Science and Technology Library catalog",
  wanfang: "Wanfang Data - Chinese academic journals and conference papers",
  cnki: "CNKI - China National Knowledge Infrastructure comprehensive database",
  chinaxiv: "ChinaXiv - Chinese preprint server for scientific research",
  chaoxing: "Chaoxing - Comprehensive Chinese academic platform with books, journals, and theses",
};

const presets: CrawlerPreset[] = [
  {
    name: "balanced",
    label: "Balanced",
    description: "Good mix of speed and coverage for general research",
    enabledEngines: ["google_scholar", "semantic_scholar", "arxiv", "pubmed"],
    rateLimit: 5,
    timeout: 30,
    maxResults: 20,
  },
  {
    name: "fast",
    label: "Fast",
    description: "Quick searches with minimal engines for rapid results",
    enabledEngines: ["google_scholar", "semantic_scholar"],
    rateLimit: 10,
    timeout: 15,
    maxResults: 10,
  },
  {
    name: "thorough",
    label: "Thorough",
    description: "Maximum coverage with all engines enabled",
    enabledEngines: Object.keys(engineDescriptions),
    rateLimit: 3,
    timeout: 45,
    maxResults: 50,
  },
  {
    name: "minimal",
    label: "Minimal",
    description: "Only essential engines for basic searches",
    enabledEngines: ["google_scholar"],
    rateLimit: 5,
    timeout: 30,
    maxResults: 15,
  },
  {
    name: "custom",
    label: "Custom",
    description: "Customized settings that don't match any preset",
    enabledEngines: [],
    rateLimit: 0,
    timeout: 0,
    maxResults: 0,
    isCustom: true,
  },
];

const selectedPreset = ref<CrawlerPresetName>(
  props.crawlerConfig?.preset ?? "balanced",
);
const isApplyingPreset = ref(false);
const testingConnections = ref<Record<string, boolean>>({});
const connectionStatus = ref<Record<string, ConnectionStatus>>({});
const expandedEngine = ref<string | null>(null);

watch(
  () => props.crawlerConfig,
  (newConfig) => {
    if (!newConfig) {
      localConfig.value = null;
      return;
    }
    isUpdatingFromProp.value = true;
    localConfig.value = { ...newConfig };
    selectedPreset.value = newConfig.preset;
    nextTick(() => {
      isUpdatingFromProp.value = false;
    });
  },
  { deep: true, immediate: true },
);

let saveTimeout: ReturnType<typeof setTimeout> | null = null;

async function autoSave(config: CrawlerConfig) {
  try {
    const saved = await updateCrawlerConfig(config);
    props.onUpdate(saved);
  } catch (error) {
    console.error("Failed to save crawler settings", error);
  }
}

async function applyPreset(preset: CrawlerPreset) {
  if (!localConfig.value) return;

  isApplyingPreset.value = true;
  selectedPreset.value = preset.name;

  localConfig.value.preset = preset.name;
  localConfig.value.max_results_per_engine = preset.maxResults;
  localConfig.value.timeout_seconds = preset.timeout;

  Object.keys(localConfig.value.engines).forEach((engine) => {
    const isEnabled = preset.enabledEngines.includes(engine);
    localConfig.value!.engines[engine].enabled = isEnabled;
    localConfig.value!.engines[engine].rate_limit = preset.rateLimit;
    localConfig.value!.engines[engine].timeout = preset.timeout;
  });

  await autoSave(localConfig.value);
  await nextTick();
  isApplyingPreset.value = false;
}

function markAsCustom() {
  if (!localConfig.value || isUpdatingFromProp.value || isApplyingPreset.value)
    return;

  localConfig.value.preset = "custom";
  selectedPreset.value = "custom";

  if (saveTimeout) clearTimeout(saveTimeout);
  saveTimeout = setTimeout(() => {
    autoSave(localConfig.value!);
  }, 300);
}

function toggleEngine(engineName: string, enabled: boolean) {
  if (!localConfig.value) return;
  localConfig.value.engines[engineName].enabled = enabled;
  markAsCustom();
}

function updateEngineRateLimit(engineName: string, value: number) {
  if (!localConfig.value) return;
  localConfig.value.engines[engineName].rate_limit = value;
  markAsCustom();
}

function updateEngineTimeout(engineName: string, value: number) {
  if (!localConfig.value) return;
  localConfig.value.engines[engineName].timeout = value;
  markAsCustom();
}

function toggleAllEngines(enable: boolean) {
  if (!localConfig.value) return;
  Object.keys(localConfig.value.engines).forEach((engine) => {
    localConfig.value!.engines[engine].enabled = enable;
  });
  markAsCustom();
}

function testConnection(engine: string) {
  testingConnections.value[engine] = true;
  connectionStatus.value[engine] = "testing";

  setTimeout(() => {
    testingConnections.value[engine] = false;
    connectionStatus.value[engine] = "success";
  }, 1000);
}

function toggleAdvanced(engine: string) {
  expandedEngine.value = expandedEngine.value === engine ? null : engine;
}

const enabledEngineCount = computed(() => {
  if (!localConfig.value) return 0;
  return Object.values(localConfig.value.engines).filter((e) => e.enabled)
    .length;
});

const totalEngineCount = computed(() => {
  if (!localConfig.value) return 0;
  return Object.keys(localConfig.value.engines).length;
});
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

    <div v-else class="crawler-settings-content">
      <section class="settings-card">
        <div class="section-header">
          <div class="section-icon">
            <Settings :size="16" />
          </div>
          <div>
            <h4 class="section-title">Quick Configuration</h4>
            <p class="section-description">
              Choose a preset or customize settings below
            </p>
          </div>
        </div>

        <div class="section-content">
          <div class="preset-selector">
            <label class="form-label">Configuration Preset</label>
            <div class="preset-grid">
              <div v-for="preset in presets.filter(
                (p) => !p.isCustom || selectedPreset === 'custom',
              )" :key="preset.name" class="preset-card" :class="{
                active: selectedPreset === preset.name,
                'custom-preset': preset.isCustom,
              }" @click="!preset.isCustom && applyPreset(preset)">
                <div class="preset-header">
                  <span class="preset-label">{{ preset.label }}</span>
                  <Check v-if="selectedPreset === preset.name" :size="14" class="preset-check" />
                </div>
                <p class="preset-desc">{{ preset.description }}</p>
                <div v-if="!preset.isCustom" class="preset-stats">
                  <span>{{ preset.enabledEngines.length }} engines</span>
                  <span>{{ preset.maxResults }} results/engine</span>
                </div>
                <div v-else class="preset-stats">
                  <span>{{ enabledEngineCount }} engines enabled</span>
                  <span>{{
                    localConfig?.max_results_per_engine
                  }}
                    results/engine</span>
                </div>
              </div>
            </div>
          </div>

          <div class="global-settings-grid">
            <div class="pref-setting-row">
              <div class="pref-setting-info">
                <label class="form-label">Enable Crawler</label>
                <p class="form-hint">
                  Enable or disable web crawler functionality
                </p>
              </div>
              <div class="setting-control">
                <BaseToggle v-model="localConfig.enabled" @update:model-value="markAsCustom" />
              </div>
            </div>

            <div class="pref-setting-row">
              <div class="pref-setting-info">
                <label class="form-label">Auto-Download</label>
                <p class="form-hint">
                  Automatically trigger download flow after search
                </p>
              </div>
              <div class="setting-control">
                <BaseToggle v-model="localConfig.auto_download" @update:model-value="markAsCustom" />
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
                  <input type="number" v-model.number="localConfig.max_results_per_engine" min="5" max="100"
                    class="form-input" @input="markAsCustom" />
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
                  <input type="number" v-model.number="localConfig.timeout_seconds" min="5" max="120" class="form-input"
                    @input="markAsCustom" />
                </div>
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
            <h4 class="section-title">Search Engines</h4>
            <p class="section-description">
              {{ enabledEngineCount }} of {{ totalEngineCount }} engines enabled
            </p>
          </div>
          <div class="section-header-actions">
            <button class="btn-outline" @click="toggleAllEngines(true)">
              Enable All
            </button>
            <button class="btn-outline" @click="toggleAllEngines(false)">
              Disable All
            </button>
          </div>
        </div>

        <div class="section-content">
          <div class="engines-table">
            <div class="engines-header">
              <div class="col-engine">Engine</div>
              <div class="col-status">Status</div>
              <div class="col-rate">Rate Limit</div>
              <div class="col-actions">Actions</div>
            </div>
            <div v-for="(engineConfig, engineName) in localConfig.engines" :key="engineName" class="engine-row"
              :class="{ disabled: !engineConfig.enabled }">
              <div class="col-engine">
                <div class="engine-info">
                  <div class="engine-toggle">
                    <BaseToggle :model-value="engineConfig.enabled" @update:model-value="
                      toggleEngine(engineName as string, $event)
                      " @click.stop />
                  </div>
                  <div class="engine-details">
                    <span class="engine-name">{{ engineName }}</span>
                    <p class="engine-desc">
                      {{ engineDescriptions[engineName] || "" }}
                    </p>
                  </div>
                </div>
              </div>
              <div class="col-status">
                <div class="connection-indicator">
                  <span v-if="testingConnections[engineName]" class="status-testing">
                    <RefreshCw :size="12" class="spin" />
                  </span>
                  <Check v-else-if="connectionStatus[engineName] === 'success'" :size="14" class="status-success" />
                  <X v-else-if="connectionStatus[engineName] === 'failed'" :size="14" class="status-failed" />
                  <span v-else class="status-unknown">—</span>
                </div>
              </div>
              <div class="col-rate">
                <div class="setting-control setting-control--sm">
                  <input type="number" :value="engineConfig.rate_limit" @input="
                    updateEngineRateLimit(
                      engineName as string,
                      Number(($event.target as HTMLInputElement).value),
                    )
                    " min="1" max="60" class="form-input" />
                </div>
              </div>
              <div class="col-actions">
                <button class="btn-icon" @click="testConnection(engineName)" title="Test connection">
                  <RefreshCw :size="14" />
                </button>
                <button class="btn-icon" @click="toggleAdvanced(engineName)" :title="expandedEngine === engineName
                  ? 'Hide advanced'
                  : 'Show advanced'
                  ">
                  <ChevronDown v-if="expandedEngine !== engineName" :size="14" />
                  <ChevronUp v-else :size="14" />
                </button>
              </div>
              <div v-if="expandedEngine === engineName" class="engine-advanced">
                <div class="advanced-row">
                  <label class="form-label">Timeout (seconds)</label>
                  <input type="number" :value="engineConfig.timeout" @input="
                    updateEngineTimeout(
                      engineName as string,
                      Number(($event.target as HTMLInputElement).value),
                    )
                    " min="5" max="120" class="form-input" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Reference Identification Mode -->
      <section class="settings-card">
        <div class="section-header">
          <div class="section-icon">
            <ScanText :size="16" />
          </div>
          <div>
            <h4 class="section-title">Reference Identification</h4>
            <p class="section-description">
              How to identify reference entries from documents
            </p>
          </div>
        </div>

        <div class="section-content">
          <div class="radio-group-vertical">
            <label class="radio-option">
              <input type="radio" name="refIdentMode" value="string_only"
                :checked="localConfig.ref_ident_mode === 'string_only'"
                @change="localConfig.ref_ident_mode = 'string_only'; markAsCustom()" />
              <div class="radio-option-content">
                <span class="radio-option-label">String Search Only</span>
                <span class="radio-option-desc">Only character-based pattern matching to identify references</span>
              </div>
            </label>
            <label class="radio-option" :class="{ disabled: !isOcrReady }">
              <input type="radio" name="refIdentMode" value="string_then_ocr"
                :checked="localConfig.ref_ident_mode === 'string_then_ocr'" :disabled="!isOcrReady"
                @change="localConfig.ref_ident_mode = 'string_then_ocr'; markAsCustom()" />
              <div class="radio-option-content">
                <span class="radio-option-label">String Search + OCR Fallback</span>
                <span class="radio-option-desc">Use string search first, then OCR when entries are unclear</span>
              </div>
            </label>
            <label class="radio-option" :class="{ disabled: !isOcrReady }">
              <input type="radio" name="refIdentMode" value="ocr_only"
                :checked="localConfig.ref_ident_mode === 'ocr_only'" :disabled="!isOcrReady"
                @change="localConfig.ref_ident_mode = 'ocr_only'; markAsCustom()" />
              <div class="radio-option-content">
                <span class="radio-option-label">OCR Only</span>
                <span class="radio-option-desc">Use optical character recognition exclusively for all
                  identification</span>
              </div>
            </label>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
/* Layout container for crawler settings cards */
.crawler-settings-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Grid for global settings with top border separator */
.global-settings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--border-color);
}

/* Preset selection - selectable cards for configuration presets */
.preset-selector {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.preset-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 12px;
}

.preset-card {
  padding: 16px;
  background: var(--bg-panel);
  border: 2px solid transparent;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.preset-card:hover {
  border-color: var(--accent-bright);
  background: var(--bg-card-hover);
}

.preset-card.active {
  border-color: var(--accent-color);
  background: var(--bg-selected);
}

.preset-card.custom-preset {
  border-style: dashed;
  border-color: var(--border-color);
}

.preset-card.custom-preset:hover {
  border-color: var(--accent-bright);
}

.preset-card.custom-preset.active {
  border-style: solid;
  border-color: var(--accent-color);
}

.preset-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.preset-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.preset-check {
  color: var(--accent-color);
}

.preset-desc {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 0 0 12px 0;
  line-height: 1.4;
}

.preset-stats {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: var(--text-secondary);
}

/* Engines data table - grid layout for search engine configuration */
.engines-table {
  border: 1px solid var(--border-card);
  border-radius: 8px;
  overflow: hidden;
}

.engines-header,
.engine-row {
  display: grid;
  grid-template-columns: 1fr 80px 100px 100px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-card);
}

.engines-header {
  background: var(--bg-panel);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-secondary);
}

.engine-row {
  transition: background 0.15s;
  position: relative;
}

.engine-row:last-child {
  border-bottom: none;
}

.engine-row:hover {
  background: var(--bg-card-hover);
}

.engine-row.disabled {
  opacity: 0.6;
}

/* Table column alignment */
.col-engine {
  overflow: hidden;
  display: flex;
  gap: 12px;
  align-items: center;
}

.col-status,
.col-rate,
.col-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

/* Engine info - toggle + name/description */
.engine-info {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}

.engine-details {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.engine-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.engine-desc {
  font-size: 11px;
  color: var(--text-secondary);
  margin: 0;
  white-space: wrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 300px;
}

/* Connection status indicators */
.connection-indicator {
  display: flex;
  align-items: center;
}

.status-testing {
  color: var(--accent-color);
}

.status-success {
  color: var(--color-success-600);
}

.status-failed {
  color: var(--color-danger-600);
}

.status-unknown {
  color: var(--text-secondary);
  font-size: 12px;
}

/* Expandable per-engine advanced settings */
.engine-advanced {
  grid-column: 1 / -1;
  padding: 12px 0 0 0;
  border-top: 1px solid var(--border-color);
}

.advanced-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.advanced-row .form-input {
  width: 100px;
}
</style>
