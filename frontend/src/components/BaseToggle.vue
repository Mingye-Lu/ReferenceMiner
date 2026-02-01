<script setup lang="ts">
import { computed } from "vue";

interface Props {
  modelValue: boolean;
  size?: "small" | "medium";
  disabled?: boolean;
}

interface Emits {
  (e: "update:modelValue", value: boolean): void;
}

const props = withDefaults(defineProps<Props>(), {
  size: "medium",
  disabled: false,
});

const emit = defineEmits<Emits>();

const toggleWidth = computed(() => {
  return props.size === "small" ? "44px" : "52px";
});

const toggleHeight = computed(() => {
  return props.size === "small" ? "24px" : "28px";
});

const thumbSize = computed(() => {
  return props.size === "small" ? "20px" : "24px";
});

// Calculate thumb position
const thumbInset = "2px";

const thumbLeftOff = computed(() => {
  return thumbInset;
});

const thumbLeftOn = computed(() => {
  return `calc(100% - ${thumbSize.value} - ${thumbInset})`;
});

function handleClick() {
  if (!props.disabled) {
    emit("update:modelValue", !props.modelValue);
  }
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    handleClick();
  }
}
</script>

<template>
  <button class="toggle" :class="{ active: modelValue, disabled }" :style="{ width: toggleWidth, height: toggleHeight }"
    :disabled="disabled" @click="handleClick" @keydown="handleKeydown" :aria-checked="modelValue" role="switch"
    tabindex="0">
    <span class="toggle-thumb" :style="{
      width: thumbSize,
      height: thumbSize,
      left: modelValue ? thumbLeftOn : thumbLeftOff,
    }"></span>
  </button>
</template>

<style scoped>
.toggle {
  position: relative;
  background: var(--color-neutral-250);
  border-radius: 8px;
  border: 1px solid var(--border-color);
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  padding: 0;
  display: flex;
  align-items: center;
}

.toggle:hover:not(.disabled) {
  border-color: var(--accent-color);
  background: var(--color-neutral-200);
}

.toggle.active {
  background: var(--accent-color);
  border-color: var(--accent-color);
}

.toggle.active:hover:not(.disabled) {
  background: var(--accent-hover, var(--accent-color));
  border-color: var(--accent-hover, var(--accent-color));
}

.toggle.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.toggle-thumb {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  background: white;
  border-radius: 6px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
  transition: left 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

[data-theme="dark"] .toggle {
  background: var(--color-neutral-600);
  border-color: var(--color-neutral-500);
}

[data-theme="dark"] .toggle:hover:not(.disabled) {
  background: var(--color-neutral-500);
}

[data-theme="dark"] .toggle.active {
  background: var(--accent-color);
  border-color: var(--accent-color);
}

[data-theme="dark"] .toggle.active:hover:not(.disabled) {
  background: var(--accent-hover, var(--accent-bright));
  border-color: var(--accent-hover, var(--accent-bright));
}

[data-theme="dark"] .toggle-thumb {
  background: var(--color-white);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
}
</style>
