<script setup lang="ts">
import type { UploadItem } from "../types";

const props = defineProps<{
  item: UploadItem;
  isSelected: boolean;
}>();

const emit = defineEmits<{
  (event: "select"): void;
  (event: "remove"): void;
  (event: "replace"): void;
}>();

function getStatusLabel(status: string): string {
  switch (status) {
    case "pending":
      return "Pending";
    case "uploading":
      return "Uploading...";
    case "processing":
      return "Processing...";
    case "complete":
      return "Complete";
    case "error":
      return "Error";
    case "duplicate":
      return "Duplicate";
    default:
      return status;
  }
}

function getBibliographyStatus(): string {
  if (props.item.bibliography) {
    return "has-bib";
  }
  return "no-bib";
}
</script>

<template>
  <div class="file-queue-item" :class="[item.status, getBibliographyStatus(), { selected: isSelected }]"
    @click="emit('select')">
    <div class="item-header">
      <span class="filename">{{ item.file.name }}</span>
      <div class="item-badges">
        <span class="status-badge" :class="item.status">
          {{ getStatusLabel(item.status) }}
        </span>
        <span v-if="item.bibliography" class="bib-badge" title="Has bibliography">
          Bib
        </span>
      </div>
      <button v-if="item.status === 'complete'" class="btn-icon" @click.stop="emit('remove')">
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
      <button class="btn-small" @click.stop="emit('replace')">Replace</button>
      <button class="btn-small btn-ghost" @click.stop="emit('remove')">
        Skip
      </button>
    </div>

    <div v-if="item.status === 'error'" class="error-info">
      <span class="error-text">{{ item.error }}</span>
      <button class="btn-small btn-ghost" @click.stop="emit('remove')">
        Dismiss
      </button>
    </div>
  </div>
</template>

<style scoped>
.file-queue-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px;
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
}

.file-queue-item:hover {
  border-color: var(--accent-bright);
  background: var(--bg-card-hover);
}

.file-queue-item.selected {
  border-color: var(--accent-color);
  background: rgba(59, 130, 246, 0.05);
}

.file-queue-item.complete {
  border-color: var(--color-success-600);
  background: rgba(76, 175, 80, 0.1);
}

.file-queue-item.error {
  border-color: var(--color-danger-400);
  background: rgba(211, 47, 47, 0.1);
}

.file-queue-item.duplicate {
  border-color: var(--color-warning-600);
  background: rgba(255, 152, 0, 0.1);
}

.item-header {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.filename {
  font-size: 12px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.item-badges {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.status-badge {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 99px;
  background: var(--color-neutral-215);
  color: var(--color-neutral-650);
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

.bib-badge {
  font-size: 9px;
  padding: 2px 5px;
  border-radius: 4px;
  background: var(--color-success-50);
  color: var(--color-success-700);
  font-weight: 600;
}

.bib-badge.pending {
  background: var(--color-warning-100);
  color: var(--color-warning-800);
}

.btn-icon {
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

.btn-icon:hover {
  background: var(--bg-icon-hover);
  color: var(--color-red-600);
}

.progress-bar {
  height: 3px;
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

.btn-small {
  padding: 4px 8px;
  font-size: 10px;
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
</style>
