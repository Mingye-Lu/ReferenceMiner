<script setup lang="ts">
import { ref, computed, watch } from "vue";
import BaseModal from "./BaseModal.vue";
import FileQueueItem from "./FileQueueItem.vue";
import BibliographyEditor from "./BibliographyEditor.vue";
import { uploadFileStream, uploadFileToBankStream } from "../api/client";
import type {
  UploadItem,
  ManifestEntry,
  UploadProgress,
  Bibliography,
} from "../types";
import { useQueue } from "../composables/useQueue";

const props = withDefaults(
  defineProps<{
    projectId?: string;
    uploadMode?: "bank" | "project";
  }>(),
  {
    uploadMode: "project",
  },
);

const emit = defineEmits<{
  (e: "upload-complete", entry: ManifestEntry): void;
}>();

const isDragOver = ref(false);
const uploads = ref<UploadItem[]>([]);
const fileInput = ref<HTMLInputElement | null>(null);
const folderInput = ref<HTMLInputElement | null>(null);
const isOpen = ref(false);
const activeUploads = ref(0);
const selectedFileId = ref<string | null>(null);
const MAX_CONCURRENT_UPLOADS = 3;
const lastTriggerPoint = ref<{ x: number; y: number } | null>(null);
const { launchQueueEject } = useQueue();

const SUPPORTED_EXTENSIONS = [
  ".pdf",
  ".docx",
  ".txt",
  ".md",
  ".png",
  ".jpg",
  ".jpeg",
  ".csv",
  ".xlsx",
];

const selectedFile = computed(
  () => uploads.value.find((u) => u.id === selectedFileId.value) || null,
);

const hasFilesWithBibliography = computed(() =>
  uploads.value.some((u) => u.bibliography),
);

const hasFilesWithoutBibliography = computed(() =>
  uploads.value.some((u) => !u.bibliography),
);

function isSupported(file: File): boolean {
  const ext = "." + file.name.split(".").pop()?.toLowerCase();
  return SUPPORTED_EXTENSIONS.includes(ext);
}

function addFiles(
  files: FileList | File[],
  origin?: { x: number; y: number } | null,
) {
  for (const file of files) {
    if (!isSupported(file)) {
      uploads.value.push({
        id: Date.now().toString() + Math.random(),
        file,
        status: "error",
        progress: 0,
        error: `Unsupported file type: ${file.name.split(".").pop()}`,
      });
      continue;
    }

    const item: UploadItem = {
      id: Date.now().toString() + Math.random(),
      file,
      status: "pending",
      progress: 0,
      bibliography: null,
    };
    uploads.value.push(item);
    if (origin) {
      launchQueueEject(origin.x, origin.y);
    }
  }

  if (!selectedFileId.value && uploads.value.length > 0) {
    selectedFileId.value = uploads.value[0].id;
  }
}

async function processQueue() {
  const pending = uploads.value.filter((u) => u.status === "pending");

  for (const item of pending) {
    if (activeUploads.value >= MAX_CONCURRENT_UPLOADS) {
      break;
    }
    processUpload(item);
  }
}

function openModal() {
  isOpen.value = true;
}

function closeModal(value: boolean) {
  isOpen.value = value;
  if (!value) {
    isDragOver.value = false;
  }
}

async function processUpload(item: UploadItem, replace: boolean = false) {
  const updateItem = (updates: Partial<UploadItem>) => {
    const idx = uploads.value.findIndex((u) => u.id === item.id);
    if (idx !== -1) {
      Object.assign(uploads.value[idx], updates);
    }
  };

  activeUploads.value++;
  updateItem({ status: "uploading", progress: 0 });

  try {
    const handlers = {
      onProgress: (progress: UploadProgress) => {
        updateItem({
          status: "processing",
          progress: progress.percent ?? item.progress,
          phase: progress.phase,
        });
      },
      onDuplicate: (_sha256: string, existingPath: string) => {
        updateItem({
          status: "duplicate",
          duplicatePath: existingPath,
          phase: undefined,
        });
      },
      onComplete: (result: any) => {
        updateItem({
          status: "complete",
          progress: 100,
          result,
          phase: undefined,
        });
        if (result.manifestEntry) {
          emit("upload-complete", result.manifestEntry);
        }
      },
      onError: (_code: string, message: string) => {
        updateItem({
          status: "error",
          error: message,
          phase: undefined,
        });
      },
    };

    const result =
      props.uploadMode === "bank"
        ? await uploadFileToBankStream(
          item.file,
          handlers,
          replace,
          item.bibliography,
        )
        : await uploadFileStream(
          props.projectId!,
          item.file,
          handlers,
          replace,
          item.bibliography,
        );

    const currentItem = uploads.value.find((u) => u.id === item.id);
    if (!result && currentItem) {
      if (
        currentItem.status !== "duplicate" &&
        currentItem.status !== "error"
      ) {
        updateItem({ status: "error", error: "Upload failed" });
      }
    }
  } catch (e) {
    updateItem({
      status: "error",
      error: e instanceof Error ? e.message : "Upload failed",
    });
  } finally {
    activeUploads.value--;
    processQueue();
  }
}

function handleDrop(event: DragEvent) {
  isDragOver.value = false;
  if (event.dataTransfer?.files) {
    addFiles(event.dataTransfer.files, { x: event.clientX, y: event.clientY });
  }
}

function handleFileSelect(event: Event) {
  const target = event.target as HTMLInputElement;
  if (target.files) {
    addFiles(target.files, lastTriggerPoint.value);
    target.value = "";
  }
}

function handleFolderSelect(event: Event) {
  const target = event.target as HTMLInputElement;
  if (target.files) {
    addFiles(target.files, lastTriggerPoint.value);
    target.value = "";
  }
}

function selectFile(item: UploadItem) {
  if (selectedFileId.value === item.id) {
    selectedFileId.value = null;
    return;
  }
  selectedFileId.value = item.id;
}

function replaceFile(item: UploadItem, event?: MouseEvent) {
  const idx = uploads.value.findIndex((u) => u.id === item.id);
  if (idx !== -1) {
    uploads.value[idx].status = "pending";
    uploads.value[idx].duplicatePath = undefined;
    if (event?.currentTarget instanceof HTMLElement) {
      const rect = event.currentTarget.getBoundingClientRect();
      launchQueueEject(rect.left + rect.width / 2, rect.top + rect.height / 2);
    }
    processUpload(uploads.value[idx], true);
  }
}

function removeItem(item: UploadItem) {
  const idx = uploads.value.findIndex((u) => u.id === item.id);
  if (idx !== -1) {
    uploads.value.splice(idx, 1);
    if (selectedFileId.value === item.id) {
      selectedFileId.value =
        uploads.value.length > 0 ? uploads.value[0].id : null;
    }
  }
}

function clearCompleted() {
  uploads.value = uploads.value.filter(
    (u) => u.status !== "complete" && u.status !== "error",
  );
  if (
    selectedFileId.value &&
    !uploads.value.find((u) => u.id === selectedFileId.value)
  ) {
    selectedFileId.value =
      uploads.value.length > 0 ? uploads.value[0].id : null;
  }
}

function setTriggerPoint(event: MouseEvent) {
  if (!(event.currentTarget instanceof HTMLElement)) return;
  const rect = event.currentTarget.getBoundingClientRect();
  lastTriggerPoint.value = {
    x: rect.left + rect.width / 2,
    y: rect.top + rect.height / 2,
  };
}

function updateBibliography(bibliography: Bibliography | null) {
  if (selectedFile.value) {
    selectedFile.value.bibliography = bibliography;
  }
}

function startUploads() {
  processQueue();
  closeModal(false);
}

function handleKeyDown(event: KeyboardEvent) {
  if (!isOpen.value) return;

  const currentIndex = uploads.value.findIndex(
    (u) => u.id === selectedFileId.value,
  );

  if (event.key === "ArrowDown" && currentIndex < uploads.value.length - 1) {
    event.preventDefault();
    selectedFileId.value = uploads.value[currentIndex + 1].id;
  } else if (event.key === "ArrowUp" && currentIndex > 0) {
    event.preventDefault();
    selectedFileId.value = uploads.value[currentIndex - 1].id;
  } else if (event.key === "Escape") {
    event.preventDefault();
    selectedFileId.value = null;
  }
}

watch(isOpen, (value) => {
  if (value) {
    document.addEventListener("keydown", handleKeyDown);
  } else {
    document.removeEventListener("keydown", handleKeyDown);
  }
});
</script>

<template>
  <div class="file-uploader">
    <button class="upload-trigger" @click="openModal">Upload Files</button>

    <BaseModal :model-value="isOpen" size="xlarge" :title="uploadMode === 'bank' ? 'Upload to Reference Bank' : 'Upload to Project'
      " @update:model-value="closeModal">
      <div class="upload-modal-content">
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
            <p class="drop-hint">
              PDF, DOCX, TXT, MD, Images (PNG, JPG). Folder upload supported.
            </p>
            <input type="file" multiple :accept="SUPPORTED_EXTENSIONS.join(',')" @change="handleFileSelect"
              ref="fileInput" class="hidden-input" />
            <input type="file" webkitdirectory directory @change="handleFolderSelect" ref="folderInput"
              class="hidden-input" />
            <div class="upload-actions">
              <button class="btn-secondary" @click="
                setTriggerPoint($event);
              fileInput?.click();
              ">
                Select Files
              </button>
              <button class="btn-secondary" @click="
                setTriggerPoint($event);
              folderInput?.click();
              ">
                Select Folder
              </button>
            </div>
          </template>

          <template v-else>
            <div class="upload-queue">
              <FileQueueItem v-for="item in uploads" :key="item.id" :item="item"
                :is-selected="selectedFileId === item.id" @select="selectFile(item)" @remove="removeItem(item)"
                @replace="replaceFile(item, $event)" />
            </div>

            <div class="upload-actions">
              <button class="btn-secondary" @click="
                setTriggerPoint($event);
              fileInput?.click();
              ">
                Add More
              </button>
              <button class="btn-secondary" @click="
                setTriggerPoint($event);
              folderInput?.click();
              ">
                Add Folder
              </button>
              <button v-if="
                uploads.some(
                  (u) => u.status === 'complete' || u.status === 'error',
                )
              " class="btn-secondary" @click="clearCompleted">
                Clear Done
              </button>
            </div>
            <input type="file" multiple :accept="SUPPORTED_EXTENSIONS.join(',')" @change="handleFileSelect"
              ref="fileInput" class="hidden-input" />
            <input type="file" webkitdirectory directory @change="handleFolderSelect" ref="folderInput"
              class="hidden-input" />
          </template>
        </div>

        <div class="bibliography-panel">
          <template v-if="selectedFile">
            <BibliographyEditor :model-value="selectedFile.bibliography ?? null" :file="selectedFile.file" compact
              @update:model-value="updateBibliography" />
          </template>
          <template v-else>
            <div class="empty-state">
              <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="16" x2="8" y1="13" y2="13" />
                <line x1="16" x2="8" y1="17" y2="17" />
                <polyline points="10 9 10 9 10 9" />
              </svg>
              <p class="empty-text">Select a file to edit bibliography</p>
            </div>
          </template>
        </div>
      </div>

      <template #footer>
        <div class="footer-info">
          <span v-if="hasFilesWithBibliography" class="info-badge has-bib">
            {{uploads.filter((u) => u.bibliography).length}} with bibliography
          </span>
          <span v-if="hasFilesWithoutBibliography" class="info-badge no-bib">
            {{uploads.filter((u) => !u.bibliography).length}} without
          </span>
        </div>
        <button class="btn-secondary" @click="closeModal(false)">Cancel</button>
        <button class="btn-primary" @click="startUploads" :disabled="uploads.length === 0">
          Upload {{ uploads.length }} file{{ uploads.length === 1 ? "" : "s" }}
        </button>
      </template>
    </BaseModal>
  </div>
</template>

<style scoped>
.modal-body {
  padding: 0 20px;
}

.file-uploader {
  margin-bottom: 8px;
}

.upload-trigger {
  width: 100%;
  padding: 10px 12px;
  background: var(--text-primary);
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

.upload-modal-content {
  display: grid;
  padding: 20px;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  min-height: 400px;
}

.drop-zone {
  border: 2px dashed var(--border-color);
  border-radius: 12px;
  padding: 16px;
  text-align: center;
  transition: all 0.2s;
  background: var(--bg-panel);
  display: flex;
  flex-direction: column;
  align-items: center;
}

.drop-zone.dragover {
  border-color: var(--accent-color);
  background: var(--color-neutral-140);
}

.drop-zone.has-items {
  padding: 12px;
  text-align: left;
  align-items: flex-start;
}

.drop-zone svg {
  color: var(--color-neutral-500);
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
  color: var(--text-primary);
  padding: 8px 16px;
  font-size: 12px;
  background: var(--color-white);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s;
}

.btn-secondary:hover {
  background: var(--bg-card-hover);
  border-color: var(--accent-bright);
}

.btn-primary {
  background: var(--accent-color);
  color: white;
  padding: 8px 16px;
  font-size: 12px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s;
}

.btn-primary:hover {
  opacity: 0.9;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.upload-queue {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
  overflow-y: auto;
  margin-bottom: 12px;
}

.upload-actions {
  display: flex;
  gap: 8px;
  justify-content: center;
  flex-wrap: wrap;
}

.bibliography-panel {
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background: var(--bg-panel);
  padding: 16px;
  overflow-y: auto;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 12px;
  color: var(--text-secondary);
}

.empty-state svg {
  opacity: 0.5;
}

.empty-text {
  font-size: 13px;
  margin: 0;
}

.footer-info {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-right: auto;
}

.info-badge {
  font-size: 11px;
  padding: 3px 8px;
  border-radius: 99px;
  font-weight: 500;
}

.info-badge.has-bib {
  background: var(--color-success-50);
  color: var(--color-success-700);
}

.info-badge.no-bib {
  background: var(--color-neutral-200);
  color: var(--color-neutral-700);
}

.info-badge.pending {
  background: var(--color-warning-100);
  color: var(--color-warning-800);
}
</style>
