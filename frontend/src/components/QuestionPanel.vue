<script setup lang="ts">
import { ref } from "vue"
import type { AnswerBlock, EvidenceChunk } from "../types"
import EvidenceCard from "./EvidenceCard.vue"
import AnswerBlockView from "./AnswerBlock.vue"
import ScopeChips from "./ScopeChips.vue"

defineProps<{ 
  question: string
  scope: string[]
  evidence: EvidenceChunk[]
  answer: AnswerBlock[]
  loading: boolean
}>()

const emit = defineEmits<{ 
  (event: "ask", question: string): void
  (event: "scope", scope: string[]): void
  (event: "focus", evidence: EvidenceChunk): void
  (event: "cite", citation: string): void
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
        <span>{{ evidence.length }} snippets</span>
      </div>
      <div v-if="evidence.length === 0" class="empty-state">
        Evidence will appear here once you ask a question.
      </div>
      <EvidenceCard
        v-for="item in evidence"
        :key="item.chunkId"
        :item="item"
        @focus="emit('focus', item)"
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
