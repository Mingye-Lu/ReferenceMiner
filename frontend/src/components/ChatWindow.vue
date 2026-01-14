<script setup lang="ts">
import { ref, nextTick, watch, inject, type Ref } from "vue"
import MessageItem from "./MessageItem.vue"
import { streamAsk } from "../api/client"
import type { ChatMessage, EvidenceChunk } from "../types"

const props = defineProps<{ history: ChatMessage[] }>()
defineEmits<{ (event: 'update:history', val: ChatMessage[]): void }>()

const draftInput = ref("")
const isLoading = ref(false)
const scrollAnchor = ref<HTMLElement | null>(null)
const scrollContainer = ref<HTMLElement | null>(null)
const userScrolledUp = ref(false)

const selectedFiles = inject<Ref<Set<string>>>("selectedFiles")!
const selectedNotes = inject<Ref<Set<string>>>("selectedNotes")!
const pinnedEvidenceMap = inject<Ref<Map<string, EvidenceChunk>>>("pinnedEvidenceMap")!
const toggleDrawer = inject<(open?: boolean) => void>("toggleDrawer")!

const isNoteMode = ref(false)
function toggleNoteMode() {
  isNoteMode.value = !isNoteMode.value
}

function handleScroll() {
  if (!scrollContainer.value) return
  const { scrollTop, scrollHeight, clientHeight } = scrollContainer.value
  if (scrollHeight - scrollTop - clientHeight > 50) {
    userScrolledUp.value = true
  } else {
    userScrolledUp.value = false
  }
}

function scrollToBottom() {
  if (!userScrolledUp.value) {
    nextTick(() => scrollAnchor.value?.scrollIntoView({ behavior: "auto" }))
  }
}

watch(() => props.history.length, () => {
  userScrolledUp.value = false
  nextTick(() => scrollAnchor.value?.scrollIntoView({ behavior: "smooth" }))
})

async function sendMessage() {
  if (!draftInput.value.trim() || isLoading.value) return
  const question = draftInput.value
  draftInput.value = ""

  userScrolledUp.value = false

  const userMsg: ChatMessage = { id: Date.now().toString(), role: "user", content: question, timestamp: Date.now() }
  props.history.push(userMsg)

  const aiMsgId = (Date.now() + 1).toString()
  const aiMsg: ChatMessage = {
    id: aiMsgId, role: "ai", content: "", timestamp: Date.now(),
    timeline: [], sources: [], keywords: [], isStreaming: true
  }
  props.history.push(aiMsg)
  isLoading.value = true

  try {
    const context = Array.from(selectedFiles.value)

    // Logic: If Note Mode is ON:
    // 1. If individual notes are selected, use ONLY those.
    // 2. If no notes selected, use ALL pinned notes.
    // If Note Mode is OFF:
    // Send empty notes (Server uses RAG on files).
    let notes: EvidenceChunk[] = []
    if (isNoteMode.value) {
      if (selectedNotes.value.size > 0) {
        notes = Array.from(pinnedEvidenceMap.value.values())
          .filter(n => selectedNotes.value.has(n.chunkId))
      } else {
        notes = Array.from(pinnedEvidenceMap.value.values())
      }
    }

    await streamAsk(question, (event, payload) => {
      // ... (keep event handling)
      const currentAiMsg = props.history.find(m => m.id === aiMsgId)
      if (!currentAiMsg) return

      if (event === "status" || event === "analysis") {
        currentAiMsg.timeline?.push({ phase: payload.phase || event, message: payload.message || "Processing...", timestamp: new Date().toLocaleTimeString() })
        if (payload.keywords) currentAiMsg.keywords = payload.keywords
      }
      if (event === "evidence") {
        currentAiMsg.sources = (payload || []).map((item: any) => ({
          chunkId: item.chunk_id ?? item.chunkId, path: item.path ?? item.rel_path,
          page: item.page, section: item.section, text: item.text, score: item.score
        }))
      }
      if (event === "llm_delta") {
        currentAiMsg.content += (payload.delta || "")
        scrollToBottom()
      }
      if (event === "answer_done") {
        currentAiMsg.content = payload.markdown || currentAiMsg.content
        currentAiMsg.isStreaming = false
      }
    }, context, isNoteMode.value, notes)
  } catch (e) {
    const currentAiMsg = props.history.find(m => m.id === aiMsgId)
    if (currentAiMsg) {
      currentAiMsg.content += "\n\n**Error:** Analysis failed."
      currentAiMsg.isStreaming = false
    }
  } finally { isLoading.value = false }
}
</script>

<template>
  <header class="workspace-header">
    <div style="font-weight: 600; font-size: 14px;">Study: Default Project</div>

    <button class="header-icon-btn" @click="toggleDrawer()" title="Toggle Right Panel">
      <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none"
        stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect width="18" height="18" x="3" y="3" rx="2" ry="2" />
        <line x1="15" x2="15" y1="3" y2="21" />
      </svg>
    </button>
  </header>

  <div class="chat-scroll-area" ref="scrollContainer" @scroll="handleScroll">
    <div v-if="history.length === 0" class="empty-welcome">
      <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#e1e1e6"
        stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="margin-bottom:16px">
        <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
        <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
      </svg>
      <h2>Research Cockpit</h2>
      <p>Select files from the sidebar and start your analysis.</p>
    </div>

    <div class="chat-container">
      <MessageItem v-for="msg in history" :key="msg.id" :message="msg" />
    </div>
    <div ref="scrollAnchor" style="height: 1px;"></div>
  </div>

  <div class="input-area-wrapper">
    <div class="context-bar">
      <div class="note-chip" :class="{ active: isNoteMode }" @click="toggleNoteMode">
        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
          style="margin-right: 4px;">
          <path
            d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48">
          </path>
        </svg>
        Use Notes ({{ selectedNotes.size > 0 ? selectedNotes.size + '/' : '' }}{{ pinnedEvidenceMap.size }})
      </div>
      <div class="context-divider"></div>
      <div class="context-label">Context:</div>
      <div class="context-scroll">
        <div v-if="selectedFiles.size === 0" class="file-chip placeholder">
          <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10" />
            <line x1="2" x2="22" y1="12" y2="12" />
            <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
          </svg>
          All files
        </div>
        <div v-else v-for="file in selectedFiles" :key="file" class="file-chip">
          <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
          {{ file.split('/').pop() }}
        </div>
      </div>
    </div>

    <div class="input-box">
      <textarea v-model="draftInput" placeholder="Ask a question..." @keydown.enter.prevent="sendMessage"></textarea>
      <div class="input-footer">
        <span style="font-size: 11px; color: #aaa;">Enter to send</span>
        <button class="btn-primary" :disabled="!draftInput || isLoading" @click="sendMessage">Run Analysis</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.workspace-header {
  height: 56px;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(8px);
  position: sticky;
  top: 0;
  z-index: 20;
}

.header-icon-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--text-secondary);
  padding: 6px;
  border-radius: 6px;
}

.header-icon-btn:hover {
  background: rgba(0, 0, 0, 0.05);
  color: var(--text-primary);
}

.chat-scroll-area {
  flex: 1;
  overflow-y: auto;
  padding: 24px 0;
}

.chat-container {
  max-width: 800px;
  margin: 0 auto;
  width: 100%;
  padding: 0 24px;
}

.empty-welcome {
  text-align: center;
  margin-top: 100px;
  color: var(--text-secondary);
}

.empty-welcome h2 {
  font-family: var(--font-serif);
  color: var(--text-primary);
  margin-bottom: 8px;
}

.input-area-wrapper {
  max-width: 800px;
  margin: 0 auto;
  width: 100%;
  padding: 12px 24px 24px 24px;
  border-top: 1px solid var(--border-color);
}

.context-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  overflow: hidden;
}

.context-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.context-scroll {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  padding-bottom: 2px;
  flex: 1;
  scrollbar-width: none;
}

.file-chip {
  font-size: 11px;
  padding: 4px 10px;
  background: #fff;
  border: 1px solid var(--border-color);
  border-radius: 99px;
  white-space: nowrap;
  color: var(--text-primary);
}

.file-chip.placeholder {
  color: var(--text-secondary);
  border-style: dashed;
}

.note-chip {
  font-size: 11px;
  padding: 4px 10px;
  background: #f1f1f1;
  border: 1px solid transparent;
  border-radius: 99px;
  color: var(--text-secondary);
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.2s;
}

.note-chip.active {
  background: #fff8c5;
  color: #5f4b0e;
  border-color: #ffeba6;
}

.context-divider {
  width: 1px;
  height: 16px;
  background: var(--border-color);
  margin: 0 4px;
}

.input-box {
  background: #fff;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 12px;
  box-shadow: var(--shadow-md);
  transition: border 0.2s;
}

.input-box:focus-within {
  border-color: var(--accent-color);
}

.input-box textarea {
  width: 100%;
  border: none;
  resize: none;
  outline: none;
  font-family: var(--font-main);
  font-size: 14px;
  min-height: 48px;
  max-height: 200px;
}

.input-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
}
</style>