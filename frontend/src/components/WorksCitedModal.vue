<script setup lang="ts">
import { ref, computed, watch, inject, type Ref } from "vue";
import BaseModal from "./BaseModal.vue";
import ConfirmExtractMetadataModal from "./ConfirmExtractMetadataModal.vue";
import CustomSelect from "./CustomSelect.vue";
import type { ManifestEntry } from "../types";
import {
  formatCitation,
  hasCitationData,
  type CitationStyle,
} from "../utils/citations";
import { extractFileMetadata } from "../api/client";
import { getFileName } from "../utils";
import { X, FileText, Copy, Download, Check } from "lucide-vue-next";

const props = defineProps<{
  modelValue: boolean;
  files: ManifestEntry[];
}>();

const emit = defineEmits<{
  (e: "update:modelValue", value: boolean): void;
}>();

const manifest = inject<Ref<ManifestEntry[]>>("manifest", ref([]));

const citationStyle = ref<CitationStyle>("apa");
const copiedId = ref<string | null>(null);
const copiedAll = ref(false);
const showMetadataConfirm = ref(false);
const pendingAction = ref<"copy-all" | "download-txt" | "download-bib" | null>(
  null,
);
const isExtractingMetadata = ref(false);

// Filter files that have citation data
const citableFiles = computed(() => {
  return props.files.filter((f) => hasCitationData(f.bibliography));
});

const missingFiles = computed(() => {
  return props.files.filter((f) => !hasCitationData(f.bibliography));
});

const missingPaths = computed(() =>
  missingFiles.value.map((file) => file.relPath),
);

// Generate citations for all citable files
const citations = computed(() => {
  return citableFiles.value.map((file) => ({
    relPath: file.relPath,
    fileName: getFileName(file.relPath),
    citation: formatCitation(
      file.bibliography!,
      citationStyle.value,
      file.relPath,
    ),
  }));
});

const styleOptions = [
  { value: "apa", label: "APA 7th" },
  { value: "mla", label: "MLA 9th" },
  { value: "chicago", label: "Chicago 17th" },
  { value: "gbt7714", label: "GB/T 7714-2015" },
  { value: "bibtex", label: "BibTeX" },
];

function handleClose() {
  emit("update:modelValue", false);
}

async function copySingleCitation(citation: string, relPath: string) {
  try {
    await navigator.clipboard.writeText(citation);
    copiedId.value = relPath;
    setTimeout(() => {
      copiedId.value = null;
    }, 2000);
  } catch (err) {
    console.error("Failed to copy citation:", err);
  }
}

async function copyAllCitations() {
  try {
    const allCitations = citations.value.map((c) => c.citation).join("\n\n");
    await navigator.clipboard.writeText(allCitations);
    copiedAll.value = true;
    setTimeout(() => {
      copiedAll.value = false;
    }, 2000);
  } catch (err) {
    console.error("Failed to copy citations:", err);
  }
}

function extractMissingMetadata() {
  const paths = missingPaths.value;
  if (paths.length === 0 || isExtractingMetadata.value) return;
  isExtractingMetadata.value = true;
  (async () => {
    try {
      const updateMap = new Map<string, ManifestEntry["bibliography"]>();
      for (const path of paths) {
        const updated = await extractFileMetadata(path);
        updateMap.set(path, updated);
      }
      if (manifest.value.length > 0) {
        manifest.value = manifest.value.map((entry) => {
          const next = updateMap.get(entry.relPath);
          return next ? { ...entry, bibliography: next } : entry;
        });
      }
    } catch (err) {
      console.error("Failed to extract metadata:", err);
    } finally {
      isExtractingMetadata.value = false;
    }
  })();
}

async function requestCopyAll() {
  if (missingFiles.value.length > 0 && !isExtractingMetadata.value) {
    pendingAction.value = "copy-all";
    showMetadataConfirm.value = true;
    return;
  }
  await copyAllCitations();
}

async function requestDownloadTxt() {
  if (missingFiles.value.length > 0 && !isExtractingMetadata.value) {
    pendingAction.value = "download-txt";
    showMetadataConfirm.value = true;
    return;
  }
  downloadAsTxt();
}

async function requestDownloadBib() {
  if (missingFiles.value.length > 0 && !isExtractingMetadata.value) {
    pendingAction.value = "download-bib";
    showMetadataConfirm.value = true;
    return;
  }
  downloadAsBib();
}

async function handleExtractConfirm() {
  showMetadataConfirm.value = false;
  extractMissingMetadata();
  const action = pendingAction.value;
  pendingAction.value = null;
  if (action === "copy-all") {
    await copyAllCitations();
  } else if (action === "download-txt") {
    downloadAsTxt();
  } else if (action === "download-bib") {
    downloadAsBib();
  }
}

async function handleExtractSkip() {
  showMetadataConfirm.value = false;
  const action = pendingAction.value;
  pendingAction.value = null;
  if (action === "copy-all") {
    await copyAllCitations();
  } else if (action === "download-txt") {
    downloadAsTxt();
  } else if (action === "download-bib") {
    downloadAsBib();
  }
}

function handleExtractCancel() {
  showMetadataConfirm.value = false;
  pendingAction.value = null;
}

function downloadAsTxt() {
  const allCitations = citations.value.map((c) => c.citation).join("\n\n");
  const blob = new Blob([allCitations], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `works-cited-${citationStyle.value}.txt`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function downloadAsBib() {
  // Generate BibTeX entries for all files
  const bibEntries = citableFiles.value
    .map((file) => formatCitation(file.bibliography!, "bibtex", file.relPath))
    .join("\n\n");
  const blob = new Blob([bibEntries], {
    type: "application/x-bibtex;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "references.bib";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// Reset copied states when modal closes
watch(
  () => props.modelValue,
  (isOpen) => {
    if (!isOpen) {
      copiedId.value = null;
      copiedAll.value = false;
    }
  },
);

// Format markdown-style italics to HTML
function formatHtml(text: string): string {
  // Convert *text* to <em>text</em>
  return text.replace(/\*([^*]+)\*/g, "<em>$1</em>");
}
</script>

<template>
  <BaseModal
    :model-value="modelValue"
    title="Works Cited"
    size="large"
    @update:model-value="handleClose"
    :hide-header="true"
  >
    <div class="custom-modal-layout">
      <!-- Header -->
      <div class="modal-header-custom">
        <h2>Works Cited</h2>
        <button class="close-btn-custom" @click="handleClose">
          <X :size="20" />
        </button>
      </div>

      <!-- Toolbar -->
      <div class="toolbar-section">
        <div class="style-selector">
          <label>Style:</label>
          <CustomSelect v-model="citationStyle" :options="styleOptions" />
        </div>
        <div class="toolbar-actions">
          <button
            class="toolbar-btn"
            @click="requestCopyAll"
            :disabled="citations.length === 0 && missingFiles.length === 0"
          >
            <Check v-if="copiedAll" :size="14" class="check-icon" />
            <Copy v-else :size="14" />
            {{ copiedAll ? "Copied!" : "Copy All" }}
          </button>
          <button
            class="toolbar-btn"
            @click="requestDownloadTxt"
            :disabled="citations.length === 0 && missingFiles.length === 0"
          >
            <Download :size="14" />
            .txt
          </button>
          <button
            class="toolbar-btn"
            @click="requestDownloadBib"
            :disabled="citations.length === 0 && missingFiles.length === 0"
          >
            <Download :size="14" />
            .bib
          </button>
        </div>
      </div>

      <!-- Citations List -->
      <div class="modal-body-custom">
        <div v-if="citableFiles.length === 0" class="empty-state">
          <FileText :size="48" class="empty-icon" />
          <p>No citation metadata available</p>
          <p class="empty-hint">
            Add documents with bibliographic information to generate citations.
          </p>
        </div>

        <div v-else class="citations-list">
          <div
            v-for="item in citations"
            :key="item.relPath"
            class="citation-card"
          >
            <div
              class="citation-text"
              :class="{ 'bibtex-format': citationStyle === 'bibtex' }"
            >
              <template v-if="citationStyle === 'bibtex'">
                <pre>{{ item.citation }}</pre>
              </template>
              <template v-else>
                <span v-html="formatHtml(item.citation)"></span>
              </template>
            </div>
            <div class="citation-footer">
              <button
                class="copy-btn"
                @click="copySingleCitation(item.citation, item.relPath)"
                :class="{ copied: copiedId === item.relPath }"
              >
                <Check v-if="copiedId === item.relPath" :size="12" />
                <Copy v-else :size="12" />
                {{ copiedId === item.relPath ? "Copied" : "Copy" }}
              </button>
              <span class="source-file" :title="item.relPath">{{
                item.fileName
              }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="modal-footer-custom">
        <span class="reference-count"
          >{{ citableFiles.length }} reference{{
            citableFiles.length !== 1 ? "s" : ""
          }}</span
        >
        <button class="btn-primary" @click="handleClose">Done</button>
      </div>
    </div>
  </BaseModal>

  <ConfirmExtractMetadataModal
    v-model="showMetadataConfirm"
    action-label="export"
    :missing-count="missingFiles.length"
    @confirm="handleExtractConfirm"
    @skip="handleExtractSkip"
    @cancel="handleExtractCancel"
  />
</template>

<style scoped>
.custom-modal-layout {
  margin: -24px -20px;
  display: flex;
  flex-direction: column;
  height: calc(70vh - 48px);
  min-height: 400px;
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

.toolbar-section {
  padding: 16px 24px;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  flex-shrink: 0;
  flex-wrap: wrap;
}

.style-selector {
  display: flex;
  align-items: center;
  gap: 10px;
}

.style-selector label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
}

.toolbar-actions {
  display: flex;
  gap: 8px;
}

.toolbar-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: var(--color-neutral-120);
  border: none;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
  cursor: pointer;
  transition: all 0.2s;
}

.toolbar-btn:hover:not(:disabled) {
  background: var(--color-neutral-170);
}

.toolbar-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.toolbar-btn .check-icon {
  color: var(--color-success-600);
}

.modal-body-custom {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  text-align: center;
  color: var(--text-secondary);
}

.empty-icon {
  color: var(--color-neutral-400);
  margin-bottom: 12px;
}

.empty-hint {
  font-size: 12px;
  margin-top: 4px;
  color: var(--color-neutral-450);
}

.citations-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.citation-card {
  background: var(--color-neutral-80);
  border: 1px solid var(--border-card);
  border-radius: 10px;
  padding: 16px;
  transition: all 0.2s;
}

.citation-card:hover {
  border-color: var(--accent-soft, var(--color-accent-100));
  box-shadow: 0 2px 8px var(--alpha-black-08);
}

.citation-text {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-primary);
  margin-bottom: 12px;
}

.citation-text :deep(em) {
  font-style: italic;
}

.citation-text.bibtex-format {
  font-family: "SF Mono", "Monaco", "Consolas", monospace;
  font-size: 12px;
  line-height: 1.5;
}

.citation-text pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
}

.citation-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 12px;
  border-top: 1px solid var(--border-color);
}

.copy-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  background: transparent;
  border: 1px solid var(--border-card);
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s;
}

.copy-btn:hover {
  background: var(--color-neutral-120);
  color: var(--text-primary);
  border-color: var(--border-card-hover);
}

.copy-btn.copied {
  background: var(--color-success-50);
  border-color: var(--color-success-200);
  color: var(--color-success-700);
}

.source-file {
  font-size: 11px;
  color: var(--text-secondary);
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.modal-footer-custom {
  padding: 16px 24px;
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}

.reference-count {
  font-size: 13px;
  color: var(--text-secondary);
}

.btn-primary {
  padding: 10px 24px;
  background: var(--accent-color);
  color: var(--color-white);
  border: 1px solid var(--accent-color);
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
}

.btn-primary:hover {
  opacity: 0.85;
}

/* Dark theme adjustments */
[data-theme="dark"] .modal-header-custom,
[data-theme="dark"] .toolbar-section,
[data-theme="dark"] .modal-body-custom,
[data-theme="dark"] .modal-footer-custom {
  background: var(--color-white);
}

[data-theme="dark"] .citation-card {
  background: var(--color-neutral-105);
  border-color: var(--color-neutral-150);
}

[data-theme="dark"] .citation-card:hover {
  background: var(--color-neutral-150);
  border-color: var(--border-hover);
  box-shadow: none;
}

[data-theme="dark"] .citation-footer {
  border-top-color: var(--color-neutral-150);
}

[data-theme="dark"] .toolbar-btn {
  background: var(--color-neutral-150);
  color: var(--text-primary);
}

[data-theme="dark"] .toolbar-btn:hover:not(:disabled) {
  background: var(--color-neutral-200);
}

[data-theme="dark"] .copy-btn {
  border-color: var(--color-neutral-200);
  color: var(--text-secondary);
}

[data-theme="dark"] .copy-btn:hover {
  background: var(--color-neutral-150);
  border-color: var(--color-neutral-250);
  color: var(--text-primary);
}

[data-theme="dark"] .copy-btn.copied {
  background: rgba(46, 125, 50, 0.2);
  border-color: rgba(46, 125, 50, 0.4);
  color: #81c784;
}

[data-theme="dark"] .empty-icon {
  color: var(--color-neutral-200);
}

[data-theme="dark"] .empty-hint {
  color: var(--text-secondary);
}
</style>
