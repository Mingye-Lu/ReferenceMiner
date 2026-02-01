<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from "vue";
import { ChevronDown } from "lucide-vue-next";

interface Option {
  value: string;
  label: string;
}

const props = defineProps<{
  modelValue: string;
  options: Option[];
  placeholder?: string;
}>();

const emit = defineEmits<{
  (event: "update:modelValue", value: string): void;
}>();

const isOpen = ref(false);
const wrapperRef = ref<HTMLDivElement | null>(null);

const selectedOption = computed(() => {
  return props.options.find((opt) => opt.value === props.modelValue);
});

const displayLabel = computed(() => {
  return selectedOption.value?.label || props.placeholder || "Select...";
});

function selectOption(option: Option) {
  emit("update:modelValue", option.value);
  isOpen.value = false;
}

function toggleDropdown() {
  isOpen.value = !isOpen.value;
}

function handleClickOutside(event: MouseEvent) {
  if (wrapperRef.value && !wrapperRef.value.contains(event.target as Node)) {
    isOpen.value = false;
  }
}

function handleEscape(event: KeyboardEvent) {
  if (event.key === "Escape") {
    isOpen.value = false;
  }
}

onMounted(() => {
  document.addEventListener("click", handleClickOutside);
  document.addEventListener("keydown", handleEscape);
});

onBeforeUnmount(() => {
  document.removeEventListener("click", handleClickOutside);
  document.removeEventListener("keydown", handleEscape);
});
</script>

<template>
  <div ref="wrapperRef" class="custom-select-wrapper" :class="{ open: isOpen }">
    <div class="custom-select-trigger" @click="toggleDropdown">
      <span class="custom-select-label">{{ displayLabel }}</span>
      <div class="custom-select-arrow">
        <ChevronDown :size="16" />
      </div>
    </div>
    <transition name="custom-select">
      <div v-if="isOpen" class="custom-options">
        <div
          v-for="option in options"
          :key="option.value"
          class="custom-option"
          :class="{ selected: option.value === modelValue }"
          @click="selectOption(option)"
        >
          {{ option.label }}
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.custom-select-wrapper {
  position: relative;
  width: auto;
  min-width: 160px;
}

.custom-select-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: var(--bg-input);
  border: 1px solid var(--color-neutral-250);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  min-width: 200px;
}

.custom-select-trigger:hover {
  border-color: var(--accent-color);
}

.custom-select-wrapper.open .custom-select-trigger {
  border-color: var(--accent-color);
  box-shadow: 0 0 0 2px var(--alpha-accent-10);
}

.custom-select-label {
  font-size: 14px;
  color: var(--text-primary);
  flex: 1;
}

.custom-select-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  transition: transform 0.2s;
  margin-left: 8px;
}

.custom-select-wrapper.open .custom-select-arrow {
  transform: rotate(180deg);
}

.custom-options {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  background: var(--bg-panel);
  border: 1px solid var(--color-neutral-250);
  border-radius: 8px;
  box-shadow: 0 4px 12px var(--alpha-black-10);
  z-index: 1000;
  max-height: 300px;
  overflow-y: auto;
  animation: slideDown 0.15s ease-out;
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-8px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.custom-select-enter-active,
.custom-select-leave-active {
  transition:
    opacity 0.16s ease,
    transform 0.16s ease;
}

.custom-select-enter-from,
.custom-select-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

.custom-select-enter-to,
.custom-select-leave-from {
  opacity: 1;
  transform: translateY(0);
}

.custom-option {
  padding: 10px 12px;
  font-size: 14px;
  color: var(--text-primary);
  cursor: pointer;
  transition: all 0.15s;
}

.custom-option:hover {
  background: var(--color-neutral-100);
}

.custom-option.selected {
  background: var(--accent-soft);
  color: var(--accent-color);
  font-weight: 500;
}

.custom-option.selected:hover {
  background: var(--accent-soft);
}

/* Scrollbar styling - smaller width for dropdown */
.custom-options::-webkit-scrollbar {
  width: 6px;
}

.custom-options::-webkit-scrollbar-track {
  background: var(--scrollbar-track);
}

.custom-options::-webkit-scrollbar-thumb {
  background: var(--scrollbar-thumb);
  border-radius: 3px;
}

.custom-options::-webkit-scrollbar-thumb:hover {
  background: var(--scrollbar-thumb-hover);
}
</style>
