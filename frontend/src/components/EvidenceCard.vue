<script setup lang="ts">
import { computed, inject } from "vue"
import type { EvidenceChunk } from "../types"
import { highlightTerms } from "../utils"

const props = defineProps<{ 
  item: EvidenceChunk
  highlights?: string[]
  selected?: boolean
}>()

defineEmits<{ 
  (event: "focus", item: EvidenceChunk): void
  (event: "toggle", item: EvidenceChunk): void 
}>()

const highlightedText = computed(() => {
  if (!props.highlights || props.highlights.length === 0) return props.item.text
  return highlightTerms(props.item.text, props.highlights)
})
</script>

<template>
  <article 
    class="evidence-card" 
    :class="{ selected: selected }" 
    @click="$emit('focus', item)"
  >
    <div class="evidence-head">
      <div class="head-left">
        <span class="evidence-path">{{ item.path }}</span>
        <span class="evidence-score">{{ item.score.toFixed(2) }}</span>
      </div>
      <button 
        class="pin-btn" 
        :class="{ active: selected }"
        @click.stop="$emit('toggle', item)"
        title="Pin this evidence"
      >
        <svg v-if="selected" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M16 12V4H17V2H7V4H8V12L6 14V16H11V22H13V16H18V14L16 12Z"/></svg>
        <svg v-else xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 12V4H17V2H7V4H8V12L6 14V16H11V22H13V16H18V14L16 12Z"/></svg>
      </button>
    </div>
    
    <p class="evidence-text" v-html="highlightedText"></p>
    
    <div class="evidence-meta">
      <span v-if="item.page">p.{{ item.page }}</span>
      <span v-if="item.section">{{ item.section }}</span>
      <span class="evidence-chip">{{ item.chunkId }}</span>
    </div>
  </article>
</template>
