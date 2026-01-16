<script setup lang="ts">
import { ref, onMounted } from 'vue'
import BaseModal from './BaseModal.vue'
import { getSettings, saveApiKey, validateApiKey, deleteApiKey } from '../api/client'
import type { Settings } from '../types'

defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
  (event: 'close'): void
}>()

const settings = ref<Settings | null>(null)
const apiKeyInput = ref('')
const showApiKey = ref(false)
const isLoading = ref(false)
const isSaving = ref(false)
const isValidating = ref(false)
const validationStatus = ref<'none' | 'valid' | 'invalid'>('none')
const validationError = ref('')
const saveError = ref('')

onMounted(async () => {
  isLoading.value = true
  try {
    settings.value = await getSettings()
  } catch (e) {
    console.error('Failed to load settings:', e)
  } finally {
    isLoading.value = false
  }
})

async function handleValidate() {
  if (!apiKeyInput.value && !settings.value?.hasApiKey) return

  isValidating.value = true
  validationStatus.value = 'none'
  validationError.value = ''

  try {
    // If there's input, save first then validate
    if (apiKeyInput.value) {
      await saveApiKey(apiKeyInput.value)
    }
    const result = await validateApiKey()
    validationStatus.value = result.valid ? 'valid' : 'invalid'
    validationError.value = result.error || ''

    // Reload settings if we saved
    if (apiKeyInput.value) {
      settings.value = await getSettings()
      apiKeyInput.value = ''
    }
  } catch (e: any) {
    validationStatus.value = 'invalid'
    validationError.value = e.message || 'Validation failed'
  } finally {
    isValidating.value = false
  }
}

async function handleSave() {
  if (!apiKeyInput.value) return

  isSaving.value = true
  saveError.value = ''

  try {
    await saveApiKey(apiKeyInput.value)
    settings.value = await getSettings()
    apiKeyInput.value = ''
    validationStatus.value = 'none'
  } catch (e: any) {
    saveError.value = e.message || 'Failed to save'
  } finally {
    isSaving.value = false
  }
}

async function handleDelete() {
  isSaving.value = true
  try {
    await deleteApiKey()
    settings.value = await getSettings()
    validationStatus.value = 'none'
    apiKeyInput.value = ''
  } catch (e) {
    console.error('Failed to delete API key:', e)
  } finally {
    isSaving.value = false
  }
}

function handleClose() {
  emit('update:modelValue', false)
  emit('close')
}
</script>

<template>
  <BaseModal :model-value="modelValue" size="medium" @update:model-value="handleClose">
    <template #header-content>
      <span class="icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path
            d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
          <circle cx="12" cy="12" r="3" />
        </svg>
      </span>
      <h3 class="modal-title">Settings</h3>
    </template>

    <div v-if="isLoading" class="loading">Loading settings...</div>

    <template v-else>
      <div class="form-section">
        <label class="form-label">DeepSeek API Key</label>
        <p class="form-hint">Required for AI-powered answers. Get your key from <a href="https://platform.deepseek.com"
            target="_blank">platform.deepseek.com</a></p>

        <div class="current-key" v-if="settings?.hasApiKey">
          <span class="key-status valid">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
              <polyline points="22 4 12 14.01 9 11.01" />
            </svg>
            Key configured
          </span>
          <span class="masked-key">{{ settings.maskedApiKey }}</span>
          <button class="btn-link danger" @click="handleDelete" :disabled="isSaving">Remove</button>
        </div>

        <div class="input-group">
          <input v-model="apiKeyInput" :type="showApiKey ? 'text' : 'password'" class="form-input"
            :placeholder="settings?.hasApiKey ? 'Enter new key to replace' : 'sk-xxxxxxxxxxxxxxxx'" />
          <button class="input-addon" @click="showApiKey = !showApiKey" type="button">
            <svg v-if="showApiKey" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
              fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
              <line x1="1" x2="23" y1="1" y2="23" />
            </svg>
            <svg v-else xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
              <circle cx="12" cy="12" r="3" />
            </svg>
          </button>
        </div>

        <div v-if="saveError" class="error-message">{{ saveError }}</div>

        <div class="validation-result" v-if="validationStatus !== 'none'">
          <span v-if="validationStatus === 'valid'" class="status valid">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
              <polyline points="22 4 12 14.01 9 11.01" />
            </svg>
            API key is valid
          </span>
          <span v-else class="status invalid">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="15" x2="9" y1="9" y2="15" />
              <line x1="9" x2="15" y1="9" y2="15" />
            </svg>
            Invalid: {{ validationError || 'API key verification failed' }}
          </span>
        </div>
      </div>
    </template>

    <template #footer>
      <button class="btn btn-secondary" @click="handleClose">Cancel</button>
      <button class="btn btn-outline" @click="handleValidate"
        :disabled="isValidating || (!apiKeyInput && !settings?.hasApiKey)">
        {{ isValidating ? 'Validating...' : 'Validate' }}
      </button>
      <button class="btn btn-primary" @click="handleSave" :disabled="isSaving || !apiKeyInput">
        {{ isSaving ? 'Saving...' : 'Save' }}
      </button>
    </template>
  </BaseModal>
</template>

<style scoped>
.icon {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--accent-color, var(--color-accent-600));
}

.modal-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.loading {
  text-align: center;
  color: var(--text-secondary);
  padding: 20px;
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.form-label {
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.form-hint {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0;
}

.form-hint a {
  color: var(--accent-color, var(--color-accent-600));
}

.current-key {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: var(--color-neutral-100);
  border-radius: 8px;
  font-size: 13px;
}

.key-status {
  display: flex;
  align-items: center;
  gap: 4px;
  font-weight: 500;
}

.key-status.valid {
  color: var(--color-success-700);
}

.masked-key {
  font-family: monospace;
  font-size: 12px;
  color: var(--text-secondary);
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.btn-link {
  background: none;
  border: none;
  font-size: 13px;
  cursor: pointer;
  padding: 4px 8px;
}

.btn-link.danger {
  color: var(--color-danger-700);
}

.btn-link.danger:hover {
  text-decoration: underline;
}

.input-group {
  display: flex;
  border: 1px solid var(--color-neutral-250);
  border-radius: 8px;
  overflow: hidden;
}

.input-group:focus-within {
  border-color: var(--accent-color, var(--color-accent-600));
  box-shadow: 0 0 0 2px var(--alpha-accent-10);
}

.form-input {
  flex: 1;
  padding: 10px 12px;
  border: none;
  font-size: 14px;
  font-family: inherit;
  outline: none;
}

.input-addon {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 12px;
  background: var(--color-neutral-100);
  border: none;
  border-left: 1px solid var(--color-neutral-250);
  cursor: pointer;
  color: var(--text-secondary);
}

.input-addon:hover {
  color: var(--text-primary);
  background: var(--color-neutral-220);
}

.error-message {
  color: var(--color-danger-700);
  font-size: 13px;
}

.validation-result {
  padding: 10px 12px;
  border-radius: 8px;
}

.validation-result .status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
}

.validation-result .status.valid {
  color: var(--color-success-700);
}

.validation-result .status.invalid {
  color: var(--color-danger-700);
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

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: var(--accent-color, var(--color-accent-600));
  color: var(--color-white);
}

.btn-primary:hover:not(:disabled) {
  background: var(--color-accent-700);
}

.btn-secondary {
  background: var(--color-white);
  color: var(--text-primary);
  border-color: var(--color-neutral-250);
}

.btn-secondary:hover:not(:disabled) {
  background: var(--color-neutral-100);
}

.btn-outline {
  background: transparent;
  color: var(--accent-color, var(--color-accent-600));
  border-color: var(--accent-color, var(--color-accent-600));
}

.btn-outline:hover:not(:disabled) {
  background: var(--accent-soft, var(--color-accent-50));
}
</style>
