<script setup lang="ts">
import { watch, onMounted, onUnmounted, nextTick } from 'vue'

const props = withDefaults(defineProps<{
  modelValue: boolean
  title?: string
  size?: 'small' | 'medium' | 'large' | 'xlarge' | 'fullscreen'
  hideHeader?: boolean
  hideCloseButton?: boolean
  closeOnClickOutside?: boolean
  closeOnEsc?: boolean
  zIndex?: number
}>(), {
  size: 'medium',
  hideHeader: false,
  hideCloseButton: false,
  closeOnClickOutside: true,
  closeOnEsc: true,
  zIndex: 1300
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'close'): void
}>()

function handleClose() {
  emit('update:modelValue', false)
  emit('close')
}

function handleBackdropClick() {
  if (props.closeOnClickOutside) {
    handleClose()
  }
}

function handleEscKey(event: KeyboardEvent) {
  if (event.key === 'Escape' && props.closeOnEsc && props.modelValue) {
    handleClose()
  }
}

// Body scroll lock
function lockBodyScroll() {
  document.body.style.overflow = 'hidden'
}

function unlockBodyScroll() {
  document.body.style.overflow = ''
}

// Focus trap
let previousActiveElement: HTMLElement | null = null

function setupFocusTrap() {
  previousActiveElement = document.activeElement as HTMLElement
  nextTick(() => {
    const modalElement = document.querySelector('.modal-box') as HTMLElement
    if (modalElement) {
      modalElement.focus()
    }
  })
}

function restoreFocus() {
  if (previousActiveElement) {
    previousActiveElement.focus()
  }
}

// Watch for modal open/close
watch(() => props.modelValue, (isOpen) => {
  if (isOpen) {
    lockBodyScroll()
    setupFocusTrap()
  } else {
    unlockBodyScroll()
    restoreFocus()
  }
})

// Setup keyboard listeners
onMounted(() => {
  document.addEventListener('keydown', handleEscKey)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleEscKey)
  unlockBodyScroll()
})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="modelValue" class="modal-backdrop" :style="{ zIndex: props.zIndex }" @click.self="handleBackdropClick">
        <div class="modal-box" :class="[`modal-${size}`]" role="dialog" aria-modal="true" tabindex="-1">
          <!-- Header -->
          <div v-if="!hideHeader" class="modal-header">
            <slot name="header">
              <div class="header-content">
                <slot name="header-content">
                  <h3 v-if="title" class="modal-title">{{ title }}</h3>
                </slot>
              </div>
              <button v-if="!hideCloseButton" class="close-btn" @click="handleClose" aria-label="Close modal">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none"
                  stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </slot>
          </div>

          <!-- Body -->
          <div class="modal-body">
            <slot></slot>
          </div>

          <!-- Footer -->
          <div v-if="$slots.footer" class="modal-footer">
            <slot name="footer"></slot>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* Backdrop */
.modal-backdrop {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--alpha-black-50);
  backdrop-filter: blur(2px);
  z-index: 1300;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

/* Modal Box */
.modal-box {
  background: var(--color-white);
  border-radius: 12px;
  box-shadow: 0 10px 40px var(--alpha-black-20);
  display: flex;
  flex-direction: column;
  max-height: 90vh;
  outline: none;
  overflow: hidden;
  transition: width 0.2s ease, height 0.2s ease, max-width 0.2s ease, max-height 0.2s ease, border-radius 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease;
}

/* Size variants */
.modal-small {
  width: 90%;
  max-width: 400px;
}

.modal-medium {
  width: 90%;
  max-width: 560px;
}

.modal-large {
  width: 90%;
  max-width: 800px;
}

.modal-xlarge {
  width: 90%;
  max-width: 1200px;
}

.modal-fullscreen {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  width: 100%;
  height: 100%;
  max-width: none;
  max-height: none;
  border-radius: 0;
}

/* Header */
.modal-header {
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}

.header-content {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
}

.modal-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.close-btn {
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

.close-btn:hover {
  background: var(--bg-icon-hover);
  color: var(--text-primary);
}

/* Body */
.modal-body {
  padding: 24px 20px;
  overflow-y: auto;
  flex: 1;
}

/* Footer */
.modal-footer {
  padding: 16px 24px;
  background: var(--bg-panel);
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  flex-shrink: 0;
  border-radius: 0 0 12px 12px;
}

/* Animations - matching FileUploader exactly */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active .modal-box,
.modal-leave-active .modal-box {
  transition: transform 0.2s ease, opacity 0.2s ease;
}

.modal-enter-from .modal-box {
  transform: scale(0.95) translateY(-10px);
  opacity: 0;
}

.modal-leave-to .modal-box {
  transform: scale(0.95) translateY(10px);
  opacity: 0;
}
</style>
