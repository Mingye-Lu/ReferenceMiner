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
  background: #fff;
  border-color: #ddd;
  color: #333;
}

.btn-secondary:hover {
  background: #f5f5f5;
  border-color: #ccc;
}

.btn-danger {
  background: #fff0f0;
  color: #d32f2f;
  border-color: #ffcdd2;
}

.btn-danger:hover {
  background: #ffebee;
  border-color: #ef9a9a;
}
</style>
