<script setup lang="ts">
import BaseModal from './BaseModal.vue'

defineProps<{
  modelValue: boolean
  title?: string
  message: string
  confirmText?: string
  cancelText?: string
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
  (event: 'confirm'): void
  (event: 'cancel'): void
}>()

function handleClose() {
  emit('update:modelValue', false)
  emit('cancel')
}

function handleConfirm() {
  emit('update:modelValue', false)
  emit('confirm')
}
</script>

<template>
  <BaseModal :model-value="modelValue" :title="title || 'Confirm'" size="small" @update:model-value="handleClose">
    <p class="message">{{ message }}</p>

    <template #footer>
      <button class="btn btn-secondary" @click="handleClose">{{ cancelText || 'Cancel' }}</button>
      <button class="btn btn-danger" @click="handleConfirm">{{ confirmText || 'Delete' }}</button>
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
  background: var(--color-white);
  border-color: var(--color-neutral-350);
  color: var(--color-neutral-800);
}

.btn-secondary:hover {
  background: var(--color-neutral-130);
  border-color: var(--color-neutral-400);
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
