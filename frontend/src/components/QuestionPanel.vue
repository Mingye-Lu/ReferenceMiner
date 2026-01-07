<script setup lang="ts">
import { ref, computed } from "vue"
import type { AnswerBlock, EvidenceChunk } from "../types"
import EvidenceCard from "./EvidenceCard.vue"
import AnswerBlockView from "./AnswerBlock.vue"
import ScopeChips from "./ScopeChips.vue"

defineProps<{ 
  question: string
  scope: string[]
  highlights?: string[]
  evidence: EvidenceChunk[]
  answer: AnswerBlock[]
  loading: boolean
  selectedIds?: Set<string> 
}>()

const emit = defineEmits<{ 
  (event: "ask", question: string): void
  (event: "scope", scope: string[]): void
  (event: "focus", evidence: EvidenceChunk): void
  (event: "cite", citation: string): void
  (event: "toggle-select", evidence: EvidenceChunk): void 
}>()

const draft = ref("")

function submit() {
  if (!draft.value.trim()) return
  emit("ask", draft.value.trim())
}
</script>

<template>
  <section class="panel query-panel">
    <header class="panel-header">
      <h2>Ask</h2>
      <p>Ask questions grounded in your local references.</p>
    </header>

    <div class="question-input">
      <textarea
        v-model="draft"
        rows="3"
        placeholder="Ask a question about your references"
      ></textarea>
      <div class="question-actions">
        <button class="primary" @click="submit" :disabled="loading">
          {{ loading ? "Analyzing..." : "Run analysis" }}
        </button>
        <button class="ghost" @click="draft = ''">Clear</button>
      </div>
    </div>

    <div class="scope-section" v-if="scope.length">
      <h4>Scope</h4>
      <ScopeChips :scope="scope" @update="emit('scope', $event)" />
    </div>

    <div class="evidence-section">
      <div class="section-head">
        <h4>Evidence stream</h4>
        <div class="evidence-stats">
          <span v-if="selectedIds && selectedIds.size > 0" class="selection-count">
            {{ selectedIds.size }} pinned
          </span>
          <span>{{ evidence.length }} snippets</span>
        </div>
      </div>
      <div v-if="evidence.length === 0" class="empty-state">
        Evidence will appear here once you ask a question.
      </div>
      <EvidenceCard
        v-for="item in evidence"
        :key="item.chunkId"
        :item="item"
        :highlights="highlights"
        :selected="selectedIds?.has(item.chunkId) ?? false"
        @focus="emit('focus', item)"
        @toggle="emit('toggle-select', item)"
      />
    </div>

    <div class="answer-section" v-if="answer.length">
      <div class="section-head">
        <h4>Answer</h4>
        <span>Grounded response</span>
      </div>
      <AnswerBlockView
        v-for="block in answer"
        :key="block.heading"
        :block="block"
        @cite="emit('cite', $event)"
      />
    </div>
  </section>
</template>
