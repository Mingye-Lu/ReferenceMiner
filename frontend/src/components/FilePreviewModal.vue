<script setup lang="ts">
import { computed, ref, watch, nextTick, inject, type Ref } from "vue";
import BaseModal from "./BaseModal.vue";
import FileMetadataModal from "./FileMetadataModal.vue";
import PdfPreview from "./PdfPreview.vue";
import type { ManifestEntry, Project, HighlightGroup } from "../types";
import { renderAsync } from "docx-preview";
import { getFileUrl, fetchFileHighlights } from "../api/client";
import { getFileName } from "../utils";
import { Maximize2, Minimize2 } from "lucide-vue-next";

const props = defineProps<{
  modelValue: boolean;
  file: ManifestEntry | null;
  highlightGroups?: HighlightGroup[];
}>();

const emit = defineEmits<{
  (event: "update:modelValue", value: boolean): void;
  (event: "close"): void;
}>();

const currentProject = inject<Ref<Project | null> | undefined>(
  "currentProject",
  undefined,
);
const projectId = computed(() => currentProject?.value?.id || "default");

const docxContainer = ref<HTMLElement | null>(null);
const isLoading = ref(false);
const allChunkGroups = ref<HighlightGroup[] | null>(null);
const isFullscreen = ref(true);
const showMetadataModal = ref(false);

// Cache for DOCX content to prevent re-rendering flicker
// LRU cache with max 5 files to prevent memory bloat
const MAX_DOCX_CACHE_SIZE = 5;
const docxContentCache = new Map<string, string>();

const fileUrl = computed(() => {
  if (!props.file) return "";
  return getFileUrl(projectId.value, props.file.relPath);
});

const isPdf = computed(() => props.file?.fileType === "pdf");
const isImage = computed(() =>
  ["png", "jpg", "jpeg", "gif", "webp"].includes(props.file?.fileType || ""),
);
const isDocx = computed(() =>
  ["docx", "doc"].includes(props.file?.fileType || ""),
);

const activeHighlightGroups = computed(() => {
  if (allChunkGroups.value && allChunkGroups.value.length > 0)
    return allChunkGroups.value;
  return props.highlightGroups;
});

async function loadDocx() {
  if (!isDocx.value || !fileUrl.value || !props.file) return;

  const filePath = props.file.relPath;

  // Check if content is already cached
  if (docxContentCache.has(filePath)) {
    if (docxContainer.value) {
      const cachedContent = docxContentCache.get(filePath)!;
      // Move to end (most recently used) by deleting and re-adding
      docxContentCache.delete(filePath);
      docxContentCache.set(filePath, cachedContent);
      docxContainer.value.innerHTML = cachedContent;
    }
    return;
  }

  isLoading.value = true;
  try {
    const resp = await fetch(fileUrl.value);
    if (!resp.ok) throw new Error("Failed to load file");
    const blob = await resp.blob();
    if (docxContainer.value) {
      docxContainer.value.innerHTML = ""; // Clear previous
      await renderAsync(blob, docxContainer.value, docxContainer.value, {
        className: "docx-wrapper",
        inWrapper: true,
      });

      // LRU cache management: remove oldest entry if cache is full
      if (docxContentCache.size >= MAX_DOCX_CACHE_SIZE) {
        const firstKey = docxContentCache.keys().next().value;
        if (firstKey) {
          docxContentCache.delete(firstKey);
        }
      }

      // Cache the rendered content
      docxContentCache.set(filePath, docxContainer.value.innerHTML);
    }
  } catch (e) {
    console.error("DOCX preview failed", e);
    if (docxContainer.value)
      docxContainer.value.innerHTML =
        "<div class='error'>Failed to load document preview.</div>";
  } finally {
    isLoading.value = false;
  }
}

async function loadHighlights() {
  if (!props.file || !isPdf.value) {
    allChunkGroups.value = null;
    return;
  }
  try {
    allChunkGroups.value = await fetchFileHighlights(props.file.relPath);
  } catch (e) {
    allChunkGroups.value = null;
  }
}

// Watch for file changes - only reload when file path actually changes
watch(
  () => props.file,
  (newFile, oldFile) => {
    // Only reload if the file path changed (different file selected)
    if (newFile?.relPath !== oldFile?.relPath) {
      allChunkGroups.value = null;
      if (isDocx.value) {
        nextTick(() => loadDocx());
      }
      loadHighlights();
    }
  },
  { immediate: true },
);

// Watch for modal open state - ensure content is loaded when modal opens
watch(
  () => props.modelValue,
  (isOpen) => {
    if (isOpen && props.file) {
      // For DOCX: load from cache or fetch if needed
      if (isDocx.value) {
        nextTick(() => {
          if (docxContainer.value) {
            // Always try to load (will use cache if available)
            loadDocx();
          }
        });
      }
      // For PDF: reload highlights if not loaded
      if (isPdf.value && allChunkGroups.value === null) {
        loadHighlights();
      }
    }
  },
);

function handleClose() {
  emit("update:modelValue", false);
  emit("close");
}
</script>

<template>
  <BaseModal
    :model-value="modelValue"
    :title="file ? getFileName(file.relPath) : 'Preview'"
    :size="isFullscreen ? 'fullscreen' : 'xlarge'"
    :fill-body="true"
    @update:model-value="handleClose"
  >
    <template #header-content>
      <div class="preview-header">
        <h3 class="preview-title">
          {{ file ? getFileName(file.relPath) : "Preview" }}
        </h3>
        <button
          class="preview-meta"
          @click="showMetadataModal = true"
          :disabled="!file"
          title="Edit metadata"
        >
          Metadata
        </button>
        <button
          class="preview-toggle"
          @click="isFullscreen = !isFullscreen"
          :title="isFullscreen ? 'Exit full screen' : 'Full screen'"
        >
          <Minimize2 v-if="isFullscreen" :size="16" />
          <Maximize2 v-else :size="16" />
        </button>
      </div>
    </template>
    <div class="preview-content">
      <PdfPreview
        v-if="isPdf"
        :key="`pdf-${file?.relPath}`"
        :file-url="fileUrl"
        :highlight-groups="activeHighlightGroups"
        class="pdf-viewer-wrapper"
      />
      <img
        v-else-if="isImage"
        :key="`img-${file?.relPath}`"
        :src="fileUrl"
        class="preview-image"
      />
      <div v-else-if="isDocx" class="docx-preview-area">
        <div v-if="isLoading" class="loading">Loading document...</div>
        <div ref="docxContainer" class="docx-container"></div>
      </div>
      <div v-else class="preview-text">
        <p>Preview not available for this file type ({{ file?.fileType }}).</p>
        <p><a :href="fileUrl" target="_blank">Download File</a></p>
      </div>
    </div>
    <FileMetadataModal v-model="showMetadataModal" :file="file" />
  </BaseModal>
</template>

<style scoped>
.preview-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.preview-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.preview-toggle {
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  color: var(--text-primary);
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.15s;
}

.preview-toggle:hover {
  background: var(--bg-card-hover);
  border-color: var(--accent-bright);
}

.preview-meta {
  margin-left: auto;
  background: var(--color-neutral-120);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  padding: 6px 10px;
  border-radius: 8px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}

.preview-meta:hover {
  border-color: var(--accent-bright);
  color: var(--accent-bright);
}

.preview-meta:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.preview-content {
  flex: 1;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  justify-content: stretch;
  background: var(--color-neutral-85);
  min-height: 0;
  overflow: hidden;
}

.pdf-viewer-wrapper {
  padding: 12px;
  width: 100%;
  flex: 1;
  border: none;
  min-height: 0;
  overflow: hidden;
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

.download-link {
  color: var(--accent-bright);
  text-decoration: none;
  font-weight: 600;
  padding: 8px 16px;
  border: 1px solid var(--accent-bright);
  border-radius: 8px;
  display: inline-block;
  transition: all 0.2s;
}

.download-link:hover {
  background: var(--accent-bright);
  color: var(--color-white);
}

.docx-preview-area {
  width: 100%;
  flex: 1;
  overflow-y: auto;
  background: var(--color-neutral-240);
  position: relative;
  min-height: 0;
}

.docx-container {
  background: var(--bg-panel);
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
</style>
