<script setup lang="ts">
import type { ManifestEntry } from "../types"

defineProps<{ file: ManifestEntry | null }>()
defineEmits<{ (event: 'close'): void }>()
</script>

<template>
  <div v-if="file" class="modal-backdrop" @click="$emit('close')">
    <div class="modal-content" @click.stop>
      <header class="modal-header">
        <div class="modal-title">{{ file.relPath }}</div>
        <button class="close-btn" @click="$emit('close')">✕</button>
      </header>
      <div class="modal-body">
        <div class="preview-placeholder">
          <div class="icon">📄</div>
          <p>Preview mode is a placeholder now.</p>
          <p style="font-size: 12px; color: #888;">
            Next, this will load the PDF via iframe or text content.
          </p>
          <div style="margin-top: 20px; font-family: monospace; background: #eee; padding: 10px; border-radius: 4px;">
            {{ file.relPath }} ({{ file.fileType }})
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-backdrop {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.4); backdrop-filter: blur(4px);
  z-index: 100; display: flex; align-items: center; justify-content: center;
}
.modal-content {
  width: 80%; height: 85%; background: #fff; border-radius: 12px;
  box-shadow: 0 20px 50px rgba(0,0,0,0.2); display: flex; flex-direction: column;
}
.modal-header {
  padding: 16px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center;
}
.modal-title { font-weight: 600; font-size: 16px; }
.close-btn { background: none; border: none; cursor: pointer; font-size: 20px; color: #888; }
.modal-body { flex: 1; padding: 20px; display: flex; align-items: center; justify-content: center; background: #f9f9f9; }
.preview-placeholder { text-align: center; color: #555; }
.icon { font-size: 48px; margin-bottom: 16px; }
</style>
