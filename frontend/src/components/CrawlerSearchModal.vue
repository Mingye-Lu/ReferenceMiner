<script setup lang="ts">
import { ref, computed, watch } from "vue";
import BaseModal from "./BaseModal.vue";
import BaseToggle from "./BaseToggle.vue";
import CustomSelect from "./CustomSelect.vue";
import googleScholarIcon from "../assets/google-scholar.svg";
import pubmedIcon from "../assets/pubmed.svg";
import semanticScholarIcon from "../assets/semantic-scholar.svg";
import arxivIcon from "../assets/arxiv.svg";
import biorxivIcon from "../assets/biorxiv.svg";
import coreIcon from "../assets/core.svg";
import crossrefIcon from "../assets/crossref.svg";
import europePmcIcon from "../assets/europe-pmc.svg";
import openalexIcon from "../assets/openalex.svg";
import airitiIcon from "../assets/airiti.svg";
import type { CrawlerSearchResult, CrawlerSearchQuery } from "../types";
import {
  searchPapers,
  downloadPapersQueueStream,
  fetchCrawlerConfig,
} from "../api/client";
import { useQueue } from "../composables/useQueue";
import {
  Search,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  ArrowUpDown,
  Settings,
} from "lucide-vue-next";

const props = defineProps<{
  modelValue: boolean;
}>();

const emit = defineEmits<{
  (e: "update:modelValue", value: boolean): void;
  (e: "openSettings"): void;
}>();

const { launchQueueEject } = useQueue();
const downloadAllButtonRef = ref<HTMLButtonElement | null>(null);

const searchQuery = ref("");
const selectedEngines = ref<Set<string>>(new Set());
const yearFrom = ref<number | null>(null);
const yearTo = ref<number | null>(null);
const sortBy = ref<"relevance" | "date" | "citations">("relevance");
const deepCrawl = ref(false);
const deepCrawlMaxPapers = ref(100);
const maxResults = ref(20);
const crawlerEnabled = ref(true);

const searchResults = ref<CrawlerSearchResult[]>([]);
const selectedResults = ref<Set<string>>(new Set());
const expandedAbstracts = ref<Set<string>>(new Set());
const showAdvanced = ref(false);
const hasSearched = ref(false);

const isSearching = ref(false);
const searchError = ref<string | null>(null);
const isLoadingEngines = ref(false);

const availableEngines = ref<string[]>([]);
const enabledEngines = ref<string[]>([]);

const sortOptions = [
  { value: "relevance", label: "Relevance" },
  { value: "date", label: "Date" },
  { value: "citations", label: "Citations" },
];

const engineIcons: Record<string, string> = {
  google_scholar: googleScholarIcon,
  pubmed: pubmedIcon,
  semantic_scholar: semanticScholarIcon,
  arxiv: arxivIcon,
  crossref: crossrefIcon,
  openalex: openalexIcon,
  core: coreIcon,
  europe_pmc: europePmcIcon,
  biorxiv_medrxiv: biorxivIcon,
  airiti: airitiIcon,
};

const showFilters = ref(false);
const filterEngines = ref<Set<string>>(new Set());
const filterPdfOnly = ref<boolean | null>(null);
const filterYearRange = ref<[number, number] | null>(null);
const filterMinCitations = ref<number | null>(null);
const filterKeywords = ref<string>("");
const downloadQueueing = ref<Set<string>>(new Set());
const downloadQueued = ref<Set<string>>(new Set());
const downloadErrors = ref<Record<string, string>>({});

const selectedCount = computed(() => selectedResults.value.size);

function getResultKey(result: CrawlerSearchResult, index: number): string {
  const trimmedHash = result.hash?.trim();
  if (trimmedHash) return trimmedHash;
  const fallback =
    result.doi ||
    result.url ||
    `${result.title}-${result.year ?? ""}-${result.source}`;
  return `${fallback}-${index}`;
}

const keyedResults = computed(() =>
  searchResults.value.map((result, index) => ({
    result,
    key: getResultKey(result, index),
  })),
);

const allSelected = computed(() => {
  if (filteredResults.value.length === 0) return false;
  return filteredResults.value.every((item) =>
    selectedResults.value.has(item.key),
  );
});

const resultEngines = computed(() => {
  const engines = new Set<string>();
  searchResults.value.forEach((result) => {
    if (result.source) engines.add(result.source);
  });
  return Array.from(engines);
});

const filteredResults = computed(() => {
  let results = keyedResults.value;

  if (filterEngines.value.size > 0) {
    results = results.filter((item) =>
      filterEngines.value.has(item.result.source),
    );
  }

  if (filterPdfOnly.value !== null) {
    results = results.filter((item) =>
      filterPdfOnly.value ? !!item.result.pdf_url : !item.result.pdf_url,
    );
  }

  if (filterYearRange.value) {
    results = results.filter((item) => {
      if (!item.result.year) return false;
      const year = item.result.year;
      return (
        year >= filterYearRange.value![0] && year <= filterYearRange.value![1]
      );
    });
  }

  if (filterMinCitations.value !== null) {
    results = results.filter(
      (item) => (item.result.citations ?? 0) >= filterMinCitations.value!,
    );
  }

  if (filterKeywords.value.trim()) {
    const keywords = filterKeywords.value.toLowerCase();
    results = results.filter((item) => {
      const titleMatch = item.result.title.toLowerCase().includes(keywords);
      const abstractMatch = item.result.abstract
        ?.toLowerCase()
        .includes(keywords);
      return titleMatch || abstractMatch;
    });
  }

  return results;
});

const filteredPapersWithPdfs = computed(() =>
  filteredResults.value.filter((item) => item.result.pdf_url),
);

const activeFilterCount = computed(() => {
  let count = 0;
  if (filterEngines.value.size > 0) count++;
  if (filterPdfOnly.value !== null) count++;
  if (filterYearRange.value) count++;
  if (filterMinCitations.value !== null) count++;
  if (filterKeywords.value.trim()) count++;
  return count;
});

watch(
  () => props.modelValue,
  async (isOpen) => {
    if (isOpen) {
      await loadEngines();
    } else {
      resetState();
    }
  },
);

async function loadEngines() {
  isLoadingEngines.value = true;
  try {
    const config = await fetchCrawlerConfig();
    availableEngines.value = Object.keys(config.engines);
    enabledEngines.value = Object.keys(config.engines).filter(
      (e) => config.engines[e].enabled,
    );
    selectedEngines.value = new Set(enabledEngines.value);
    maxResults.value = config.max_results_per_engine;
    crawlerEnabled.value = config.enabled;
  } catch (e) {
    console.error("Failed to load engines:", e);
  } finally {
    isLoadingEngines.value = false;
  }
}

function resetState() {
  searchQuery.value = "";
  searchResults.value = [];
  selectedResults.value.clear();
  expandedAbstracts.value.clear();
  downloadQueueing.value = new Set();
  downloadQueued.value = new Set();
  downloadErrors.value = {};
  showAdvanced.value = false;
  hasSearched.value = false;
  isSearching.value = false;
  searchError.value = null;
  isLoadingEngines.value = false;
  yearFrom.value = null;
  yearTo.value = null;
  crawlerEnabled.value = true;
  resetFilters();
}

function resetFilters() {
  filterEngines.value.clear();
  filterPdfOnly.value = null;
  filterYearRange.value = null;
  filterMinCitations.value = null;
  filterKeywords.value = "";
  showFilters.value = false;
}

async function handleSearch() {
  if (!searchQuery.value.trim()) {
    searchError.value = "Please enter a search query";
    return;
  }

  if (!crawlerEnabled.value) {
    searchError.value = "Crawler is disabled in Settings";
    return;
  }

  if (selectedEngines.value.size === 0) {
    searchError.value = "Please select at least one engine";
    return;
  }

  hasSearched.value = true;
  isSearching.value = true;
  searchError.value = null;
  searchResults.value = [];
  selectedResults.value.clear();
  downloadQueueing.value = new Set();
  downloadQueued.value = new Set();
  downloadErrors.value = {};

  try {
    const query: CrawlerSearchQuery = {
      query: searchQuery.value.trim(),
      max_results: maxResults.value,
      engines: Array.from(selectedEngines.value),
      year_from: yearFrom.value,
      year_to: yearTo.value,
      sort_by: sortBy.value,
      deep_crawl: deepCrawl.value,
      deep_crawl_max_papers: deepCrawl.value
        ? deepCrawlMaxPapers.value
        : undefined,
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
    selectedEngines.value = new Set(availableEngines.value);
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

function toggleFilterEngine(engine: string) {
  const newSet = new Set(filterEngines.value);
  if (newSet.has(engine)) {
    newSet.delete(engine);
  } else {
    newSet.add(engine);
  }
  filterEngines.value = newSet;
}

function toggleAllFilterEngines() {
  if (filterEngines.value.size === resultEngines.value.length) {
    filterEngines.value.clear();
  } else {
    filterEngines.value = new Set(resultEngines.value);
  }
}

function toggleAllSelection() {
  if (allSelected.value) {
    selectedResults.value = new Set();
  } else {
    selectedResults.value = new Set(
      filteredPapersWithPdfs.value.map((item) => item.key),
    );
  }
}

function toggleSelection(
  key: string,
  hasPdf: boolean | null,
  event?: MouseEvent,
) {
  if (hasPdf === false) return;
  if (event) {
    const target = event.target as HTMLElement;
    if (target.tagName === "A" || target.closest("a")) {
      return;
    }
  }

  const newSet = new Set(selectedResults.value);
  if (newSet.has(key)) {
    newSet.delete(key);
  } else {
    newSet.add(key);
  }
  selectedResults.value = newSet;
}

function toggleAbstract(key: string) {
  const next = new Set(expandedAbstracts.value);
  if (next.has(key)) {
    next.delete(key);
  } else {
    next.add(key);
  }
  expandedAbstracts.value = next;
}

function formatAuthors(authors: string[]): string {
  if (!authors || authors.length === 0) return "";
  if (authors.length <= 2) return authors.join(" & ");
  return `${authors[0]} et al.`;
}

function getEngineIcon(engine: string): string | undefined {
  return engineIcons[engine];
}

async function queueSingleDownload(
  key: string,
  result: CrawlerSearchResult,
  event?: MouseEvent,
) {
  if (!result.pdf_url) return;
  if (downloadQueueing.value.has(key) || downloadQueued.value.has(key)) return;

  const target = event?.currentTarget as HTMLElement | null;
  const rect = target?.getBoundingClientRect();
  const startX = rect ? rect.left + rect.width / 2 : null;
  const startY = rect ? rect.top + rect.height / 2 : null;

  const nextQueueing = new Set(downloadQueueing.value);
  nextQueueing.add(key);
  downloadQueueing.value = nextQueueing;
  downloadErrors.value = { ...downloadErrors.value, [key]: "" };

  try {
    await downloadPapersQueueStream([result], false);
    const nextQueued = new Set(downloadQueued.value);
    nextQueued.add(key);
    downloadQueued.value = nextQueued;
    if (startX !== null && startY !== null) {
      launchQueueEject(startX, startY);
    }
  } catch (e) {
    const message = e instanceof Error ? e.message : "Queueing failed";
    downloadErrors.value = { ...downloadErrors.value, [key]: message };
  } finally {
    const next = new Set(downloadQueueing.value);
    next.delete(key);
    downloadQueueing.value = next;
  }
}

function updateYearInput(target: "from" | "to", value: string) {
  const trimmed = value.trim();
  if (!trimmed) {
    if (target === "from") yearFrom.value = null;
    else yearTo.value = null;
    return;
  }

  const parsed = Number.parseInt(trimmed, 10);
  if (Number.isNaN(parsed)) return;

  if (target === "from") yearFrom.value = parsed;
  else yearTo.value = parsed;
}

async function confirmDownload() {
  if (selectedCount.value === 0) return;

  const selectedPapers = keyedResults.value
    .filter((item) => selectedResults.value.has(item.key))
    .map((item) => item.result);

  try {
    await downloadPapersQueueStream(selectedPapers, false);
    const rect = downloadAllButtonRef.value?.getBoundingClientRect();
    if (rect) {
      launchQueueEject(rect.left + rect.width / 2, rect.top + rect.height / 2);
    }
    emit("update:modelValue", false);
  } catch (e) {
    console.error("Download failed:", e);
    searchError.value = e instanceof Error ? e.message : "Download failed";
  }
}
</script>

<template>
  <BaseModal
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    title="Search Online"
    size="xlarge"
    :close-on-esc="!isSearching"
    :close-on-click-outside="!isSearching"
  >
    <template #header-actions>
      <button
        class="configure-btn"
        @click="emit('openSettings')"
        title="Configure crawler settings"
      >
        <Settings :size="14" />
        Configure
      </button>
    </template>
    <div class="crawler-modal">
      <!-- Search Section -->
      <div class="search-section">
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
          <button
            class="btn-primary search-btn"
            @click="handleSearch"
            :disabled="isSearching"
          >
            <span v-if="isSearching">Searching...</span>
            <span v-else>Search</span>
          </button>
        </div>
        <p class="search-hint">Try keywords, author names, or paper titles.</p>

        <!-- Search Options -->
        <div class="search-options">
          <div class="search-options-header">
            <div class="section-title">Search Options</div>
            <button
              class="advanced-toggle"
              type="button"
              @click="showAdvanced = !showAdvanced"
            >
              {{ showAdvanced ? "Hide advanced" : "Show advanced" }}
            </button>
          </div>
          <!-- Engine Selection -->
          <div class="search-options-grid">
            <div class="form-row">
              <label class="form-label">Engines</label>
              <div v-if="isLoadingEngines" class="engine-empty">
                Loading engines...
              </div>
              <div
                v-else-if="availableEngines.length === 0"
                class="engine-empty"
              >
                No engines available. Check Settings → Web Crawler.
              </div>
              <div v-else class="engine-checkboxes">
                <div
                  class="engine-card"
                  :class="{
                    selected: selectedEngines.size === availableEngines.length,
                  }"
                  @click="toggleAllEngines"
                >
                  <span>All</span>
                </div>
                <div
                  v-for="engine in availableEngines"
                  :key="engine"
                  class="engine-card"
                  :class="{ selected: selectedEngines.has(engine) }"
                  @click="toggleEngine(engine)"
                >
                  <img
                    v-if="getEngineIcon(engine)"
                    :src="getEngineIcon(engine)"
                    :alt="`${engine} icon`"
                    class="engine-icon"
                  />
                  <span>{{ engine }}</span>
                </div>
              </div>
            </div>

            <div class="form-row">
              <label class="form-label">Max Results per Engine</label>
              <input
                v-model.number="maxResults"
                type="number"
                min="5"
                max="100"
                class="form-input"
              />
            </div>
          </div>

          <div v-if="showAdvanced" class="advanced-options">
            <div class="form-row">
              <label class="form-label">Year Range</label>
              <div class="year-inputs">
                <input
                  :value="yearFrom ?? ''"
                  @input="
                    updateYearInput(
                      'from',
                      ($event.target as HTMLInputElement).value,
                    )
                  "
                  type="number"
                  placeholder="From"
                  class="form-input year-input"
                />
                <span class="year-separator">to</span>
                <input
                  :value="yearTo ?? ''"
                  @input="
                    updateYearInput(
                      'to',
                      ($event.target as HTMLInputElement).value,
                    )
                  "
                  type="number"
                  placeholder="To"
                  class="form-input year-input"
                />
              </div>
            </div>

            <div class="form-row">
              <label class="form-label">Deep Crawl</label>
              <div class="deep-crawl-controls">
                <div class="toggle-wrapper">
                  <BaseToggle v-model="deepCrawl" />
                  <span class="toggle-label-text">
                    Enable citation expansion
                  </span>
                </div>
                <input
                  v-if="deepCrawl"
                  v-model.number="deepCrawlMaxPapers"
                  type="number"
                  min="10"
                  max="500"
                  placeholder="Max papers"
                  class="form-input deep-crawl-input"
                />
              </div>
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
        v-if="!isSearching && searchResults.length > 0"
        class="results-section"
      >
        <div class="results-list">
          <div class="results-header">
            <div class="results-info">
              <div class="resultsCount">
                <span v-if="activeFilterCount > 0">
                  {{ filteredResults.length }} of
                  {{ searchResults.length }} papers
                </span>
                <span v-else> {{ searchResults.length }} papers found </span>
                <span
                  v-if="filteredPapersWithPdfs.length < filteredResults.length"
                  class="pdf-hint"
                >
                  ({{ filteredPapersWithPdfs.length }} with PDFs)
                </span>
              </div>
              <div class="results-sort">
                <ArrowUpDown :size="14" />
                <CustomSelect v-model="sortBy" :options="sortOptions" />
              </div>
            </div>
            <div class="results-actions">
              <button
                class="btn-text"
                @click="showFilters = !showFilters"
                v-if="searchResults.length > 0"
              >
                {{ showFilters ? "Hide Filters" : "Show Filters" }}
                <span v-if="activeFilterCount > 0" class="filter-badge">
                  {{ activeFilterCount }}
                </span>
              </button>
              <button class="btn-text" @click="toggleAllSelection">
                {{ allSelected ? "Deselect All" : "Select All" }}
              </button>
              <button
                class="btn-primary"
                @click="confirmDownload"
                :disabled="selectedCount === 0"
                ref="downloadAllButtonRef"
              >
                Download Selected ({{ selectedCount }})
              </button>
            </div>
          </div>

          <div v-if="showFilters" class="filter-panel">
            <div class="filter-panel-header">
              <div class="section-title">Filter Results</div>
              <button
                v-if="activeFilterCount > 0"
                class="btn-text"
                @click="resetFilters"
              >
                Clear Filters
              </button>
            </div>
            <div class="filter-grid">
              <div class="form-row">
                <label class="form-label">Engines</label>
                <div v-if="resultEngines.length === 0" class="engine-empty">
                  No engines in results
                </div>
                <div v-else class="engine-checkboxes">
                  <div
                    class="engine-card"
                    :class="{
                      selected: filterEngines.size === resultEngines.length,
                    }"
                    @click="toggleAllFilterEngines"
                  >
                    <span>All</span>
                  </div>
                  <div
                    v-for="engine in resultEngines"
                    :key="engine"
                    class="engine-card"
                    :class="{ selected: filterEngines.has(engine) }"
                    @click="toggleFilterEngine(engine)"
                  >
                    <img
                      v-if="getEngineIcon(engine)"
                      :src="getEngineIcon(engine)"
                      :alt="`${engine} icon`"
                      class="engine-icon"
                    />
                    <span>{{ engine }}</span>
                  </div>
                </div>
              </div>

              <div class="form-row">
                <label class="form-label">PDF Availability</label>
                <div class="engine-checkboxes">
                  <div
                    class="engine-card"
                    :class="{ selected: filterPdfOnly === null }"
                    @click="filterPdfOnly = null"
                  >
                    <span>All</span>
                  </div>
                  <div
                    class="engine-card"
                    :class="{ selected: filterPdfOnly === true }"
                    @click="filterPdfOnly = true"
                  >
                    <span>With PDF</span>
                  </div>
                  <div
                    class="engine-card"
                    :class="{ selected: filterPdfOnly === false }"
                    @click="filterPdfOnly = false"
                  >
                    <span>Without PDF</span>
                  </div>
                </div>
              </div>

              <div class="form-row">
                <label class="form-label">Year Range</label>
                <div class="year-inputs">
                  <input
                    :value="filterYearRange?.[0]"
                    @input="
                      (e) => {
                        if (!filterYearRange) filterYearRange = [0, 0];
                        filterYearRange[0] = parseInt(
                          (e.target as HTMLInputElement).value,
                        );
                      }
                    "
                    type="number"
                    placeholder="From"
                    class="form-input year-input"
                  />
                  <span class="year-separator">to</span>
                  <input
                    :value="filterYearRange?.[1]"
                    @input="
                      (e) => {
                        if (!filterYearRange) filterYearRange = [0, 0];
                        filterYearRange[1] = parseInt(
                          (e.target as HTMLInputElement).value,
                        );
                      }
                    "
                    type="number"
                    placeholder="To"
                    class="form-input year-input"
                  />
                </div>
              </div>

              <div class="form-row">
                <label class="form-label">Min Citations</label>
                <input
                  v-model.number="filterMinCitations"
                  type="number"
                  min="0"
                  placeholder="0"
                  class="form-input"
                />
              </div>

              <div class="form-row">
                <label class="form-label">Keywords</label>
                <input
                  v-model="filterKeywords"
                  type="text"
                  placeholder="Search in title/abstract..."
                  class="form-input"
                />
              </div>
            </div>
          </div>

          <div
            v-for="item in filteredResults"
            :key="item.key"
            class="result-card"
            :class="{
              selected: selectedResults.has(item.key),
              'no-pdf': !item.result.pdf_url,
              clickable: !!item.result.pdf_url,
            }"
            @click="(e) => toggleSelection(item.key, !!item.result.pdf_url, e)"
          >
            <div class="result-header">
              <div class="result-main">
                <div class="result-badges">
                  <div v-if="item.result.pdf_url" class="pdf-badge">
                    PDF Available
                  </div>
                  <div v-else class="no-pdf-badge">No PDF</div>
                  <span class="result-source">
                    <img
                      v-if="getEngineIcon(item.result.source)"
                      :src="getEngineIcon(item.result.source)"
                      :alt="`${item.result.source} icon`"
                      class="result-source-icon"
                    />
                    {{ item.result.source }}
                  </span>
                </div>
                <h4 class="result-title">{{ item.result.title }}</h4>
                <div class="result-meta">
                  <span
                    v-if="item.result.authors.length"
                    class="result-authors"
                  >
                    {{ formatAuthors(item.result.authors) }}
                  </span>
                  <span v-if="item.result.year" class="result-year">
                    {{ item.result.year }}
                  </span>
                  <span v-if="item.result.citations" class="result-citations">
                    {{ item.result.citations }} citations
                  </span>
                </div>
              </div>
            </div>

            <div class="result-links">
              <a
                v-if="item.result.doi"
                :href="`https://doi.org/${item.result.doi}`"
                target="_blank"
                class="result-link"
              >
                DOI <ExternalLink :size="12" />
              </a>
              <a
                v-if="item.result.url"
                :href="item.result.url"
                target="_blank"
                class="result-link"
              >
                Source <ExternalLink :size="12" />
              </a>
              <button
                v-if="item.result.pdf_url"
                class="result-download-btn"
                type="button"
                :disabled="
                  downloadQueueing.has(item.key) ||
                  downloadQueued.has(item.key)
                "
                @click.stop="queueSingleDownload(item.key, item.result, $event)"
              >
                <span v-if="downloadQueueing.has(item.key)">
                  Queueing...
                </span>
                <span v-else-if="downloadQueued.has(item.key)">Queued</span>
                <span v-else-if="downloadErrors[item.key]">Retry</span>
                <span v-else>Download PDF</span>
              </button>
            </div>
            <div
              v-if="downloadErrors[item.key]"
              class="result-download-error"
            >
              {{ downloadErrors[item.key] }}
            </div>

            <div
              v-if="item.result.abstract"
              class="result-abstract"
              :class="{ expanded: expandedAbstracts.has(item.key) }"
            >
              <button class="abstract-toggle" @click="toggleAbstract(item.key)">
                <span v-if="expandedAbstracts.has(item.key)">
                  <ChevronUp :size="14" /> Hide Abstract
                </span>
                <span v-else> <ChevronDown :size="14" /> Show Abstract </span>
              </button>
              <p v-if="expandedAbstracts.has(item.key)" class="abstract-text">
                {{ item.result.abstract }}
              </p>
            </div>
          </div>
        </div>
      </div>

      <div
        v-if="
          !isSearching &&
          hasSearched &&
          searchResults.length === 0 &&
          !searchError
        "
        class="empty-state"
      >
        <div class="empty-title">No results found</div>
        <div class="empty-hint">
          Try broader keywords or select more engines.
        </div>
      </div>
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
  width: 100%;
}

.search-input-row {
  display: flex;
  gap: 12px;
}

.search-input-wrapper {
  flex: 1;
  display: flex;
  align-items: center;
  background: var(--bg-input);
  border: 1px solid var(--border-input);
  border-radius: 8px;
  padding: 0 12px;
}

.search-input-wrapper:focus-within {
  border-color: var(--border-input-focus);
  box-shadow: 0 0 0 2px var(--alpha-accent-10);
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

.search-hint {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 0;
}

.search-btn {
  min-width: 120px;
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

.configure-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 500;
  background: var(--bg-panel);
  color: var(--text-primary);
  border: 1px solid var(--border-card);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s;
}

.configure-btn:hover {
  background: var(--bg-card-hover);
  border-color: var(--accent-bright);
  color: var(--accent-color);
}

.search-options {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
  padding: 16px;
  background: var(--bg-panel);
  border-radius: 8px;
  border: 1px solid var(--border-color);
}

.search-options-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.section-title {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-secondary);
}

.advanced-toggle {
  border: 1px solid var(--border-card);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: 12px;
  padding: 6px 10px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s;
}

.advanced-toggle:hover {
  border-color: var(--accent-bright);
  color: var(--accent-bright);
}

.search-options-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}

.form-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
}

.form-input {
  padding: 8px 10px;
  font-size: 13px;
  border: 1px solid var(--border-input);
  border-radius: 6px;
  background: var(--bg-input);
  color: var(--text-primary);
  outline: none;
  transition: border-color 0.15s;
}

.form-input:focus {
  border-color: var(--border-input-focus);
  box-shadow: 0 0 0 2px var(--alpha-accent-10);
}

.form-input::placeholder {
  color: var(--text-secondary);
}

.advanced-options {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--border-color);
}

.engine-checkboxes {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.engine-empty {
  font-size: 12px;
  color: var(--text-secondary);
  padding: 6px 0;
}

.engine-card {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border: 1px solid var(--border-card);
  border-radius: 6px;
  font-size: 12px;
  color: var(--text-primary);
  cursor: pointer;
  transition: all 0.15s;
  background: var(--bg-card);
}

.engine-card:hover {
  border-color: var(--accent-bright);
}

.engine-card.selected {
  border-color: var(--accent-color);
  background: var(--bg-selected);
}

.engine-icon {
  width: 14px;
  height: 14px;
  border-radius: 3px;
  object-fit: contain;
}

.year-inputs {
  display: flex;
  align-items: center;
  gap: 8px;
}

.year-input {
  width: 90px;
}

.year-separator {
  font-size: 12px;
  color: var(--text-secondary);
}

.deep-crawl-controls {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.toggle-wrapper {
  display: flex;
  align-items: center;
  gap: 10px;
}

.toggle-label-text {
  font-size: 12px;
  color: var(--text-primary);
}

.deep-crawl-input {
  width: 140px;
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
  width: 100%;
}

.results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: var(--bg-panel);
  border-radius: 8px;
  border: 1px solid var(--border-color);
  position: sticky;
  top: 0;
  z-index: 2;
}

.results-info {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.results-sort {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-secondary);
}

.results-sort .custom-select-wrapper {
  min-width: 160px;
}

.resultsCount {
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

.filter-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 6px;
  background: var(--accent-color);
  color: white;
  border-radius: 9px;
  font-size: 11px;
  font-weight: 600;
  margin-left: 4px;
}

.filter-panel {
  padding: 16px;
  background: var(--bg-panel);
  border-radius: 8px;
  border: 1px solid var(--border-color);
}

.filter-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.filter-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}

.results-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-right: 0;
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
  background: var(--bg-selected);
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

.result-badges {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}

.pdf-badge {
  background: var(--color-success-50);
  color: var(--color-success-700);
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 500;
}

.no-pdf-badge {
  background: var(--color-neutral-200);
  color: var(--text-secondary);
  padding: 2.5px 8px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 500;
}

.result-card.clickable {
  cursor: pointer;
}

.result-card.clickable:hover {
  border-color: var(--accent-bright);
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

.result-source-icon {
  width: 12px;
  height: 12px;
  border-radius: 2px;
  object-fit: contain;
}

.result-links {
  display: flex;
  gap: 12px;
  margin-top: 8px;
  flex-wrap: wrap;
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

.result-download-btn {
  padding: 4px 10px;
  font-size: 12px;
  color: var(--text-primary);
  background: var(--bg-panel);
  border: 1px solid var(--border-card);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s;
}

.result-download-btn:hover:not(:disabled) {
  border-color: var(--accent-bright);
  color: var(--accent-color);
}

.result-download-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.result-download-error {
  margin-top: 6px;
  font-size: 12px;
  color: var(--color-danger-700);
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

.empty-state {
  padding: 32px 16px;
  background: var(--bg-panel);
  border: 1px dashed var(--border-color);
  border-radius: 10px;
  text-align: center;
  color: var(--text-secondary);
}

.empty-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 6px;
}

.empty-hint {
  font-size: 12px;
}

@media (max-width: 720px) {
  .search-input-row {
    flex-direction: column;
  }

  .search-btn {
    width: 100%;
  }

  .results-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }

  .results-actions {
    width: 100%;
    flex-wrap: wrap;
    justify-content: flex-start;
  }
}
</style>
