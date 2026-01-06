<script setup lang="ts">
import type { EvidenceChunk } from "../types"

defineProps<{ focused: EvidenceChunk | null; citation: string | null }>()
</script>

<template>
  <aside class="panel reader-panel">
    <header class="panel-header">
      <h2>Reader</h2>
      <p>Jump to cited sections and figures.</p>
    </header>

    <div class="reader-body">
      <div class="reader-highlight" v-if="citation">
        Highlighting: <strong>{{ citation }}</strong>
      </div>

      <div v-if="focused" class="focused-evidence">
        <div class="focused-title">Focused evidence</div>
        <div class="focused-meta">
          <span>{{ focused.path }}</span>
          <span v-if="focused.page">p.{{ focused.page }}</span>
          <span v-if="focused.section">{{ focused.section }}</span>
        </div>
        <p>{{ focused.text }}</p>
      </div>

      <div v-else class="empty-state">
        Select evidence or a citation to preview it here.
      </div>

      <div class="reader-actions">
        <button class="ghost">Open document</button>
        <button class="ghost">Analyze figure</button>
      </div>
    </div>
  </aside>
</template>
