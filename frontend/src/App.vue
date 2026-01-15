<script setup lang="ts">
import { ref, reactive, provide, onMounted, computed, watch } from "vue"
import SidePanel from "./components/SidePanel.vue"
import ChatWindow from "./components/ChatWindow.vue"
import RightDrawer from "./components/RightDrawer.vue"
import FilePreviewModal from "./components/FilePreviewModal.vue"
import ConfirmationModal from "./components/ConfirmationModal.vue"
import { fetchManifest, streamSummarize } from "./api/client"
import type { ChatMessage, EvidenceChunk, ManifestEntry, ChatSession } from "./types"

// UI state
const isDrawerOpen = ref(false)
const drawerTab = ref<"reader" | "notebook">("reader")
const activeEvidence = ref<EvidenceChunk | null>(null)
const previewFile = ref<ManifestEntry | null>(null)
const targetNoteId = ref<string | null>(null)
const highlightedPaths = ref<Set<string>>(new Set())
const showDeleteModal = ref(false)
const pendingDeleteChatId = ref<string | null>(null)

// Data state
const manifest = ref<ManifestEntry[]>([])
const selectedFiles = ref<Set<string>>(new Set())
const selectedNotes = ref<Set<string>>(new Set())

// Chat + history store (supports switching)
const currentChatId = ref("1")
const chatStore = reactive<Record<string, ChatMessage[]>>({ "1": [] })
const chatSessions = ref<ChatSession[]>([
  { id: "1", title: "New Chat", lastActive: Date.now(), messageCount: 0, preview: "Start a new conversation" }
])

const chatHistory = computed({
  get: () => chatStore[currentChatId.value] || [],
  set: (val: ChatMessage[]) => { chatStore[currentChatId.value] = val }
})

// Global pinning (notebook)
const pinnedEvidenceMap = ref(new Map<string, EvidenceChunk>())

function togglePin(item: EvidenceChunk) {
  const map = pinnedEvidenceMap.value
  if (map.has(item.chunkId)) {
    map.delete(item.chunkId)
  } else {
    map.set(item.chunkId, item)
  }
}

function isPinned(id: string) {
  return pinnedEvidenceMap.value.has(id)
}

// Actions
function toggleDrawer(open?: boolean) {
  isDrawerOpen.value = open ?? !isDrawerOpen.value
}

function openEvidence(item: EvidenceChunk) {
  activeEvidence.value = item
  drawerTab.value = "reader"
  isDrawerOpen.value = true
}

// [新增] 打开并定位笔记
function openNoteLocation(noteId: string) {
  drawerTab.value = "notebook"
  targetNoteId.value = noteId
  isDrawerOpen.value = true
  // 重置 target 避免重复触发滚动，但要在组件响应后
  setTimeout(() => { targetNoteId.value = null }, 500)
}

function setHighlightedPaths(paths: string[]) {
  highlightedPaths.value = new Set(paths)
}

function handleNewChat() {
  const newId = Date.now().toString()
  chatStore[newId] = []
  chatSessions.value.unshift({
    id: newId,
    title: "New Chat",
    lastActive: Date.now(),
    messageCount: 0,
    preview: "Start a new conversation"
  })
  currentChatId.value = newId
}

// [新增] 删除对话
// [新增] 请求删除 (唤起 Modal)
function requestDeleteChat(id: string) {
  pendingDeleteChatId.value = id
  showDeleteModal.value = true
}

function cancelDeleteChat() {
  showDeleteModal.value = false
  pendingDeleteChatId.value = null
}

function confirmDeleteChat() {
  if (pendingDeleteChatId.value) {
    const id = pendingDeleteChatId.value
    // Logic from previous deleteChat
    const idx = chatSessions.value.findIndex(s => s.id === id)
    if (idx !== -1) chatSessions.value.splice(idx, 1)
    delete chatStore[id]
    if (currentChatId.value === id) {
      if (chatSessions.value.length > 0) currentChatId.value = chatSessions.value[0].id
      else handleNewChat()
    }
  }
  cancelDeleteChat()
}

function openPreview(file: ManifestEntry) {
  previewFile.value = file
}

function switchChat(id: string) {
  if (!chatStore[id]) chatStore[id] = []
  currentChatId.value = id
}

// Auto-Title Generation Watcher
const titleGeneratingFor = ref<string | null>(null)

watch(chatStore, async (newStore) => {
  const currentId = currentChatId.value
  const messages = newStore[currentId]
  const session = chatSessions.value.find(s => s.id === currentId)

  if (session && messages.length > 0) {
    session.messageCount = messages.length
    session.lastActive = messages[messages.length - 1].timestamp
    session.preview = messages[messages.length - 1].content.slice(0, 50)

    // Generate title if it's the first interaction
    if (messages.length >= 2 && session.title === "New Chat" && titleGeneratingFor.value !== currentId) {
      // Check if the second message (AI) is not empty/streaming done
      const aiMsg = messages.find(m => m.role === 'ai')
      if (aiMsg && !aiMsg.isStreaming && aiMsg.content.length > 10) {
        titleGeneratingFor.value = currentId
        session.title = ""
        try {
          await streamSummarize(
            messages,
            (delta) => { session.title += delta },
            (title) => {
              session.title = title
              titleGeneratingFor.value = null
            }
          )
        } catch (e) {
          console.error("Failed to generate title", e)
          session.title = "New Chat"
          titleGeneratingFor.value = null
        }
      }
    }
  }
}, { deep: true })

// Provide to children
provide("openEvidence", openEvidence)
provide("openNoteLocation", openNoteLocation)
provide("handleNewChat", handleNewChat)
provide("deleteChat", requestDeleteChat) // Provide request function
provide("toggleDrawer", toggleDrawer)
provide("openPreview", openPreview)
provide("togglePin", togglePin)
provide("isPinned", isPinned)
provide("pinnedEvidenceMap", pinnedEvidenceMap)
provide("manifest", manifest)
provide("selectedFiles", selectedFiles)
provide("selectedNotes", selectedNotes)
provide("chatSessions", chatSessions)
provide("setHighlightedPaths", setHighlightedPaths)

onMounted(async () => {
  // Load state from localStorage
  const savedChatId = localStorage.getItem("active_chat_id")
  if (savedChatId) currentChatId.value = savedChatId

  const savedChats = localStorage.getItem("chat_store")
  if (savedChats) {
    try {
      const parsed = JSON.parse(savedChats)
      Object.assign(chatStore, parsed)
    } catch (e) {
      console.error("Failed to load chat history", e)
    }
  }

  const savedSessions = localStorage.getItem("chat_sessions")
  if (savedSessions) {
    try {
      chatSessions.value = JSON.parse(savedSessions)
    } catch (e) { console.error(e) }
  }

  const savedPins = localStorage.getItem("pinned_evidence")
  if (savedPins) {
    try {
      const parsed = JSON.parse(savedPins)
      pinnedEvidenceMap.value = new Map(parsed)
    } catch (e) {
      console.error("Failed to load pins", e)
    }
  }

  try { manifest.value = await fetchManifest() } catch (e) { console.error(e) }
})

// Persistence watchers
watch(currentChatId, (val) => localStorage.setItem("active_chat_id", val))
watch(chatStore, (val) => localStorage.setItem("chat_store", JSON.stringify(val)), { deep: true })
watch(chatSessions, (val) => localStorage.setItem("chat_sessions", JSON.stringify(val)), { deep: true })
watch(pinnedEvidenceMap, (val) => {
  localStorage.setItem("pinned_evidence", JSON.stringify(Array.from(val.entries())))
}, { deep: true })
</script>

<template>
  <div class="app-container">
    <!-- Sidebar listens for preview and chat-select events -->
    <SidePanel :active-chat-id="currentChatId" :highlighted-paths="highlightedPaths" @preview="openPreview"
      @select-chat="switchChat" @new-chat="handleNewChat" />

    <main class="workspace-shell">
      <ChatWindow v-model:history="chatHistory" />
    </main>

    <div class="drawer-overlay" :class="{ open: isDrawerOpen }" @click="toggleDrawer(false)"></div>
    <RightDrawer :class="{ open: isDrawerOpen }" :tab="drawerTab" :evidence="activeEvidence"
      :highlight-note-id="targetNoteId" @close="toggleDrawer(false)" />

    <!-- File Preview Modal -->
    <Transition name="modal">
      <FilePreviewModal v-if="previewFile" :file="previewFile" @close="previewFile = null" />
    </Transition>

    <!-- Delete Confirmation Modal -->
    <Transition name="modal">
      <ConfirmationModal v-if="showDeleteModal" title="Delete Chat?"
        message="Are you sure you want to delete this conversation? This action cannot be undone." confirm-text="Delete"
        @confirm="confirmDeleteChat" @cancel="cancelDeleteChat" />
    </Transition>
  </div>
</template>

<style scoped>
/* Modal transition animations */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-active :deep(.modal-box),
.modal-enter-active :deep(.modal-content),
.modal-leave-active :deep(.modal-box),
.modal-leave-active :deep(.modal-content) {
  transition: transform 0.2s ease, opacity 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from :deep(.modal-box),
.modal-enter-from :deep(.modal-content) {
  transform: scale(0.95) translateY(-10px);
  opacity: 0;
}

.modal-leave-to :deep(.modal-box),
.modal-leave-to :deep(.modal-content) {
  transform: scale(0.95) translateY(10px);
  opacity: 0;
}
</style>