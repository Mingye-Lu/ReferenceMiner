<script setup lang="ts">
import { ref } from "vue"
import BaseModal from "./BaseModal.vue"
import { uploadFileStream, uploadFileToBankStream } from "../api/client"
import type { UploadItem, ManifestEntry, UploadProgress } from "../types"

const props = withDefaults(defineProps<{
  projectId?: string
  uploadMode?: 'bank' | 'project'
}>(), {
  uploadMode: 'project'
})

const emit = defineEmits<{
  (e: "upload-complete", entry: ManifestEntry): void
}>()

const isDragOver = ref(false)
const uploads = ref<UploadItem[]>([])
const fileInput = ref<HTMLInputElement | null>(null)
const folderInput = ref<HTMLInputElement | null>(null)
const isOpen = ref(false)
const activeUploads = ref(0)
const MAX_CONCURRENT_UPLOADS = 3

const SUPPORTED_EXTENSIONS = [".pdf", ".docx", ".txt", ".md", ".png", ".jpg", ".jpeg", ".csv", ".xlsx"]

function isSupported(file: File): boolean {
  const ext = "." + file.name.split(".").pop()?.toLowerCase()
  return SUPPORTED_EXTENSIONS.includes(ext)
}

function addFiles(files: FileList | File[]) {
  for (const file of files) {
    if (!isSupported(file)) {
      uploads.value.push({
        id: Date.now().toString() + Math.random(),
        file,
        status: "error",
        progress: 0,
        error: `Unsupported file type: ${file.name.split(".").pop()}`,
      })
      continue
    }

    const item: UploadItem = {
      id: Date.now().toString() + Math.random(),
      file,
      status: "pending",
      progress: 0,
    }
    uploads.value.push(item)
  }

  // Start processing uploads with concurrency control
  processQueue()
}

async function processQueue() {
  // Find pending uploads
  const pending = uploads.value.filter(u => u.status === "pending")

  // Start uploads up to the concurrent limit
  for (const item of pending) {
    if (activeUploads.value >= MAX_CONCURRENT_UPLOADS) {
      break
    }
    processUpload(item)
  }
}

function openModal() {
  isOpen.value = true
}

function closeModal(value: boolean) {
  isOpen.value = value
  if (!value) {
    isDragOver.value = false
  }
}

async function processUpload(item: UploadItem, replace: boolean = false) {
  // Find the item in the array for proper reactivity
  const updateItem = (updates: Partial<UploadItem>) => {
    const idx = uploads.value.findIndex(u => u.id === item.id)
    if (idx !== -1) {
      Object.assign(uploads.value[idx], updates)
    }
  }

  activeUploads.value++
  updateItem({ status: "uploading", progress: 0 })

  try {
    const handlers = {
      onProgress: (progress: UploadProgress) => {
        updateItem({
          status: "processing",
          progress: progress.percent ?? item.progress
        })
      },
      onDuplicate: (_sha256: string, existingPath: string) => {
        updateItem({
          status: "duplicate",
          duplicatePath: existingPath
        })
      },
      onComplete: (result: any) => {
        updateItem({
          status: "complete",
          progress: 100,
          result
        })
        if (result.manifestEntry) {
          emit("upload-complete", result.manifestEntry)
        }
      },
      onError: (_code: string, message: string) => {
        updateItem({
          status: "error",
          error: message
        })
      },
    }

    // Call appropriate upload function based on mode
    const result = props.uploadMode === 'bank'
      ? await uploadFileToBankStream(item.file, handlers, replace)
      : await uploadFileStream(props.projectId!, item.file, handlers, replace)

    const currentItem = uploads.value.find(u => u.id === item.id)
    if (!result && currentItem) {
      if (currentItem.status !== "duplicate" && currentItem.status !== "error") {
        updateItem({ status: "error", error: "Upload failed" })
      }
    }
  } catch (e) {
    updateItem({
      status: "error",
      error: e instanceof Error ? e.message : "Upload failed"
    })
  } finally {
    activeUploads.value--
    // Process next item in queue
    processQueue()
  }
}

function handleDrop(event: DragEvent) {
  isDragOver.value = false
  if (event.dataTransfer?.files) {
    addFiles(event.dataTransfer.files)
  }
}

function handleFileSelect(event: Event) {
  const target = event.target as HTMLInputElement
  if (target.files) {
    addFiles(target.files)
    target.value = "" // Reset for re-selection
  }
}

function handleFolderSelect(event: Event) {
  const target = event.target as HTMLInputElement
  if (target.files) {
    addFiles(target.files)
    target.value = ""
  }
}

function replaceFile(item: UploadItem) {
  const idx = uploads.value.findIndex(u => u.id === item.id)
  if (idx !== -1) {
    uploads.value[idx].status = "pending"
    uploads.value[idx].duplicatePath = undefined
    processUpload(uploads.value[idx], true)
  }
}

function removeItem(item: UploadItem) {
  const idx = uploads.value.findIndex((u) => u.id === item.id)
  if (idx !== -1) uploads.value.splice(idx, 1)
}

function clearCompleted() {
  uploads.value = uploads.value.filter((u) => u.status !== "complete" && u.status !== "error")
}

function getStatusLabel(status: string): string {
  switch (status) {
    case "pending": return "Pending"
    case "uploading": return "Uploading..."
    case "processing": return "Processing..."
    case "complete": return "Complete"
    case "error": return "Error"
    case "duplicate": return "Duplicate"
    default: return status
  }
}
</script>

<template>
  <div class="file-uploader">
    <button class="upload-trigger" @click="openModal">Upload Files</button>

    <BaseModal
      :model-value="isOpen"
      size="large"
      :title="uploadMode === 'bank' ? 'Upload to Reference Bank' : 'Upload to Project'"
      @update:model-value="closeModal"
    >
      <div class="drop-zone" :class="{ dragover: isDragOver, 'has-items': uploads.length > 0 }"
        @dragover.prevent="isDragOver = true" @dragleave="isDragOver = false" @drop.prevent="handleDrop">
        <template v-if="uploads.length === 0">
          <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" x2="12" y1="3" y2="15" />
          </svg>
          <p class="drop-text">Drop files here or click to browse</p>
          <p class="drop-hint">PDF, DOCX, TXT, MD, Images (PNG, JPG). Folder upload supported.</p>
          <input type="file" multiple :accept="SUPPORTED_EXTENSIONS.join(',')" @change="handleFileSelect"
            ref="fileInput" class="hidden-input" />
          <input type="file" webkitdirectory directory @change="handleFolderSelect" ref="folderInput"
            class="hidden-input" />
          <div class="upload-actions">
            <button class="btn-secondary" @click="fileInput?.click()">Select Files</button>
            <button class="btn-secondary" @click="folderInput?.click()">Select Folder</button>
          </div>
        </template>

        <template v-else>
          <div class="upload-queue">
            <div v-for="item in uploads" :key="item.id" class="upload-item" :class="item.status">
              <div class="item-info">
                <span class="filename">{{ item.file.name }}</span>
                <span class="status-badge" :class="item.status">{{ getStatusLabel(item.status) }}</span>
                <button v-if="item.status === 'complete'" class="btn-icon" @click="removeItem(item)">
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
                    stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </button>
              </div>

              <div v-if="item.status === 'uploading' || item.status === 'processing'" class="progress-bar">
                <div class="progress-fill" :style="{ width: item.progress + '%' }"></div>
              </div>

              <div v-if="item.status === 'duplicate'" class="duplicate-info">
                <span class="duplicate-text">Same as: {{ item.duplicatePath }}</span>
                <button class="btn-small" @click="replaceFile(item)">Replace</button>
                <button class="btn-small btn-ghost" @click="removeItem(item)">Skip</button>
              </div>

              <div v-if="item.status === 'error'" class="error-info">
                <span class="error-text">{{ item.error }}</span>
                <button class="btn-small btn-ghost" @click="removeItem(item)">Dismiss</button>
              </div>
            </div>
          </div>

          <div class="upload-actions">
            <button class="btn-secondary" @click="fileInput?.click()">Add More</button>
            <button class="btn-secondary" @click="folderInput?.click()">Add Folder</button>
            <button v-if="uploads.some(u => u.status === 'complete' || u.status === 'error')"
              class="btn-secondary" @click="clearCompleted">Clear Done</button>
          </div>
          <input type="file" multiple :accept="SUPPORTED_EXTENSIONS.join(',')" @change="handleFileSelect"
            ref="fileInput" class="hidden-input" />
          <input type="file" webkitdirectory directory @change="handleFolderSelect" ref="folderInput"
            class="hidden-input" />
        </template>
      </div>
    </BaseModal>
  </div>
</template>

<style scoped>
.file-uploader {
  margin-bottom: 16px;
}

.upload-trigger {
  width: 100%;
  padding: 10px 12px;
  background: var(--color-neutral-950);
  color: var(--color-white);
  border: none;
  border-radius: 10px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
}

.upload-trigger:hover {
  opacity: 0.9;
}

.drop-zone {
  border: 2px dashed var(--border-color);
  border-radius: 12px;
  padding: 16px;
  text-align: center;
  transition: all 0.2s;
  background: var(--color-neutral-80);
  margin: -24px -20px;
  padding: 40px 20px;
}

.drop-zone.dragover {
  border-color: var(--accent-color);
  background: var(--color-neutral-140);
}

.drop-zone.has-items {
  padding: 20px;
  text-align: left;
}

.drop-zone svg {
  color: var(--color-neutral-500);
  margin-bottom: 8px;
}

.drop-text {
  font-size: 13px;
  color: var(--text-primary);
  margin: 0 0 4px 0;
}

.drop-hint {
  font-size: 11px;
  color: var(--text-secondary);
  margin: 0 0 12px 0;
}

.hidden-input {
  display: none;
}

.btn-secondary {
  padding: 8px 16px;
  font-size: 12px;
  background: var(--color-white);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s;
}

.btn-secondary:hover {
  background: var(--color-neutral-130);
  border-color: var(--color-neutral-400);
}

.btn-small {
  padding: 4px 10px;
  font-size: 11px;
  background: var(--accent-color);
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.btn-small:hover {
  opacity: 0.9;
}

.btn-ghost {
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
}

.btn-ghost:hover {
  background: var(--color-neutral-130);
}

.btn-icon {
  background: transparent;
  border: none;
  padding: 4px;
  cursor: pointer;
  color: var(--text-secondary);
  border-radius: 4px;
}

.btn-icon:hover {
  background: var(--color-neutral-220);
}

.upload-queue {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 300px;
  overflow-y: auto;
  margin-bottom: 16px;
}

.upload-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 12px;
  background: var(--color-white);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  position: relative;
}

.upload-item.complete {
  border-color: var(--color-success-600);
  background: var(--color-success-25);
}

.upload-item.error {
  border-color: var(--color-danger-400);
  background: var(--color-danger-20);
}

.upload-item.duplicate {
  border-color: var(--color-warning-600);
  background: var(--color-warning-50);
}

.item-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.filename {
  font-size: 12px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.status-badge {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 99px;
  background: var(--color-neutral-215);
  color: var(--color-neutral-650);
  flex-shrink: 0;
}

.status-badge.complete {
  background: var(--color-success-50);
  color: var(--color-success-700);
}

.status-badge.error {
  background: var(--color-danger-50);
  color: var(--color-danger-800);
}

.status-badge.duplicate {
  background: var(--color-warning-100);
  color: var(--color-warning-800);
}

.status-badge.uploading,
.status-badge.processing {
  background: var(--color-info-90);
  color: var(--color-info-800);
}

.progress-bar {
  height: 4px;
  background: var(--color-neutral-240);
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--accent-color);
  transition: width 0.2s;
}

.duplicate-info,
.error-info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
}

.duplicate-text {
  color: var(--color-warning-800);
  flex: 1;
}

.error-text {
  color: var(--color-danger-800);
  flex: 1;
}

.upload-actions {
  display: flex;
  gap: 8px;
  justify-content: center;
}
</style>
