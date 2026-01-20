<script setup lang="ts">
import { computed, ref, watch, nextTick, inject, type Ref } from "vue"
import BaseModal from "./BaseModal.vue"
import PdfPreview from "./PdfPreview.vue"
import type { ManifestEntry, Project, HighlightGroup } from "../types"
import { renderAsync } from "docx-preview"
import { getFileUrl, fetchFileHighlights } from "../api/client"
import { getFileName } from "../utils"

const props = defineProps<{
  modelValue: boolean
  file: ManifestEntry | null
  highlightGroups?: HighlightGroup[]
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
  (event: 'close'): void
}>()

const currentProject = inject<Ref<Project | null> | undefined>("currentProject", undefined)
const projectId = computed(() => currentProject?.value?.id || "default")

const docxContainer = ref<HTMLElement | null>(null)
const isLoading = ref(false)
const allChunkGroups = ref<HighlightGroup[] | null>(null)

const fileUrl = computed(() => {
  if (!props.file) return ""
  return getFileUrl(projectId.value, props.file.relPath)
})

const isPdf = computed(() => props.file?.fileType === "pdf")
const isImage = computed(() => ["png", "jpg", "jpeg", "gif", "webp"].includes(props.file?.fileType || ""))
const isDocx = computed(() => ["docx", "doc"].includes(props.file?.fileType || ""))

const activeHighlightGroups = computed(() => {
  if (allChunkGroups.value && allChunkGroups.value.length > 0) return allChunkGroups.value
  return props.highlightGroups
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

async function loadHighlights() {
  if (!props.file || !isPdf.value) {
    allChunkGroups.value = null
    return
  }
  try {
    allChunkGroups.value = await fetchFileHighlights(props.file.relPath)
  } catch (e) {
    allChunkGroups.value = null
  }
}

watch(() => props.file, () => {
  if (isDocx.value) {
    nextTick(() => loadDocx())
  }
  loadHighlights()
}, { immediate: true })

function handleClose() {
  emit('update:modelValue', false)
  emit('close')
}
</script>

<template>
  <BaseModal :model-value="modelValue" :title="file ? getFileName(file.relPath) : 'Preview'" size="fullscreen" @update:model-value="handleClose">
    <div class="preview-content">
      <PdfPreview
        v-if="isPdf"
        :file-url="fileUrl"
        :highlight-groups="activeHighlightGroups"
        class="pdf-viewer-wrapper"
      />
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
  flex-direction: column;
  align-items: stretch;
  justify-content: stretch;
  background: var(--color-neutral-85);
}

.pdf-viewer-wrapper {
  width: 100%;
  flex: 1;
  border: none;
}

.preview-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  align-self: center;
}

.preview-text {
  text-align: center;
  color: var(--color-neutral-700);
  align-self: center;
  margin-top: auto;
  margin-bottom: auto;
}

.docx-preview-area {
  width: 100%;
  height: 100%;
  overflow-y: auto;
  background: var(--color-neutral-240);
  position: relative;
  flex: 1;
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
