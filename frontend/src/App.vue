<script setup lang="ts">
import { onMounted, ref } from "vue"
import CorpusSidebar from "./components/CorpusSidebar.vue"
import IndexStatusBanner from "./components/IndexStatusBanner.vue"
import QuestionPanel from "./components/QuestionPanel.vue"
import ReaderPanel from "./components/ReaderPanel.vue"
import { fetchIndexStatus, fetchManifest, streamAsk } from "./api/client"
import type { AnswerBlock, EvidenceChunk, IndexStatus, ManifestEntry } from "./types"

type TimelineEvent = {
  phase: string
  message: string
  timestamp: string
}

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
const timeline = ref<TimelineEvent[]>([])
const draft = ref("")

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

function pushTimeline(phase: string, message: string) {
  timeline.value.push({ phase, message, timestamp: new Date().toLocaleTimeString() })
}

async function runAsk(input: string) {
  loading.value = true
  focusedCitation.value = null
  question.value = input
  scope.value = []
  evidence.value = []
  answer.value = []
  draft.value = ""
  timeline.value = []

  try {
    errorMessage.value = null
    pushTimeline("ask", "Question received")

    await streamAsk(input, (event, payload) => {
      if (event === "status") {
        pushTimeline(payload.phase ?? "status", payload.message ?? "Working")
      }
      if (event === "analysis") {
        scope.value = payload.scope ?? []
        if ((payload.keywords ?? []).length) {
          pushTimeline("analysis", `Keywords: ${payload.keywords.join(", ")}`)
        }
      }
      if (event === "evidence") {
        evidence.value = (payload ?? []).map((item: any) => ({
          chunkId: item.chunk_id ?? item.chunkId ?? "",
          path: item.path ?? item.rel_path ?? "",
          page: item.page ?? null,
          section: item.section ?? null,
          text: item.text ?? "",
          score: item.score ?? 0,
        }))
        focusedEvidence.value = evidence.value[0] ?? null
        pushTimeline("retrieve", `Selected ${evidence.value.length} evidence chunks`)
      }
      if (event === "llm_delta") {
        draft.value += payload.delta ?? ""
      }
      if (event === "answer_done") {
        answer.value = (payload ?? []).map((block: any) => ({
          heading: block.heading ?? "Answer",
          body: block.body ?? "",
          citations: block.citations ?? [],
        }))
        pushTimeline("final", "Answer ready")
      }
      if (event === "error") {
        errorMessage.value = payload.message ?? "Streaming error"
      }
    })
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to run analysis."
    errorMessage.value = message
  } finally {
    loading.value = false
  }
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
      <CorpusSidebar :manifest="manifest" />

      <QuestionPanel
        :question="question"
        :scope="scope"
        :evidence="evidence"
        :answer="answer"
        :loading="loading"
        :timeline="timeline"
        :draft="draft"
        @ask="runAsk"
        @scope="updateScope"
        @focus="focusEvidence"
        @cite="focusCitation"
      />

      <ReaderPanel :focused="focusedEvidence" :citation="focusedCitation" />
    </main>
  </div>
</template>
