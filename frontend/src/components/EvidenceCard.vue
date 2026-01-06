<script setup lang="ts">
import type { EvidenceChunk } from "../types"

defineProps<{ item: EvidenceChunk }>()

defineEmits<{ (event: "focus", item: EvidenceChunk): void }>()
</script>

<template>
  <article class="evidence-card" @click="$emit('focus', item)">
    <div class="evidence-head">
      <span class="evidence-path">{{ item.path }}</span>
      <span class="evidence-score">{{ item.score.toFixed(2) }}</span>
    </div>
    <p class="evidence-text">{{ item.text }}</p>
    <div class="evidence-meta">
      <span v-if="item.page">p.{{ item.page }}</span>
      <span v-if="item.section">{{ item.section }}</span>
      <span class="evidence-chip">{{ item.chunkId }}</span>
    </div>
  </article>
</template>
