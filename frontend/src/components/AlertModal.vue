<script setup lang="ts">
import BaseModal from "./BaseModal.vue";

defineProps<{
  modelValue: boolean;
  title?: string;
  message: string;
  buttonText?: string;
  type?: "error" | "warning" | "info" | "success";
}>();

const emit = defineEmits<{
  (event: "update:modelValue", value: boolean): void;
  (event: "close"): void;
}>();

function handleClose() {
  emit("update:modelValue", false);
  emit("close");
}
</script>

<template>
  <BaseModal
    :model-value="modelValue"
    size="small"
    @update:model-value="handleClose"
  >
    <template #header-content>
      <span class="icon" :class="type || 'error'">
        <svg
          v-if="type === 'success'"
          xmlns="http://www.w3.org/2000/svg"
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
          <polyline points="22 4 12 14.01 9 11.01" />
        </svg>
        <svg
          v-else-if="type === 'warning'"
          xmlns="http://www.w3.org/2000/svg"
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path
            d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"
          />
          <line x1="12" x2="12" y1="9" y2="13" />
          <line x1="12" x2="12.01" y1="17" y2="17" />
        </svg>
        <svg
          v-else-if="type === 'info'"
          xmlns="http://www.w3.org/2000/svg"
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <circle cx="12" cy="12" r="10" />
          <path d="M12 16v-4" />
          <path d="M12 8h.01" />
        </svg>
        <svg
          v-else
          xmlns="http://www.w3.org/2000/svg"
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <circle cx="12" cy="12" r="10" />
          <line x1="15" x2="9" y1="9" y2="15" />
          <line x1="9" x2="15" y1="9" y2="15" />
        </svg>
      </span>
      <h3 class="modal-title">{{ title || "Error" }}</h3>
    </template>

    <p class="message">{{ message }}</p>

    <template #footer>
      <button
        class="btn"
        :class="'btn-' + (type || 'error')"
        @click="handleClose"
      >
        {{ buttonText || "OK" }}
      </button>
    </template>
  </BaseModal>
</template>

<style scoped>
.icon {
  display: flex;
  align-items: center;
  justify-content: center;
}

.icon.error {
  color: var(--color-danger-700);
}

.icon.warning {
  color: var(--color-warning-700);
}

.icon.info {
  color: var(--color-info-700);
}

.icon.success {
  color: var(--color-success-700);
}

.modal-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.message {
  margin: 0;
  word-break: break-word;
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.5;
}

.btn {
  padding: 8px 20px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.2s;
}

.btn-error {
  background: var(--color-danger-25);
  color: var(--color-danger-700);
  border-color: var(--color-danger-100);
}

.btn-error:hover {
  background: var(--color-danger-50);
  border-color: var(--color-danger-250);
}

.btn-warning {
  background: var(--color-warning-100);
  color: var(--color-warning-700);
  border-color: var(--color-warning-400);
}

.btn-warning:hover {
  background: var(--color-warning-200);
  border-color: var(--color-warning-500);
}

.btn-info {
  background: var(--color-info-100);
  color: var(--color-info-700);
  border-color: var(--color-info-300);
}

.btn-info:hover {
  background: var(--color-info-200);
  border-color: var(--color-info-400);
}

.btn-success {
  background: var(--color-success-50);
  color: var(--color-success-700);
  border-color: var(--color-success-200);
}

.btn-success:hover {
  background: var(--color-success-100);
  border-color: var(--color-success-300);
}
</style>
