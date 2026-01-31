<script setup lang="ts">
import { ref, computed, watch } from "vue";
import BaseModal from "./BaseModal.vue";
import type {
  CrawlerSearchResult,
  CrawlerSearchQuery,
  CrawlerDownloadResult,
  ManifestEntry,
} from "../types";
import {
  searchPapers,
  downloadPapersStream,
  fetchCrawlerConfig,
} from "../api/client";
import { Search, ChevronDown, ChevronUp, ExternalLink } from "lucide-vue-next";

const props = defineProps<{
  modelValue: boolean;
}>();

const emit = defineEmits<{
  (e: "update:modelValue", value: boolean): void;
  (e: "downloadComplete", entries: ManifestEntry[]): void;
}>();

const searchQuery = ref("");
const selectedEngines = ref<Set<string>>(new Set());
const yearRange = ref<[number, number] | null>(null);
const sortBy = ref<"relevance" | "date" | "citations">("relevance");
const deepCrawl = ref(false);
const deepCrawlMaxPapers = ref(100);
const maxResults = ref(20);

const searchResults = ref<CrawlerSearchResult[]>([]);
const selectedResults = ref<Set<string>>(new Set());
const expandedAbstracts = ref<Set<string>>(new Set());

const isSearching = ref(false);
const isDownloading = ref(false);
const showDownloadConfirm = ref(false);
const searchError = ref<string | null>(null);

const downloadProgress = ref({ current: 0, total: 0 });
const downloadResults = ref<Map<string, CrawlerDownloadResult>>(new Map());

const availableEngines = ref<string[]>([]);
const enabledEngines = ref<string[]>([]);

const sortOptions = [
  { value: "relevance", label: "Relevance" },
  { value: "date", label: "Date" },
  { value: "citations", label: "Citations" },
];

const selectedCount = computed(() => selectedResults.value.size);

const allSelected = computed(() => {
  if (searchResults.value.length === 0) return false;
  return searchResults.value.every((r) => selectedResults.value.has(r.hash));
});

const papersWithPdfs = computed(() =>
  searchResults.value.filter((r) => r.pdf_url)
);

watch(() => props.modelValue, async (isOpen) => {
  if (isOpen) {
    await loadEngines();
  } else {
    resetState();
  }
});

async function loadEngines() {
  try {
    const config = await fetchCrawlerConfig();
    availableEngines.value = Object.keys(config.engines);
    enabledEngines.value = Object.keys(config.engines).filter(
      (e) => config.engines[e].enabled
    );
    selectedEngines.value = new Set(enabledEngines.value);
  } catch (e) {
    console.error("Failed to load engines:", e);
  }
}

function resetState() {
  searchQuery.value = "";
  searchResults.value = [];
  selectedResults.value.clear();
  expandedAbstracts.value.clear();
  isSearching.value = false;
  isDownloading.value = false;
  showDownloadConfirm.value = false;
  searchError.value = null;
  downloadProgress.value = { current: 0, total: 0 };
  downloadResults.value.clear();
}

async function handleSearch() {
  if (!searchQuery.value.trim()) {
    searchError.value = "Please enter a search query";
    return;
  }

  if (selectedEngines.value.size === 0) {
    searchError.value = "Please select at least one engine";
    return;
  }

  isSearching.value = true;
  searchError.value = null;
  searchResults.value = [];
  selectedResults.value.clear();

  try {
    const query: CrawlerSearchQuery = {
      query: searchQuery.value.trim(),
      max_results: maxResults.value,
      engines: Array.from(selectedEngines.value),
      year_range: yearRange.value,
      sort_by: sortBy.value,
      deep_crawl: deepCrawl.value,
      deep_crawl_max_papers: deepCrawl.value ? deepCrawlMaxPapers.value : undefined,
    };

    const results = await searchPapers(query);
    searchResults.value = results;
  } catch (e: any) {
    searchError.value = e.message || "Search failed";
  } finally {
    isSearching.value = false;
  }
}

function toggleAllEngines() {
  if (selectedEngines.value.size === availableEngines.value.length) {
    selectedEngines.value = new Set();
  } else {
    selectedEngines.value = new Set(enabledEngines.value);
  }
}

function toggleEngine(engine: string) {
  const newSet = new Set(selectedEngines.value);
  if (newSet.has(engine)) {
    newSet.delete(engine);
  } else {
    newSet.add(engine);
  }
  selectedEngines.value = newSet;
}

function toggleAllSelection() {
  const downloadablePapers = papersWithPdfs.value;
  if (allSelected.value) {
    selectedResults.value = new Set();
  } else {
    selectedResults.value = new Set(
      downloadablePapers.map((r) => r.hash)
    );
  }
}

function toggleSelection(hash: string, hasPdf: boolean | null) {
  if (hasPdf === false) return;

  const newSet = new Set(selectedResults.value);
  if (newSet.has(hash)) {
    newSet.delete(hash);
  } else {
    newSet.add(hash);
  }
  selectedResults.value = newSet;
}

function toggleAbstract(hash: string) {
  if (expandedAbstracts.value.has(hash)) {
    expandedAbstracts.value.delete(hash);
  } else {
    expandedAbstracts.value.add(hash);
  }
}

function formatAuthors(authors: string[]): string {
  if (!authors || authors.length === 0) return "";
  if (authors.length <= 2) return authors.join(" & ");
  return `${authors[0]} et al.`;
}

function openDownloadConfirm() {
  if (selectedCount.value === 0) return;
  showDownloadConfirm.value = true;
}

async function confirmDownload() {
  showDownloadConfirm.value = false;
  isDownloading.value = true;
  downloadProgress.value = { current: 0, total: selectedCount.value };
  downloadResults.value.clear();

  const selectedPapers = searchResults.value.filter((r) =>
    selectedResults.value.has(r.hash)
  );

  try {
    await downloadPapersStream(selectedPapers, false, {
      onStart: (total) => {
        downloadProgress.value = { current: 0, total };
      },
      onProgress: (current, total, result) => {
        downloadProgress.value = { current, total };
        downloadResults.value.set(result.hash, result);
      },
      onComplete: (results) => {
        isDownloading.value = false;
        const successCount = results.filter((r) => r.success).length;
        if (successCount > 0) {
          emit("update:modelValue", false);
          emit("downloadComplete", []);
        }
      },
      onError: (error) => {
        console.error("Download error:", error);
        isDownloading.value = false;
      },
    });
  } catch (e) {
    console.error("Download failed:", e);
    isDownloading.value = false;
  }
}

function cancelDownload() {
  showDownloadConfirm.value = false;
}
</script>

<template>
  <BaseModal
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    title="Search Online"
    size="xlarge"
    :close-on-esc="!isSearching && !isDownloading"
    :close-on-click-outside="!isSearching && !isDownloading"
  >
    <div class="crawler-modal">
      <!-- Search Section -->
      <div v-if="!isDownloading" class="search-section">
        <div class="search-input-row">
          <div class="search-input-wrapper">
            <Search :size="16" class="search-icon" />
            <input
              v-model="searchQuery"
              type="text"
              placeholder="Search for papers..."
              class="search-input"
              @keyup.enter="handleSearch"
            />
          </div>
          <button class="btn-primary" @click="handleSearch" :disabled="isSearching">
            <span v-if="isSearching">Searching...</span>
            <span v-else>Search</span>
          </button>
        </div>

        <!-- Search Options -->
        <div class="search-options">
          <!-- Engine Selection -->
          <div class="option-group">
            <label class="option-label">Engines</label>
            <div class="engine-checkboxes">
              <label class="engine-checkbox">
                <input
                  type="checkbox"
                  :checked="selectedEngines.size === availableEngines.length"
                  @click="toggleAllEngines"
                />
                <span>All</span>
              </label>
              <label
                v-for="engine in availableEngines"
                :key="engine"
                class="engine-checkbox"
              >
                <input
                  type="checkbox"
                  :checked="selectedEngines.has(engine)"
                  @click="toggleEngine(engine)"
                />
                <span>{{ engine }}</span>
              </label>
            </div>
          </div>

          <!-- Year Range -->
          <div class="option-group">
            <label class="option-label">Year Range</label>
            <div class="year-inputs">
              <input
                :value="yearRange?.[0]"
                @input="(e) => { if (yearRange) yearRange[0] = parseInt((e.target as HTMLInputElement).value) }"
                type="number"
                placeholder="From"
                class="year-input"
              />
              <span class="year-separator">to</span>
              <input
                :value="yearRange?.[1]"
                @input="(e) => { if (yearRange) yearRange[1] = parseInt((e.target as HTMLInputElement).value) }"
                type="number"
                placeholder="To"
                class="year-input"
              />
            </div>
          </div>

          <!-- Sort By -->
          <div class="option-group">
            <label class="option-label">Sort By</label>
            <select v-model="sortBy" class="sort-select">
              <option
                v-for="option in sortOptions"
                :key="option.value"
                :value="option.value"
              >
                {{ option.label }}
              </option>
            </select>
          </div>

          <!-- Max Results -->
          <div class="option-group">
            <label class="option-label">Max Results per Engine</label>
            <input
              v-model.number="maxResults"
              type="number"
              min="5"
              max="100"
              class="number-input"
            />
          </div>

          <!-- Deep Crawl -->
          <div class="option-group">
            <label class="option-label">Deep Crawl</label>
            <div class="deep-crawl-controls">
              <label class="toggle-label">
                <input type="checkbox" v-model="deepCrawl" />
                <span>Enable citation expansion</span>
              </label>
              <input
                v-if="deepCrawl"
                v-model.number="deepCrawlMaxPapers"
                type="number"
                min="10"
                max="500"
                placeholder="Max papers"
                class="number-input small"
              />
            </div>
          </div>
        </div>

        <!-- Search Error -->
        <div v-if="searchError" class="error-banner">
          {{ searchError }}
        </div>
      </div>

      <!-- Results Section -->
      <div
        v-if="!isSearching && !isDownloading && searchResults.length > 0"
        class="results-section"
      >
        <div class="results-header">
          <div class="results-count">
            {{ searchResults.length }} papers found
            <span v-if="papersWithPdfs.length < searchResults.length" class="pdf-hint">
              ({{ papersWithPdfs.length }} with PDFs)
            </span>
          </div>
          <div class="results-actions">
            <button class="btn-text" @click="toggleAllSelection">
              {{ allSelected ? "Deselect All" : "Select All" }}
            </button>
            <button
              class="btn-primary"
              @click="openDownloadConfirm"
              :disabled="selectedCount === 0"
            >
              Download Selected ({{ selectedCount }})
            </button>
          </div>
        </div>

        <div class="results-list">
          <div
            v-for="result in searchResults"
            :key="result.hash"
            class="result-card"
            :class="{ 
              selected: selectedResults.has(result.hash),
              'no-pdf': !result.pdf_url
            }"
          >
            <div class="result-header">
              <input
                type="checkbox"
                :checked="selectedResults.has(result.hash)"
                :disabled="!result.pdf_url"
                @click="toggleSelection(result.hash, !!result.pdf_url)"
                class="result-checkbox"
              />
              <div class="result-main">
                <div v-if="result.pdf_url" class="pdf-badge">
                  PDF Available
                </div>
                <div v-else class="no-pdf-badge">
                  No PDF
                </div>
                <h4 class="result-title">{{ result.title }}</h4>
                <div class="result-meta">
                  <span v-if="result.authors.length" class="result-authors">
                    {{ formatAuthors(result.authors) }}
                  </span>
                  <span v-if="result.year" class="result-year">
                    {{ result.year }}
                  </span>
                  <span v-if="result.citations" class="result-citations">
                    {{ result.citations }} citations
                  </span>
                  <span class="result-source">{{ result.source }}</span>
                </div>
              </div>
            </div>

            <div class="result-links">
              <a
                v-if="result.doi"
                :href="`https://doi.org/${result.doi}`"
                target="_blank"
                class="result-link"
              >
                DOI <ExternalLink :size="12" />
              </a>
              <a
                v-if="result.url"
                :href="result.url"
                target="_blank"
                class="result-link"
              >
                Source <ExternalLink :size="12" />
              </a>
            </div>

            <div
              v-if="result.abstract"
              class="result-abstract"
              :class="{ expanded: expandedAbstracts.has(result.hash) }"
            >
              <button
                class="abstract-toggle"
                @click="toggleAbstract(result.hash)"
              >
                <span v-if="expandedAbstracts.has(result.hash)">
                  <ChevronUp :size="14" /> Hide Abstract
                </span>
                <span v-else>
                  <ChevronDown :size="14" /> Show Abstract
                </span>
              </button>
              <p v-if="expandedAbstracts.has(result.hash)" class="abstract-text">
                {{ result.abstract }}
              </p>
            </div>
          </div>
        </div>
      </div>

      <!-- Download Progress Section -->
      <div v-if="isDownloading" class="download-progress-section">
        <h3 class="progress-title">Downloading Papers</h3>
        <div class="progress-bar">
          <div
            class="progress-fill"
            :style="{
              width: `${(downloadProgress.current / downloadProgress.total) * 100}%`,
            }"
          ></div>
        </div>
        <div class="progress-text">
          {{ downloadProgress.current }} / {{ downloadProgress.total }}
        </div>

        <div class="download-results">
          <div
            v-for="[hash, result] in Array.from(downloadResults.entries())"
            :key="hash"
            class="download-result-item"
            :class="{ success: result.success, error: !result.success }"
          >
            <span class="result-status">
              {{ result.success ? "✓" : "✗" }}
            </span>
            <span class="result-message">
              {{ result.success ? "Downloaded" : result.error || "Failed" }}
            </span>
          </div>
        </div>
      </div>

      <!-- Download Confirmation Modal -->
      <BaseModal
        :model-value="showDownloadConfirm"
        @update:model-value="showDownloadConfirm = $event"
        title="Confirm Download"
        size="small"
      >
        <div class="download-confirm">
          <p class="confirm-text">
            You are about to download <strong>{{ selectedCount }}</strong> papers.
          </p>
          <p class="confirm-hint">
            Papers will be added to your Reference Bank.
          </p>
          <div class="confirm-actions">
            <button class="btn-secondary" @click="cancelDownload">
              Cancel
            </button>
            <button class="btn-primary" @click="confirmDownload">
              Confirm Download
            </button>
          </div>
        </div>
      </BaseModal>
    </div>
  </BaseModal>
</template>

<style scoped>
.crawler-modal {
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-height: 500px;
}

.search-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.search-input-row {
  display: flex;
  gap: 12px;
}

.search-input-wrapper {
  flex: 1;
  display: flex;
  align-items: center;
  background: var(--bg-panel);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 0 12px;
}

.search-icon {
  color: var(--text-secondary);
  flex-shrink: 0;
}

.search-input {
  flex: 1;
  border: none;
  background: transparent;
  padding: 10px 8px;
  font-size: 14px;
  color: var(--text-primary);
  outline: none;
}

.search-input::placeholder {
  color: var(--text-secondary);
}

.btn-primary {
  padding: 10px 20px;
  font-size: 13px;
  font-weight: 500;
  background: var(--accent-color);
  color: white;
  border: none;
  border-radius: 8px;
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
  padding: 8px 16px;
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

.btn-text {
  padding: 6px 12px;
  font-size: 12px;
  background: transparent;
  color: var(--accent-color);
  border: none;
  cursor: pointer;
}

.btn-text:hover {
  text-decoration: underline;
}

.search-options {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  padding: 16px;
  background: var(--bg-panel);
  border-radius: 8px;
}

.option-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.option-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
}

.engine-checkboxes {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.engine-checkbox {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-primary);
  cursor: pointer;
}

.year-inputs {
  display: flex;
  align-items: center;
  gap: 8px;
}

.year-input {
  width: 80px;
  padding: 6px 8px;
  font-size: 12px;
  background: var(--color-white);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  color: var(--text-primary);
}

.year-separator {
  font-size: 12px;
  color: var(--text-secondary);
}

.sort-select,
.number-input {
  padding: 6px 10px;
  font-size: 12px;
  background: var(--color-white);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  color: var(--text-primary);
}

.number-input.small {
  width: 100px;
}

.deep-crawl-controls {
  display: flex;
  align-items: center;
  gap: 12px;
}

.toggle-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-primary);
  cursor: pointer;
}

.error-banner {
  padding: 12px;
  background: rgba(211, 47, 47, 0.1);
  border: 1px solid var(--color-danger-400);
  border-radius: 8px;
  font-size: 13px;
  color: var(--color-danger-800);
}

.results-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1;
  overflow: hidden;
}

.results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: var(--bg-panel);
  border-radius: 8px;
}

.results-count {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.pdf-hint {
  font-size: 11px;
  color: var(--text-secondary);
  margin-left: 8px;
}

.results-actions {
  display: flex;
  gap: 8px;
}

.results-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-right: 8px;
}

.result-card {
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: 8px;
  padding: 12px;
  transition: all 0.2s;
}

.result-card.selected {
  border-color: var(--accent-color);
  background: rgba(59, 130, 246, 0.05);
}

.result-card.no-pdf {
  opacity: 0.6;
  background: var(--bg-panel);
}

.result-header {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.pdf-badge {
  background: var(--color-success-50);
  color: var(--color-success-700);
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 500;
  margin-bottom: 6px;
}

.no-pdf-badge {
  background: var(--color-neutral-200);
  color: var(--text-secondary);
  padding: 2.5px 8px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 500;
  margin-bottom: 6px;
}

.result-checkbox {
  margin-top: 4px;
  flex-shrink: 0;
}

.result-main {
  flex: 1;
}

.result-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  margin: 0 0 6px 0;
  line-height: 1.4;
;
}

.result-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 12px;
  color: var(--text-secondary);
}

.result-authors,
.result-year,
.result-citations,
.result-source {
  display: flex;
  align-items: center;
  gap: 4px;
}

.result-source {
  background: var(--bg-panel);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
}

.result-links {
  display: flex;
  gap: 12px;
  margin-top: 8px;
}

.result-link {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--accent-color);
  text-decoration: none;
}

.result-link:hover {
  text-decoration: underline;
}

.result-abstract {
  margin-top: 12px;
  border-top: 1px solid var(--border-color);
  padding-top: 8px;
}

.abstract-toggle {
  background: transparent;
  border: none;
  color: var(--accent-color);
  font-size: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 0;
}

.abstract-toggle:hover {
  text-decoration: underline;
}

.abstract-text {
  margin-top: 8px;
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.5;
}

.download-progress-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px;
  text-align: center;
}

.progress-title {
  font-size: 16px;
  font-weight: 500;
  color: var(--text-primary);
  margin: 0;
}

.progress-bar {
  height: 8px;
  background: var(--color-neutral-240);
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--accent-color);
  transition: width 0.3s;
}

.progress-text {
  font-size: 13px;
  color: var(--text-secondary);
}

.download-results {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 300px;
  overflow-y: auto;
  text-align: left;
}

.download-result-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg-panel);
  border-radius: 6px;
  font-size: 12px;
}

.download-result-item.success {
  border-left: 3px solid var(--color-success-600);
}

.download-result-item.error {
  border-left: 3px solid var(--color-danger-400);
}

.result-status {
  flex-shrink: 0;
}

.result-message {
  flex: 1;
  color: var(--text-primary);
}

.download-confirm {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.confirm-text {
  font-size: 14px;
  color: var(--text-primary);
  margin: 0;
}

.confirm-hint {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 0;
}

.confirm-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}
</style>
