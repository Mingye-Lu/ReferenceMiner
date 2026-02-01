<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from "vue";
import BaseModal from "./BaseModal.vue";
import FilePreviewModal from "./FilePreviewModal.vue";
import CustomSelect from "./CustomSelect.vue";
import { fetchBankManifest, fetchFileStats } from "../api/client";
import type { ManifestEntry, BibliographyAuthor } from "../types";
import { getFileName } from "../utils";
import { Search, X, FileText, Loader2 } from "lucide-vue-next";

const props = defineProps<{
  modelValue: boolean;
  projectId?: string;
  selectedFiles: Set<string>;
}>();

const emit = defineEmits<{
  (e: "update:modelValue", value: boolean): void;
  (e: "confirm", files: string[]): void;
  (e: "close"): void;
}>();

const bankFiles = ref<ManifestEntry[]>([]);
const fileStats = ref<
  Record<string, { usage_count: number; last_used: number }>
>({});
const loading = ref(true);
const searchQuery = ref("");
const localSelected = ref<Set<string>>(new Set());
const showPreview = ref(false);
const previewFile = ref<ManifestEntry | null>(null);

// Phase 2: Filter state
const filters = ref({
  fileTypes: new Set<string>(),
  years: new Set<string>(),
  language: null as string | null,
  inProject: null as boolean | null,
});
const sortBy = ref<"usage" | "name" | "year" | "added">("usage");
const sortOrder = ref<"asc" | "desc">("desc");

const sortOptions = [
  { value: "usage", label: "Usage" },
  { value: "name", label: "Name" },
  { value: "year", label: "Year" },
  { value: "added", label: "Date Added" },
];

// Phase 5: Keyboard navigation state
const focusedIndex = ref(-1);

// Phase 1: Helper functions for metadata display
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

function truncate(str: string | undefined | null, len: number): string {
  if (!str || str.length <= len) return str || "";
  return str.slice(0, len) + "...";
}

// Phase 2: Computed available filters
const availableTypes = computed(() => {
  const types = new Set(bankFiles.value.map((f) => f.fileType));
  return Array.from(types).sort();
});

const availableYears = computed(() => {
  const years = new Set<string>();
  bankFiles.value.forEach((f) => {
    if (f.bibliography?.year) years.add(f.bibliography.year.toString());
  });
  return Array.from(years).sort().reverse().slice(0, 5);
});

const hasActiveFilters = computed(() => {
  return (
    filters.value.fileTypes.size > 0 ||
    filters.value.years.size > 0 ||
    filters.value.language !== null ||
    filters.value.inProject !== null
  );
});

function toggleFilter(filterKey: "fileTypes" | "years", value: string) {
  const filterSet = filters.value[filterKey];
  if (filterSet.has(value)) {
    filterSet.delete(value);
  } else {
    filterSet.add(value);
  }
  filters.value[filterKey] = new Set(filterSet);
}

function clearAllFilters() {
  filters.value.fileTypes.clear();
  filters.value.years.clear();
  filters.value.language = null;
  filters.value.inProject = null;
  filters.value = { ...filters.value };
}

const filteredFiles = computed(() => {
  let files = bankFiles.value;

  // Text search (title, authors, filename)
  if (searchQuery.value.trim()) {
    const query = searchQuery.value.toLowerCase();
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
  if (filters.value.fileTypes.size > 0) {
    files = files.filter((f) => filters.value.fileTypes.has(f.fileType));
  }

  // Year filter
  if (filters.value.years.size > 0) {
    files = files.filter((f) => {
      const year = f.bibliography?.year?.toString();
      return year && filters.value.years.has(year);
    });
  }

  // Language filter
  if (filters.value.language) {
    files = files.filter(
      (f) => f.bibliography?.language === filters.value.language,
    );
  }

  // In-project filter
  if (filters.value.inProject !== null) {
    files = files.filter((f) =>
      filters.value.inProject
        ? props.selectedFiles.has(f.relPath)
        : !props.selectedFiles.has(f.relPath),
    );
  }

  return sortFiles(files);
});

function sortFiles(files: ManifestEntry[]): ManifestEntry[] {
  return [...files].sort((a, b) => {
    const multiplier = sortOrder.value === "asc" ? 1 : -1;

    switch (sortBy.value) {
      case "usage": {
        const usageA = fileStats.value[a.relPath]?.usage_count || 0;
        const usageB = fileStats.value[b.relPath]?.usage_count || 0;
        if (usageA !== usageB) return (usageB - usageA) * multiplier;

        const timeA = fileStats.value[a.relPath]?.last_used || 0;
        const timeB = fileStats.value[b.relPath]?.last_used || 0;
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
        const timeA = fileStats.value[a.relPath]?.last_used || 0;
        const timeB = fileStats.value[b.relPath]?.last_used || 0;
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

function displayName(path: string) {
  return getFileName(path);
}

function toggleSelection(filePath: string) {
  if (localSelected.value.has(filePath)) {
    localSelected.value.delete(filePath);
  } else {
    localSelected.value.add(filePath);
  }

  localSelected.value = new Set(localSelected.value);
}

function selectAll() {
  if (localSelected.value.size === filteredFiles.value.length) {
    localSelected.value.clear();
  } else {
    localSelected.value = new Set(filteredFiles.value.map((f) => f.relPath));
  }
}

function clearSelection() {
  localSelected.value = new Set();
}

// Phase 5: Keyboard navigation
function handleKeydown(e: KeyboardEvent) {
  // Only handle when modal is open
  if (!props.modelValue) return;

  // Don't handle if focused on an input
  const target = e.target as HTMLElement;
  if (
    target.tagName === "INPUT" ||
    target.tagName === "TEXTAREA" ||
    target.tagName === "SELECT"
  ) {
    // Allow slash to focus search even from inputs (except when already in search)
    if (e.key === "/" && !target.classList.contains("search-input")) {
      e.preventDefault();
      document.querySelector<HTMLInputElement>(".search-input")?.focus();
    }
    return;
  }

  const files = filteredFiles.value;

  switch (e.key) {
    case "ArrowDown":
      e.preventDefault();
      focusedIndex.value = Math.min(focusedIndex.value + 1, files.length - 1);
      scrollToFocused();
      break;
    case "ArrowUp":
      e.preventDefault();
      focusedIndex.value = Math.max(focusedIndex.value - 1, 0);
      scrollToFocused();
      break;
    case " ":
      e.preventDefault();
      if (focusedIndex.value >= 0 && focusedIndex.value < files.length) {
        toggleSelection(files[focusedIndex.value].relPath);
      }
      break;
    case "Enter":
      e.preventDefault();
      if (focusedIndex.value >= 0 && focusedIndex.value < files.length) {
        previewFile.value = files[focusedIndex.value];
        showPreview.value = true;
      }
      break;
    case "/":
      e.preventDefault();
      document.querySelector<HTMLInputElement>(".search-input")?.focus();
      break;
    case "Escape":
      if (showPreview.value) {
        showPreview.value = false;
      }
      break;
  }
}

function scrollToFocused() {
  const el = document.querySelector(`[data-index="${focusedIndex.value}"]`);
  el?.scrollIntoView({ block: "nearest" });
}

// Reset focused index when filtered files change
watch(filteredFiles, () => {
  focusedIndex.value = -1;
});

function handlePreview(file: ManifestEntry, e: Event) {
  e.stopPropagation();
  previewFile.value = file;
  showPreview.value = true;
}

function closePreview() {
  showPreview.value = false;
  previewFile.value = null;
}

function handleConfirm() {
  emit("confirm", Array.from(localSelected.value));
  emit("update:modelValue", false);
}

function handleClose() {
  emit("update:modelValue", false);
  emit("close");
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
}

async function loadData() {
  try {
    loading.value = true;
    const [manifest, stats] = await Promise.all([
      fetchBankManifest(),
      fetchFileStats(),
    ]);
    bankFiles.value = manifest;
    fileStats.value = stats;

    // Initialize selection from props
    localSelected.value = new Set(props.selectedFiles);
  } catch (e) {
    console.error("Failed to load bank data", e);
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  loadData();
  document.addEventListener("keydown", handleKeydown);
});

onUnmounted(() => {
  document.removeEventListener("keydown", handleKeydown);
});
</script>

<template>
  <BaseModal
    :model-value="modelValue"
    title="Manage Project Files"
    size="xlarge"
    @update:model-value="handleClose"
    :hide-header="true"
  >
    <!-- Custom Header with Search -->
    <div class="custom-modal-layout">
      <div class="modal-header-custom">
        <h2>Manage Project Files</h2>
        <button class="close-btn-custom" @click="handleClose">
          <X :size="20" />
        </button>
      </div>

      <!-- Search Bar -->
      <div class="search-section">
        <div class="search-input-wrapper">
          <Search :size="16" class="search-icon" />
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Search by title, author, or filename..."
            class="search-input"
          />
        </div>

        <!-- Filter Chips -->
        <div class="filter-chips" v-if="bankFiles.length > 0">
          <!-- File Type Chips -->
          <button
            v-for="type in availableTypes"
            :key="type"
            class="filter-chip"
            :class="{ active: filters.fileTypes.has(type) }"
            @click="toggleFilter('fileTypes', type)"
          >
            {{ type.toUpperCase() }}
          </button>

          <!-- Year Chips -->
          <button
            v-for="year in availableYears"
            :key="year"
            class="filter-chip"
            :class="{ active: filters.years.has(year) }"
            @click="toggleFilter('years', year)"
          >
            {{ year }}
          </button>

          <!-- Language Toggle -->
          <button
            class="filter-chip"
            :class="{ active: filters.language === 'zh' }"
            @click="filters.language = filters.language === 'zh' ? null : 'zh'"
          >
            中文
          </button>

          <!-- In-Project Toggle -->
          <button
            class="filter-chip"
            :class="{ active: filters.inProject === true }"
            @click="
              filters.inProject = filters.inProject === true ? null : true
            "
          >
            In Project
          </button>

          <!-- Clear All Filters -->
          <button
            v-if="hasActiveFilters"
            class="filter-chip clear-filters"
            @click="clearAllFilters"
          >
            <X :size="12" />
            Clear
          </button>
        </div>

        <!-- Sort Controls & Selection Info -->
        <div class="controls-row">
          <div class="sort-controls">
            <span>Sort:</span>
            <CustomSelect
              v-model="sortBy"
              :options="sortOptions"
              class="sort-select"
            />
          </div>
          <div class="selection-info">
            <span>{{ filteredFiles.length }} files</span>
          </div>
        </div>
      </div>

      <!-- File List -->
      <div class="modal-body-custom">
        <div v-if="loading" class="loading-state">
          <Loader2 class="spinner" :size="32" />
          <p>Loading files...</p>
        </div>

        <div v-else-if="filteredFiles.length === 0" class="empty-state">
          <FileText :size="48" class="empty-icon" />
          <p v-if="searchQuery">No files match your search</p>
          <p v-else>No files in Reference Bank</p>
        </div>

        <TransitionGroup
          v-else
          name="file-list"
          tag="div"
          class="file-grid"
          @before-leave="handleBeforeLeave"
        >
          <div
            v-for="(file, index) in filteredFiles"
            :key="file.relPath"
            :data-index="index"
            class="file-card"
            :class="{
              selected: localSelected.has(file.relPath),
              focused: focusedIndex === index,
            }"
            @click="toggleSelection(file.relPath)"
          >
            <div class="file-icon">
              <FileText :size="20" />
            </div>
            <div class="file-info">
              <div class="file-name" :title="displayName(file.relPath)">
                {{ displayName(file.relPath) }}
              </div>
              <div
                class="file-title"
                v-if="file.bibliography?.title"
                :title="file.bibliography.title"
              >
                {{ truncate(file.bibliography.title, 50) }}
              </div>
              <div
                class="file-authors"
                v-if="file.bibliography?.authors || file.bibliography?.year"
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
                  v-if="fileStats[file.relPath]?.usage_count"
                  class="usage-badge"
                >
                  {{ fileStats[file.relPath].usage_count }} project{{
                    fileStats[file.relPath].usage_count > 1 ? "s" : ""
                  }}
                </span>
              </div>
            </div>
            <button
              class="preview-btn"
              @click="(e) => handlePreview(file, e)"
              title="Preview"
            >
              <Search :size="14" />
            </button>
          </div>
        </TransitionGroup>
      </div>

      <!-- Quick Actions Toolbar (Phase 4) -->
      <Transition name="slide-up">
        <div v-if="localSelected.size > 0" class="quick-actions-bar">
          <span class="selection-count">{{ localSelected.size }} selected</span>
          <div class="action-buttons">
            <button @click="selectAll" class="action-btn">
              {{
                localSelected.size === filteredFiles.length
                  ? "Deselect All"
                  : "Select All Visible"
              }}
            </button>
            <button @click="clearSelection" class="action-btn">Clear</button>
          </div>
        </div>
      </Transition>

      <!-- Footer -->
      <div class="modal-footer-custom">
        <button class="btn-secondary" @click="handleClose">Cancel</button>
        <button class="btn-primary" @click="handleConfirm" :disabled="loading">
          <Loader2
            v-if="loading"
            class="spin"
            :size="16"
            style="margin-right: 6px"
          />
          Update
        </button>
      </div>
    </div>

    <!-- Preview Modal -->
    <FilePreviewModal
      v-model="showPreview"
      :file="previewFile"
      @close="closePreview"
    />
  </BaseModal>
</template>

<style scoped>
.custom-modal-layout {
  margin: -24px -20px;
  display: flex;
  flex-direction: column;
  height: calc(85vh - 48px);
}

.modal-header-custom {
  padding: 20px 24px;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}

.modal-header-custom h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

.close-btn-custom {
  background: transparent;
  border: none;
  width: 32px;
  height: 32px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--text-secondary);
  transition: all 0.2s;
}

.close-btn-custom:hover {
  background: var(--bg-icon-hover);
  color: var(--text-primary);
}

.search-section {
  padding: 16px 24px;
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.search-input-wrapper {
  position: relative;
  margin-bottom: 12px;
}

.search-icon {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-secondary);
}

.search-input {
  width: 100%;
  padding: 10px 12px 10px 36px;
  border: 1px solid var(--border-card);
  border-radius: 8px;
  font-size: 14px;
  transition: border-color 0.2s;
}

.search-input:focus {
  outline: none;
  border-color: var(--border-input-focus);
  box-shadow: 0 0 0 3px rgba(var(--accent-color-rgb), 0.1);
}

/* Filter Chips */
.filter-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.filter-chip {
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

.filter-chip:hover {
  background: var(--color-neutral-150);
  border-color: var(--border-card-hover, var(--border-color));
}

.filter-chip.active {
  background: var(--accent-soft, var(--color-accent-50));
  border-color: var(--accent-color);
  color: var(--accent-color);
}

.filter-chip.clear-filters {
  background: var(--color-danger-50);
  border-color: var(--color-danger-200);
  color: var(--color-danger-600);
  display: flex;
  align-items: center;
  gap: 4px;
}

.filter-chip.clear-filters:hover {
  background: var(--color-danger-100);
}

/* Controls Row */
.controls-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
}

.sort-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-secondary);
}

/* Compact sort dropdown */
.sort-select {
  min-width: 110px;
}

.sort-select :deep(.custom-select-trigger) {
  padding: 5px 10px;
  min-width: 110px;
  border-radius: 6px;
}

.sort-select :deep(.custom-select-label) {
  font-size: 12px;
}

.sort-select :deep(.custom-options) {
  min-width: 110px;
}

.sort-select :deep(.custom-option) {
  padding: 8px 10px;
  font-size: 12px;
}

.selection-info {
  display: flex;
  align-items: center;
  font-size: 13px;
  color: var(--text-secondary);
}

.modal-body-custom {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}

.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 300px;
  text-align: center;
  color: var(--text-secondary);
}

.empty-icon {
  color: var(--color-neutral-400);
  margin-bottom: 12px;
}

.spinner {
  animation: spin 1s linear infinite;
  margin-bottom: 12px;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}

.file-grid {
  position: relative;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
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
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
  will-change: transform;
}

.file-card:hover {
  border-color: var(--accent-bright);
  box-shadow: 0 2px 8px var(--alpha-black-08);
}

.file-card.selected {
  background: var(--accent-soft, var(--color-accent-50));
  border-color: var(--accent-color);
}

/* Phase 5: Keyboard focus indicator */
.file-card.focused {
  outline: 2px solid var(--accent-color);
  outline-offset: 2px;
}

.file-icon {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--accent-soft, var(--color-accent-50));
  border-radius: 8px;
  color: var(--accent-color);
}

.file-info {
  flex: 1;
  min-width: 0;
}

.file-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 2px;
}

/* Phase 1: Enhanced metadata display */
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
  font-size: 11px;
  color: var(--text-secondary);
  text-transform: uppercase;
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
}

.preview-btn {
  flex-shrink: 0;
  background: transparent;
  border: none;
  padding: 6px;
  border-radius: 6px;
  cursor: pointer;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  opacity: 0;
  transition: all 0.2s;
}

.file-card:hover .preview-btn {
  opacity: 1;
}

.preview-btn:hover {
  background: var(--alpha-black-05);
  color: var(--text-primary);
}

[data-theme="dark"] .usage-badge {
  background: var(--color-neutral-150);
  color: var(--text-secondary);
}

[data-theme="dark"] .preview-btn:hover {
  background: var(--bg-icon-hover);
  color: var(--text-primary);
}

.modal-footer-custom {
  padding: 16px 24px;
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  flex-shrink: 0;
}

.btn-secondary {
  padding: 10px 20px;
  background: var(--color-neutral-120);
  color: var(--text-primary);
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-secondary:hover {
  background: var(--color-neutral-170);
}

.btn-primary {
  padding: 10px 20px;
  background: var(--accent-color);
  color: var(--color-white);
  border: 1px solid var(--accent-color);
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
  display: flex;
  align-items: center;
  white-space: nowrap;
}

.btn-primary:hover:not(:disabled) {
  opacity: 0.85;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Phase 4: Quick Actions Toolbar */
.quick-actions-bar {
  padding: 12px 24px;
  background: var(--color-neutral-100);
  color: var(--text-primary);
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: 0 -4px 12px var(--alpha-black-08);
  flex-shrink: 0;
  border-top: 1px solid var(--border-color);
}

.selection-count {
  font-weight: 600;
  font-size: 14px;
  color: var(--text-primary);
}

.action-buttons {
  display: flex;
  gap: 8px;
}

.action-btn {
  padding: 6px 12px;
  background: var(--color-neutral-200);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn:hover {
  background: var(--color-neutral-250);
  border-color: var(--border-card-hover);
}

[data-theme="dark"] .quick-actions-bar {
  background: var(--color-neutral-150);
  border-top-color: var(--color-neutral-200);
}

[data-theme="dark"] .action-btn {
  background: var(--color-neutral-200);
  border-color: var(--color-neutral-300);
}

[data-theme="dark"] .action-btn:hover {
  background: var(--color-neutral-250);
  border-color: var(--color-neutral-350);
}

/* Slide-up transition for quick actions bar */
.slide-up-enter-active,
.slide-up-leave-active {
  transition:
    transform 0.2s ease,
    opacity 0.2s ease;
}

.slide-up-enter-from,
.slide-up-leave-to {
  transform: translateY(100%);
  opacity: 0;
}

/* Dark mode adjustments */
[data-theme="dark"] .search-input {
  background: var(--color-neutral-150);
  border-color: var(--color-neutral-200);
  color: var(--text-primary);
}

[data-theme="dark"] .search-input:focus {
  border-color: var(--border-input-focus);
  box-shadow: 0 0 0 3px rgba(var(--accent-color-rgb), 0.15);
}

[data-theme="dark"] .search-input::placeholder {
  color: var(--text-secondary);
}

[data-theme="dark"] .filter-chip {
  background: var(--color-neutral-150);
  border-color: var(--color-neutral-200);
}

[data-theme="dark"] .filter-chip:hover {
  background: var(--color-neutral-200);
}

[data-theme="dark"] .filter-chip.active {
  background: var(--accent-soft);
  border-color: var(--accent-color);
  color: var(--accent-color);
}

[data-theme="dark"] .filter-chip.clear-filters {
  background: var(--color-danger-50);
  border-color: var(--color-danger-200);
  color: var(--color-danger-400);
}

[data-theme="dark"] .filter-chip.clear-filters:hover {
  background: var(--color-danger-100);
}
</style>
