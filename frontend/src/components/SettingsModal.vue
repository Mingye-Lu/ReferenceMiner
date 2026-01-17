<script setup lang="ts">
import { ref, onMounted } from 'vue'
import BaseModal from './BaseModal.vue'
import ConfirmationModal from './ConfirmationModal.vue'
import { getSettings, saveApiKey, validateApiKey, deleteApiKey, resetAllData } from '../api/client'
import type { BalanceInfo, Settings } from '../types'

defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
  (event: 'close'): void
  (event: 'reset'): void
}>()

const settings = ref<Settings | null>(null)
const apiKeyInput = ref('')
const showApiKey = ref(false)
const isLoading = ref(false)
const isSaving = ref(false)
const isValidating = ref(false)
const isResetting = ref(false)
const showResetConfirm = ref(false)
const validationStatus = ref<'none' | 'valid' | 'invalid'>('none')
const validationError = ref('')
const balanceInfos = ref<BalanceInfo[]>([])
const balanceAvailable = ref<boolean | null>(null)
const saveError = ref('')
const resetError = ref('')
const resetSuccess = ref('')

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
    const result = await validateApiKey(apiKeyInput.value || undefined)
    validationStatus.value = result.valid ? 'valid' : 'invalid'
    validationError.value = formatValidationError(result.error)
    balanceInfos.value = result.balanceInfos ?? []
    balanceAvailable.value = typeof result.isAvailable === 'boolean' ? result.isAvailable : null

  } catch (e: any) {
    validationStatus.value = 'invalid'
    validationError.value = formatValidationError(e.message || 'Validation failed')
    balanceInfos.value = []
    balanceAvailable.value = null
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
    balanceInfos.value = []
    balanceAvailable.value = null
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
    balanceInfos.value = []
    balanceAvailable.value = null
  } catch (e) {
    console.error('Failed to delete API key:', e)
  } finally {
    isSaving.value = false
  }
}

function handleResetClick() {
  showResetConfirm.value = true
  resetError.value = ''
  resetSuccess.value = ''
}

async function handleResetConfirm() {
  isResetting.value = true
  resetError.value = ''
  resetSuccess.value = ''

  try {
    const result = await resetAllData()
    resetSuccess.value = result.message
    showResetConfirm.value = false

    // Emit reset event to parent so it can refresh data
    emit('reset')

    // Close settings modal after a brief delay
    setTimeout(() => {
      handleClose()
    }, 1500)
  } catch (e: any) {
    resetError.value = e.message || 'Failed to reset data'
  } finally {
    isResetting.value = false
  }
}

function handleClose() {
  emit('update:modelValue', false)
  emit('close')
}

function formatValidationError(error?: string): string {
  if (!error) return ''
  const trimmed = error.trim()
  const jsonStart = trimmed.indexOf('{')
  if (jsonStart !== -1) {
    const maybeJson = trimmed.slice(jsonStart)
    try {
      const parsed = JSON.parse(maybeJson)
      const message = parsed?.error?.message
      if (typeof message === 'string' && message.trim()) {
        return message.trim()
      }
    } catch {
      // Ignore JSON parsing errors and fall back to raw text.
    }
  }
  return trimmed
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

    <div class="settings-container">
      <!-- API Configuration Section -->
      <section class="settings-section">
        <div class="section-header">
          <div class="section-icon">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4" />
            </svg>
          </div>
          <div>
            <h4 class="section-title">API Configuration</h4>
            <p class="section-description">Configure your DeepSeek API key for AI-powered answers</p>
          </div>
        </div>

        <div class="section-content">
          <label class="form-label">DeepSeek API Key</label>
          <p class="form-hint">Get your key from <a href="https://platform.deepseek.com" target="_blank">platform.deepseek.com</a></p>

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

          <div class="api-input-row">
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
            <div class="api-actions">
              <button class="btn btn-outline" @click="handleValidate"
                :disabled="isValidating || (!apiKeyInput && !settings?.hasApiKey)">
                {{ isValidating ? 'Validating...' : 'Validate' }}
              </button>
              <button class="btn btn-primary" @click="handleSave" :disabled="isSaving || !apiKeyInput">
                {{ isSaving ? 'Saving...' : 'Save' }}
              </button>
            </div>
          </div>

          <div v-if="saveError" class="error-message">{{ saveError }}</div>

          <div class="validation-result" v-if="validationStatus !== 'none'">
            <span v-if="validationStatus === 'valid'" class="status valid">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                <polyline points="22 4 12 14.01 9 11.01" />
              </svg>
              {{ balanceAvailable === false ? 'API key is valid, but balance is insufficient' : 'API key is valid' }}
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

          <div v-if="balanceInfos.length" class="balance-panel">
            <div class="balance-header">
              <span class="balance-title">Remaining balance</span>
              <span v-if="balanceAvailable === false" class="balance-warning">Insufficient for API calls</span>
            </div>
            <div class="balance-list">
              <div v-for="info in balanceInfos" :key="info.currency" class="balance-item">
                <div class="balance-line">
                  <span class="balance-currency">{{ info.currency }}</span>
                  <span class="balance-amount">{{ info.totalBalance }}</span>
                </div>
                <div class="balance-meta">
                  Granted {{ info.grantedBalance }} · Topped up {{ info.toppedUpBalance }}
                </div>
              </div>
            </div>
          </div>

        </div>
      </section>

      <!-- Danger Zone Section -->
      <section class="settings-section danger-section">
        <div class="section-header">
          <div class="section-icon danger-icon">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
              <line x1="12" x2="12" y1="9" y2="13" />
              <line x1="12" x2="12.01" y1="17" y2="17" />
            </svg>
          </div>
          <div>
            <h4 class="section-title">Danger Zone</h4>
            <p class="section-description">Destructive actions that cannot be undone</p>
          </div>
        </div>

        <div class="section-content">
          <p class="form-hint">Clear all indexed chunks and chat sessions. Files will remain in the reference folder.</p>

          <div v-if="resetSuccess" class="success-message">{{ resetSuccess }}</div>
          <div v-if="resetError" class="error-message">{{ resetError }}</div>

          <button class="btn btn-danger" @click="handleResetClick" :disabled="isResetting">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M3 6h18" />
              <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
              <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
              <line x1="10" x2="10" y1="11" y2="17" />
              <line x1="14" x2="14" y1="11" y2="17" />
            </svg>
            {{ isResetting ? 'Clearing...' : 'Clear All Data' }}
          </button>
        </div>
      </section>
    </div>

  </BaseModal>

  <!-- Reset Confirmation Modal -->
  <ConfirmationModal
    v-model="showResetConfirm"
    title="Clear All Data?"
    message="This will permanently delete all indexed chunks, search indexes, and chat sessions. Your files will remain in the reference folder. This action cannot be undone."
    confirm-text="Clear All Data"
    cancel-text="Cancel"
    @confirm="handleResetConfirm"
  />
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

.settings-container {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.settings-section {
  border: 1px solid var(--color-neutral-250);
  border-radius: 10px;
  overflow: hidden;
}

.section-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px;
  background: var(--color-neutral-100);
  border-bottom: 1px solid var(--color-neutral-250);
}

.section-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 6px;
  background: var(--accent-soft, var(--color-accent-50));
  color: var(--accent-color, var(--color-accent-600));
  flex-shrink: 0;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 2px 0;
}

.section-description {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 0;
}

.section-content {
  padding: 16px;
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

.form-input::-ms-reveal,
.form-input::-ms-clear {
  display: none;
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

.balance-panel {
  border: 1px solid var(--color-neutral-250);
  border-radius: 8px;
  background: var(--color-neutral-100);
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.balance-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.balance-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.balance-warning {
  font-size: 12px;
  color: var(--color-danger-700);
  background: var(--color-danger-50);
  border: 1px solid var(--color-danger-200);
  padding: 2px 8px;
  border-radius: 999px;
}

.balance-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.balance-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.balance-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 13px;
  color: var(--text-primary);
}

.balance-currency {
  font-weight: 600;
}

.balance-amount {
  font-variant-numeric: tabular-nums;
}

.balance-meta {
  font-size: 12px;
  color: var(--text-secondary);
}

.api-input-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.api-input-row .input-group {
  flex: 1;
}

.api-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.api-actions .btn {
  min-width: 88px;
  height: 36px;
}

@media (max-width: 640px) {
  .api-input-row {
    flex-direction: column;
    align-items: stretch;
  }

  .api-actions {
    justify-content: flex-end;
  }
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

.danger-section {
  border-color: var(--color-danger-200);
}

.danger-section .section-header {
  background: var(--color-danger-50);
  border-bottom-color: var(--color-danger-200);
}

.danger-icon {
  background: var(--color-danger-100) !important;
  color: var(--color-danger-700) !important;
}

.danger-section .section-title {
  color: var(--color-danger-700);
}

.danger-section .section-description {
  color: var(--color-danger-600);
}

.btn-danger {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--color-danger-600);
  color: var(--color-white);
}

.btn-danger:hover:not(:disabled) {
  background: var(--color-danger-700);
}

.success-message {
  color: var(--color-success-700);
  font-size: 13px;
  padding: 10px 12px;
  background: var(--color-success-50);
  border-radius: 8px;
  border: 1px solid var(--color-success-200);
}
</style>
