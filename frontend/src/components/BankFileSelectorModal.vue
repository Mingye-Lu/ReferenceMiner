<script setup lang="ts">
import { ref, computed, onMounted } from "vue"
import BaseModal from "./BaseModal.vue"
import FilePreviewModal from "./FilePreviewModal.vue"
import { fetchBankManifest, fetchFileStats } from "../api/client"
import type { ManifestEntry } from "../types"
import { getFileName } from "../utils"
import { Search, X, FileText, Loader2 } from "lucide-vue-next"

const props = defineProps<{
  modelValue: boolean
  projectId?: string
  selectedFiles: Set<string>
}>()

const emit = defineEmits<{
  (e: "update:modelValue", value: boolean): void
  (e: "confirm", files: string[]): void
  (e: "close"): void
}>()

const bankFiles = ref<ManifestEntry[]>([])
const fileStats = ref<Record<string, { usage_count: number; last_used: number }>>({})
const loading = ref(true)
const searchQuery = ref("")
const localSelected = ref<Set<string>>(new Set())
const showPreview = ref(false)
const previewFile = ref<ManifestEntry | null>(null)

const filteredFiles = computed(() => {
  let files = bankFiles.value

  if (searchQuery.value.trim()) {
    const query = searchQuery.value.toLowerCase()
    files = files.filter(f =>
      getFileName(f.relPath).toLowerCase().includes(query) ||
      f.fileType.toLowerCase().includes(query)
    )
  }

  return sortFiles(files)
})

function sortFiles(files: ManifestEntry[]): ManifestEntry[] {
  return [...files].sort((a, b) => {
    const usageA = fileStats.value[a.relPath]?.usage_count || 0
    const usageB = fileStats.value[b.relPath]?.usage_count || 0
    if (usageA !== usageB) return usageB - usageA

    const timeA = fileStats.value[a.relPath]?.last_used || 0
    const timeB = fileStats.value[b.relPath]?.last_used || 0
    if (timeA !== timeB) return timeB - timeA

    if (a.fileType !== b.fileType) {
      return a.fileType.localeCompare(b.fileType)
    }

    return getFileName(a.relPath).localeCompare(getFileName(b.relPath))
  })
}

function displayName(path: string) {
  return getFileName(path)
}

function toggleSelection(filePath: string) {
  if (localSelected.value.has(filePath)) {
    localSelected.value.delete(filePath)
  } else {
    localSelected.value.add(filePath)
  }

  localSelected.value = new Set(localSelected.value)
}

function selectAll() {
  if (localSelected.value.size === filteredFiles.value.length) {
    localSelected.value.clear()
  } else {
    localSelected.value = new Set(filteredFiles.value.map(f => f.relPath))
  }
}

function handlePreview(file: ManifestEntry, e: Event) {
  e.stopPropagation()
  previewFile.value = file
  showPreview.value = true
}

function closePreview() {
  showPreview.value = false
  previewFile.value = null
}

function handleConfirm() {
  emit("confirm", Array.from(localSelected.value))
  emit("update:modelValue", false)
}

function handleClose() {
  emit("update:modelValue", false)
  emit("close")
}

async function loadData() {
  try {
    loading.value = true
    const [manifest, stats] = await Promise.all([
      fetchBankManifest(),
      fetchFileStats()
    ])
    bankFiles.value = manifest
    fileStats.value = stats

    // Initialize selection from props
    localSelected.value = new Set(props.selectedFiles)
  } catch (e) {
    console.error("Failed to load bank data", e)
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<template>
  <BaseModal :model-value="modelValue" title="Manage Project Files" size="xlarge" @update:model-value="handleClose"
    :hide-header="true">
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
          <input v-model="searchQuery" type="text" placeholder="Search files by name or type..." class="search-input" />
        </div>
        <div class="selection-info">
          <span>{{ localSelected.size }} selected</span>
          <button class="link-btn" @click="selectAll">
            {{ localSelected.size === filteredFiles.length ? 'Deselect All' : 'Select All' }}
          </button>
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

        <div v-else class="file-grid">
          <div v-for="file in filteredFiles" :key="file.relPath" class="file-card"
            :class="{ selected: localSelected.has(file.relPath) }" @click="toggleSelection(file.relPath)">
            <div class="file-checkbox">
              <input type="checkbox" :checked="localSelected.has(file.relPath)" readonly />
            </div>
            <div class="file-icon">
              <FileText :size="20" />
            </div>
            <div class="file-info">
              <div class="file-name" :title="displayName(file.relPath)">{{ displayName(file.relPath) }}</div>
              <div class="file-meta">
                {{ file.fileType }} · {{ Math.round((file.sizeBytes || 0) / 1024) }}KB
                <span v-if="fileStats[file.relPath]?.usage_count" class="usage-badge">
                  {{ fileStats[file.relPath].usage_count }} project{{ fileStats[file.relPath].usage_count > 1 ? 's' : ''
                  }}
                </span>
              </div>
            </div>
            <button class="preview-btn" @click="(e) => handlePreview(file, e)" title="Preview">
              <Search :size="14" />
            </button>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="modal-footer-custom">
        <button class="btn-secondary" @click="handleClose">Cancel</button>
        <button class="btn-primary" @click="handleConfirm" :disabled="loading">
          <Loader2 v-if="loading" class="spin" :size="16" style="margin-right:6px" />
          Update
        </button>
      </div>
    </div>

    <!-- Preview Modal -->
    <FilePreviewModal v-model="showPreview" :file="previewFile" @close="closePreview" />
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
  border-color: var(--accent-color);
  box-shadow: 0 0 0 3px var(--accent-soft, var(--color-accent-50));
}

.selection-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  color: var(--text-secondary);
}

.link-btn {
  background: transparent;
  border: none;
  color: var(--accent-color);
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  padding: 4px 8px;
  border-radius: 4px;
  transition: background 0.2s;
}

.link-btn:hover {
  background: var(--accent-soft, var(--color-accent-50));
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
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}

.file-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: var(--color-neutral-60);
  border: 1px solid var(--border-card);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
}

.file-card:hover {
  background: var(--color-neutral-80);
  border-color: var(--accent-soft, var(--color-accent-100));
  box-shadow: 0 2px 8px var(--alpha-black-08);
}

.file-card.selected {
  background: var(--accent-soft, var(--color-accent-50));
  border-color: var(--accent-color);
}

.file-checkbox {
  flex-shrink: 0;
}

.file-checkbox input[type="checkbox"] {
  width: 18px;
  height: 18px;
  cursor: pointer;
  accent-color: var(--accent-color);
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
  margin-bottom: 4px;
}

.file-meta {
  font-size: 11px;
  color: var(--text-secondary);
  text-transform: uppercase;
  display: flex;
  align-items: center;
  gap: 6px;
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

[data-theme="dark"] .file-card {
  background: var(--color-neutral-105);
  border-color: var(--color-neutral-150);
}

[data-theme="dark"] .file-card:hover {
  background: var(--color-neutral-150);
  border-color: var(--border-hover);
  box-shadow: var(--shadow-sm);
}

[data-theme="dark"] .file-card.selected {
  background: var(--accent-soft);
  border-color: var(--accent-color);
}

[data-theme="dark"] .file-icon {
  background: var(--accent-soft);
  color: var(--accent-color);
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
</style>
