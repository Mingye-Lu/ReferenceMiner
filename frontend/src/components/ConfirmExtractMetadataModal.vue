<script setup lang="ts">
import { computed } from "vue";
import BaseModal from "./BaseModal.vue";

const props = defineProps<{
  modelValue: boolean;
  missingCount: number;
  actionLabel?: string;
}>();

const emit = defineEmits<{
  (event: "update:modelValue", value: boolean): void;
  (event: "confirm"): void;
  (event: "skip"): void;
  (event: "cancel"): void;
}>();

const actionText = computed(() => props.actionLabel || "export");

function handleClose() {
  emit("update:modelValue", false);
  emit("cancel");
}

function handleConfirm() {
  emit("update:modelValue", false);
  emit("confirm");
}

function handleSkip() {
  emit("update:modelValue", false);
  emit("skip");
}
</script>

<template>
  <BaseModal
    :model-value="modelValue"
    title="Extract missing metadata?"
    size="small"
    @update:model-value="handleClose"
  >
    <p class="message">
      Some references in this {{ actionText }} do not have citation metadata
      yet. Extract metadata now to improve citation quality.
    </p>
    <p class="hint" v-if="missingCount > 0">
      {{ missingCount }} reference{{ missingCount === 1 ? "" : "s" }} missing
      metadata.
    </p>

    <template #footer>
      <button class="btn btn-secondary" @click="handleSkip">
        Continue without
      </button>
      <button class="btn btn-primary" @click="handleConfirm">
        Extract metadata
      </button>
    </template>
  </BaseModal>
</template>

<style scoped>
.message {
  margin: 0;
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.5;
}

.hint {
  margin: 8px 0 0;
  color: var(--text-secondary);
  font-size: 12px;
}

.btn {
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.2s;
}

.btn-secondary {
  background: var(--bg-card);
  border-color: var(--border-card);
  color: var(--text-primary);
}

.btn-secondary:hover {
  background: var(--bg-card-hover);
  border-color: var(--accent-bright);
}

.btn-primary {
  background: var(--accent-color);
  color: var(--color-white);
  border-color: var(--accent-color);
}

.btn-primary:hover {
  opacity: 0.9;
}
</style>
