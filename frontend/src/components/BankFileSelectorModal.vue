<script setup lang="ts">
import { ref, computed, onMounted } from "vue"
import { fetchBankManifest, fetchFileStats } from "../api/client"
import type { ManifestEntry } from "../types"
import FilePreviewModal from "./FilePreviewModal.vue"
import { Search, X, FileText, Loader2 } from "lucide-vue-next"

const props = defineProps<{
  projectId?: string
  selectedFiles: Set<string>
}>()

const emit = defineEmits<{
  (e: "confirm", files: string[]): void
  (e: "close"): void
}>()

const bankFiles = ref<ManifestEntry[]>([])
const fileStats = ref<Record<string, { usage_count: number; last_used: number }>>({})
const loading = ref(true)
const searchQuery = ref("")
const localSelected = ref<Set<string>>(new Set())
const previewFile = ref<ManifestEntry | null>(null)


const filteredFiles = computed(() => {
  let files = bankFiles.value


  if (searchQuery.value.trim()) {
    const query = searchQuery.value.toLowerCase()
    files = files.filter(f =>
      f.relPath.toLowerCase().includes(query) ||
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


    return a.relPath.localeCompare(b.relPath)
  })
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
}

function closePreview() {
  previewFile.value = null
}

function handleConfirm() {
  emit("confirm", Array.from(localSelected.value))
}

function handleClose() {
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
  <div class="modal-backdrop" @click.self="handleClose">
    <div class="modal-container">
      <!-- Header -->
      <div class="modal-header">
        <h2>Manage Project Files</h2>
        <button class="close-btn" @click="handleClose">
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
      <div class="modal-body">
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
              <div class="file-name" :title="file.relPath">{{ file.relPath }}</div>
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
      <div class="modal-footer">
        <button class="btn-secondary" @click="handleClose">Cancel</button>
        <button class="btn-primary" @click="handleConfirm" :disabled="loading">
          <Loader2 v-if="loading" class="spin" :size="16" style="margin-right:6px" />
          Update
        </button>
      </div>

      <!-- Preview Modal -->
      <FilePreviewModal v-if="previewFile" :file="previewFile" @close="closePreview" />
    </div>
  </div>
</template>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  z-index: 1100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.modal-container {
  background: white;
  border-radius: 16px;
  width: 90%;
  max-width: 900px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.modal-header {
  padding: 20px 24px;
  border-bottom: 1px solid #e0e0e0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.modal-header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

.close-btn {
  background: transparent;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  transition: all 0.2s;
}

.close-btn:hover {
  background: #f0f0f0;
  color: var(--text-primary);
}

.search-section {
  padding: 16px 24px;
  border-bottom: 1px solid #e0e0e0;
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
  border: 1px solid #ddd;
  border-radius: 8px;
  font-size: 14px;
  transition: border-color 0.2s;
}

.search-input:focus {
  outline: none;
  border-color: var(--accent-color);
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
  background: rgba(var(--accent-color-rgb), 0.1);
}

.modal-body {
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
  color: #ccc;
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
  background: #fafafa;
  border: 2px solid transparent;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
}

.file-card:hover {
  background: white;
  border-color: #e0e0e0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.file-card.selected {
  background: #e3f2fd;
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
  background: white;
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
  background: #fff3e0;
  color: #e65100;
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
  background: rgba(0, 0, 0, 0.05);
  color: var(--text-primary);
}

.modal-footer {
  padding: 16px 24px;
  border-top: 1px solid #e0e0e0;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.btn-secondary {
  padding: 10px 20px;
  background: #f1f3f9;
  color: var(--text-primary);
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-secondary:hover {
  background: #e0e3e9;
}

.btn-primary {
  padding: 10px 20px;
  background: var(--accent-color);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
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
</style>
