<script setup lang="ts">
import { computed, ref, watch, nextTick, inject, type Ref } from "vue"
import type { ManifestEntry, Project } from "../types"
import { renderAsync } from "docx-preview"
import { getFileUrl } from "../api/client"

const props = defineProps<{ file: ManifestEntry | null }>()
const emit = defineEmits<{ (event: 'close'): void }>()

const currentProject = inject<Ref<Project | null>>("currentProject")!
const projectId = computed(() => currentProject.value?.id || "default")

const docxContainer = ref<HTMLElement | null>(null)
const isLoading = ref(false)

const fileUrl = computed(() => {
  if (!props.file) return ""
  return getFileUrl(projectId.value, props.file.relPath)
})

const isPdf = computed(() => props.file?.fileType === "pdf")
const isImage = computed(() => ["png", "jpg", "jpeg", "gif", "webp"].includes(props.file?.fileType || ""))
const isDocx = computed(() => ["docx", "doc"].includes(props.file?.fileType || ""))

async function loadDocx() {
  if (!isDocx.value || !fileUrl.value) return
  isLoading.value = true
  try {
    const resp = await fetch(fileUrl.value)
    if (!resp.ok) throw new Error("Failed to load file")
    const blob = await resp.blob()
    if (docxContainer.value) {
      docxContainer.value.innerHTML = "" // Clear previous
      await renderAsync(blob, docxContainer.value, docxContainer.value, {
        className: "docx-wrapper",
        inWrapper: true
      })
    }
  } catch (e) {
    console.error("DOCX preview failed", e)
    if (docxContainer.value) docxContainer.value.innerHTML = "<div class='error'>Failed to load document preview.</div>"
  } finally {
    isLoading.value = false
  }
}

watch(() => props.file, () => {
  if (isDocx.value) {
    nextTick(() => loadDocx())
  }
}, { immediate: true })

function handleClose() {
  emit('close')
}
</script>

<template>
  <div v-if="file" class="modal-backdrop" @click.self="handleClose">
    <div class="modal-content">
      <header class="modal-header">
        <div class="modal-title">{{ file.relPath }}</div>
        <button class="close-btn" @click="handleClose">×</button>
      </header>
      <div class="modal-body">
        <iframe v-if="isPdf" :src="fileUrl" class="preview-frame"></iframe>
        <img v-else-if="isImage" :src="fileUrl" class="preview-image" />
        <div v-else-if="isDocx" class="docx-preview-area">
          <div v-if="isLoading" class="loading">Loading document...</div>
          <div ref="docxContainer" class="docx-container"></div>
        </div>
        <div v-else class="preview-text">
          <p>Preview not available for this file type ({{ file.fileType }}).</p>
          <p><a :href="fileUrl" target="_blank">Download File</a></p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-backdrop {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(4px);
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-content {
  width: 90%;
  height: 90%;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.2);
  display: flex;
  flex-direction: column;
  max-width: 1200px;
}

.modal-header {
  padding: 16px;
  border-bottom: 1px solid #eee;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.modal-title {
  font-weight: 600;
  font-size: 16px;
}

.close-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 24px;
  color: #888;
}

.modal-body {
  flex: 1;
  overflow: hidden;
  background: #f9f9f9;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-frame {
  width: 100%;
  height: 100%;
  border: none;
}

.preview-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.preview-text {
  text-align: center;
  color: #555;
}

.docx-preview-area {
  width: 100%;
  height: 100%;
  overflow-y: auto;
  background: #e0e0e0;
}

.docx-container {
  background: white;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
  min-height: 100%;
}

.loading {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-weight: 600;
  color: #666;
}

/* docx-preview specific overrides if needed */
:deep(.docx-wrapper) {
  background: #ffffff;
  padding: 40px !important;
}
</style>
