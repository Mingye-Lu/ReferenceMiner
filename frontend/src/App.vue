<script setup lang="ts">
import { onMounted, ref, computed } from "vue"
import CorpusSidebar from "./components/CorpusSidebar.vue"
import IndexStatusBanner from "./components/IndexStatusBanner.vue"
import QuestionPanel from "./components/QuestionPanel.vue"
import ReaderPanel from "./components/ReaderPanel.vue"
import { askQuestion, fetchIndexStatus, fetchManifest } from "./api/client"
import type { AnswerBlock, EvidenceChunk, IndexStatus, ManifestEntry } from "./types"

const manifest = ref<ManifestEntry[]>([])
const status = ref<IndexStatus | null>(null)
const question = ref("")
const scope = ref<string[]>([])
const evidence = ref<EvidenceChunk[]>([])
const answer = ref<AnswerBlock[]>([])
const focusedEvidence = ref<EvidenceChunk | null>(null)
const focusedCitation = ref<string | null>(null)
const loading = ref(false)
const mode = ref<"hybrid" | "text" | "visual">("hybrid")
const errorMessage = ref<string | null>(null)
const keywords = ref<string[]>([])
const selectedChunkIds = ref<Set<string>>(new Set())

const evidenceCounts = computed(() => {
  const counts: Record<string, number> = {}
  for (const item of evidence.value) {
    counts[item.path] = (counts[item.path] || 0) + 1
  }
  return counts
})

async function loadManifest() {
  try {
    errorMessage.value = null
    manifest.value = await fetchManifest()
    status.value = await fetchIndexStatus()
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to load manifest."
    errorMessage.value = message
    status.value = { indexed: false }
  }
}

async function runAsk(input: string) {
  loading.value = true
  focusedCitation.value = null
  selectedChunkIds.value.clear()
  try {
    errorMessage.value = null
    const response = await askQuestion(input)
    question.value = response.question
    scope.value = response.scope
    keywords.value = response.keywords
    evidence.value = response.evidence
    answer.value = response.answer
    focusedEvidence.value = response.evidence[0] ?? null
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to run analysis."
    errorMessage.value = message
  } finally {
    loading.value = false
  }
}

function toggleSelection(item: EvidenceChunk) {
  if (selectedChunkIds.value.has(item.chunkId)) {
    selectedChunkIds.value.delete(item.chunkId)
  } else {
    selectedChunkIds.value.add(item.chunkId)
  }
  selectedChunkIds.value = new Set(selectedChunkIds.value)
}

function updateScope(next: string[]) {
  scope.value = next
}

function focusEvidence(item: EvidenceChunk) {
  focusedEvidence.value = item
}

function focusCitation(citation: string) {
  focusedCitation.value = citation
}

onMounted(() => {
  loadManifest()
})
</script>

<template>
  <div class="app-shell">
    <header class="top-bar">
      <div class="brand">
        <span class="brand-title">ReferenceMiner</span>
        <span class="brand-subtitle">Local-first research cockpit</span>
      </div>
      <div class="mode-toggle">
        <button :class="{ active: mode === 'text' }" @click="mode = 'text'">Text-first</button>
        <button :class="{ active: mode === 'hybrid' }" @click="mode = 'hybrid'">Hybrid</button>
        <button :class="{ active: mode === 'visual' }" @click="mode = 'visual'">Visual-first</button>
      </div>
    </header>

    <IndexStatusBanner :status="status" />
    <div v-if="errorMessage" class="error-banner">
      {{ errorMessage }}
    </div>

    <main class="grid">
      <CorpusSidebar 
        :manifest="manifest" 
        :counts="evidenceCounts" 
      />

      <QuestionPanel
        :question="question"
        :scope="scope"
        :evidence="evidence"
        :answer="answer"
        :loading="loading"
        :highlights="keywords"
        :selected-ids="selectedChunkIds" 
        @ask="runAsk"
        @scope="updateScope"
        @focus="focusEvidence"
        @cite="focusCitation"
        @toggle-select="toggleSelection"
      />

      <ReaderPanel 
        :focused="focusedEvidence" 
        :citation="focusedCitation" 
        :highlights="keywords"
      />
    </main>
  </div>
</template>
