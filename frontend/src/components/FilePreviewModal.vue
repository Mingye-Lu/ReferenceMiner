<script setup lang="ts">
import { computed, ref, watch, nextTick, inject, type Ref } from "vue"
import BaseModal from "./BaseModal.vue"
import PdfViewer from "./PdfViewer.vue"
import type { ManifestEntry, Project, BoundingBox } from "../types"
import { renderAsync } from "docx-preview"
import { getFileUrl } from "../api/client"
import { getFileName } from "../utils"

const props = defineProps<{
  modelValue: boolean
  file: ManifestEntry | null
  highlights?: BoundingBox[]
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
  (event: 'close'): void
}>()

const currentProject = inject<Ref<Project | null> | undefined>("currentProject", undefined)
const projectId = computed(() => currentProject?.value?.id || "default")

const docxContainer = ref<HTMLElement | null>(null)
const isLoading = ref(false)

const fileUrl = computed(() => {
  if (!props.file) return ""
  return getFileUrl(projectId.value, props.file.relPath)
})

const isPdf = computed(() => props.file?.fileType === "pdf")
const isImage = computed(() => ["png", "jpg", "jpeg", "gif", "webp"].includes(props.file?.fileType || ""))
const isDocx = computed(() => ["docx", "doc"].includes(props.file?.fileType || ""))
const usePdfViewer = computed(() => {
  return isPdf.value && props.highlights && props.highlights.length > 0
})
const initialPage = computed(() => {
  if (!props.highlights || props.highlights.length === 0) return undefined
  return props.highlights[0].page
})

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
  emit('update:modelValue', false)
  emit('close')
}
</script>

<template>
  <BaseModal :model-value="modelValue" :title="file ? getFileName(file.relPath) : 'Preview'" size="fullscreen" @update:model-value="handleClose">
    <div class="preview-content">
      <PdfViewer v-if="usePdfViewer" :file-url="fileUrl" :highlights="highlights" :initial-page="initialPage" class="pdf-viewer-wrapper" />
      <iframe v-else-if="isPdf" :src="fileUrl" class="preview-frame"></iframe>
      <img v-else-if="isImage" :src="fileUrl" class="preview-image" />
      <div v-else-if="isDocx" class="docx-preview-area">
        <div v-if="isLoading" class="loading">Loading document...</div>
        <div ref="docxContainer" class="docx-container"></div>
      </div>
      <div v-else class="preview-text">
        <p>Preview not available for this file type ({{ file?.fileType }}).</p>
        <p><a :href="fileUrl" target="_blank">Download File</a></p>
      </div>
    </div>
  </BaseModal>
</template>

<style scoped>
.preview-content {
  height: 100%;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-neutral-85);
}

.preview-frame,
.pdf-viewer-wrapper {
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
  color: var(--color-neutral-700);
}

.docx-preview-area {
  width: 100%;
  height: 100%;
  overflow-y: auto;
  background: var(--color-neutral-240);
  position: relative;
}

.docx-container {
  background: white;
  box-shadow: 0 2px 10px var(--alpha-black-10);
  min-height: 100%;
}

.loading {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-weight: 600;
  color: var(--color-neutral-650);
}

/* docx-preview specific overrides if needed */
:deep(.docx-wrapper) {
  background: var(--color-white);
  padding: 40px !important;
}

:deep(.modal-body) {
  padding: 0;
  overflow: hidden;
}
</style>
