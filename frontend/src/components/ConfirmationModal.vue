<script setup lang="ts">
import BaseModal from "./BaseModal.vue";

defineProps<{
  modelValue: boolean;
  title?: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
}>();

const emit = defineEmits<{
  (event: "update:modelValue", value: boolean): void;
  (event: "confirm"): void;
  (event: "cancel"): void;
}>();

function handleClose() {
  emit("update:modelValue", false);
  emit("cancel");
}

function handleConfirm() {
  emit("update:modelValue", false);
  emit("confirm");
}
</script>

<template>
  <BaseModal :model-value="modelValue" :title="title || 'Confirm'" size="small" @update:model-value="handleClose">
    <p class="message">{{ message }}</p>

    <template #footer>
      <button class="btn btn-secondary" @click="handleClose">
        {{ cancelText || "Cancel" }}
      </button>
      <button class="btn btn-danger" @click="handleConfirm">
        {{ confirmText || "Delete" }}
      </button>
    </template>
  </BaseModal>
</template>

<style scoped>
.message {
  padding: 20px;
  margin: 0;
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.5;
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

.modal-footer {
  background: var(--bg-panel);
  padding: 16px 20px;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  border-top: 1px solid var(--border-color);
  border-radius: 0 0 12px 12px;
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

.btn-danger {
  background: var(--color-danger-25);
  color: var(--color-danger-700);
  border-color: var(--color-danger-100);
}

.btn-danger:hover {
  background: var(--color-danger-50);
  border-color: var(--color-danger-250);
}
</style>
