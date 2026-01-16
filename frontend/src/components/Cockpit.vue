<script setup lang="ts">
import { ref, reactive, provide, onMounted, onUnmounted, computed, watch, nextTick } from "vue"
import SidePanel from "./SidePanel.vue"
import ChatWindow from "./ChatWindow.vue"
import RightDrawer from "./RightDrawer.vue"
import FilePreviewModal from "./FilePreviewModal.vue"
import ConfirmationModal from "./ConfirmationModal.vue"
import CommandPalette from "./CommandPalette.vue"
import {
  fetchBankManifest,
  fetchProjectFiles,
  streamSummarize,
  activateProject,
  fetchProjects,
  fetchChatSessions,
  fetchChatSession,
  createChatSession,
  updateChatSession,
  deleteChatSession
} from "../api/client"
import type { ChatMessage, EvidenceChunk, ManifestEntry, ChatSession, Project } from "../types"
import { useRouter } from "vue-router"
import { Home, Search, PanelRight } from "lucide-vue-next"

const props = defineProps<{
  id: string
}>()

const router = useRouter()
const project = ref<Project | null>(null)

// UI state
const isDrawerOpen = ref(false)
const drawerTab = ref<"reader" | "notebook">("reader")
const activeEvidence = ref<EvidenceChunk | null>(null)
const showPreviewModal = ref(false)
const previewFile = ref<ManifestEntry | null>(null)
const targetNoteId = ref<string | null>(null)
const highlightedPaths = ref<Set<string>>(new Set())
const showDeleteModal = ref(false)
const pendingDeleteChatId = ref<string | null>(null)

// Data state
const manifest = ref<ManifestEntry[]>([])
// Project Files: files belonging to this project
const projectFiles = ref<Set<string>>(new Set())
// Selected Files: files selected for AI context
const selectedFiles = ref<Set<string>>(new Set())
const selectedNotes = ref<Set<string>>(new Set())

// Search State
const isSearchOpen = ref(false)
const highlightMessageId = ref<string | null>(null)

// Chat + history store (supports switching)
const currentChatId = ref<string | null>(null)
const chatStore = reactive<Record<string, ChatMessage[]>>({})
const chatSessions = ref<ChatSession[]>([])
const isLoadingChats = ref(true)
const savePending = ref(false)
const saveDebounceTimer = ref<ReturnType<typeof setTimeout> | null>(null)

const chatHistory = computed({
  get: () => currentChatId.value ? (chatStore[currentChatId.value] || []) : [],
  set: (val: ChatMessage[]) => {
    if (currentChatId.value) {
      chatStore[currentChatId.value] = val
      debouncedSaveSession()
    }
  }
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

function openNoteLocation(noteId: string) {
  drawerTab.value = "notebook"
  targetNoteId.value = noteId
  isDrawerOpen.value = true
  setTimeout(() => { targetNoteId.value = null }, 500)
}

function setHighlightedPaths(paths: string[]) {
  highlightedPaths.value = new Set(paths)
}

// Debounced save to avoid too many API calls
function debouncedSaveSession() {
  if (saveDebounceTimer.value) {
    clearTimeout(saveDebounceTimer.value)
  }
  savePending.value = true
  saveDebounceTimer.value = setTimeout(async () => {
    await saveCurrentSession()
    savePending.value = false
  }, 1000)
}

async function saveCurrentSession() {
  if (!currentChatId.value) return
  const messages = chatStore[currentChatId.value]
  if (!messages) return

  try {
    await updateChatSession(props.id, currentChatId.value, { messages })
    // Update local session metadata
    const session = chatSessions.value.find(s => s.id === currentChatId.value)
    if (session && messages.length > 0) {
      session.messageCount = messages.length
      session.lastActive = messages[messages.length - 1].timestamp
      session.preview = messages[messages.length - 1].content.slice(0, 50)
    }
  } catch (e) {
    console.error("Failed to save session:", e)
  }
}

async function handleNewChat() {
  try {
    const session = await createChatSession(props.id, "New Chat")
    chatStore[session.id] = []
    chatSessions.value.unshift(session)
    currentChatId.value = session.id
  } catch (e) {
    console.error("Failed to create chat session:", e)
  }
}

function requestDeleteChat(id: string) {
  pendingDeleteChatId.value = id
  showDeleteModal.value = true
}

function cancelDeleteChat() {
  showDeleteModal.value = false
  pendingDeleteChatId.value = null
}

async function confirmDeleteChat() {
  if (pendingDeleteChatId.value) {
    const id = pendingDeleteChatId.value
    try {
      await deleteChatSession(props.id, id)
      const idx = chatSessions.value.findIndex(s => s.id === id)
      if (idx !== -1) chatSessions.value.splice(idx, 1)
      delete chatStore[id]
      if (currentChatId.value === id) {
        if (chatSessions.value.length > 0) {
          currentChatId.value = chatSessions.value[0].id
          // Load messages for the new current session
          await loadSessionMessages(currentChatId.value)
        } else {
          await handleNewChat()
        }
      }
    } catch (e) {
      console.error("Failed to delete chat session:", e)
    }
  }
  cancelDeleteChat()
}

function openPreview(file: ManifestEntry) {
  previewFile.value = file
  showPreviewModal.value = true
}

async function loadSessionMessages(sessionId: string) {
  if (chatStore[sessionId] && chatStore[sessionId].length > 0) {
    // Already loaded
    return
  }
  try {
    const session = await fetchChatSession(props.id, sessionId)
    chatStore[sessionId] = session.messages
  } catch (e) {
    console.error("Failed to load session messages:", e)
    chatStore[sessionId] = []
  }
}

async function switchChat(id: string) {
  // Save current session before switching
  if (currentChatId.value && savePending.value) {
    if (saveDebounceTimer.value) {
      clearTimeout(saveDebounceTimer.value)
      saveDebounceTimer.value = null
    }
    await saveCurrentSession()
    savePending.value = false
  }

  currentChatId.value = id
  await loadSessionMessages(id)
}

function openSearch() {
  isSearchOpen.value = true
}

async function handleSearchNavigate(item: any) {
  if (item.type === 'chat') {
    if (item.data.sessionId) {
      await switchChat(item.data.sessionId)
      await nextTick()
      highlightMessageId.value = item.data.messageId
    }
  } else if (item.type === 'note') {
    openNoteLocation(item.data.chunkId)
  } else if (item.type === 'file') {
    // File navigation: Just close search, file is already in the project
    // User can find it in SidePanel corpus tab
    // TODO: Add file highlighting in SidePanel for better UX
  }
}

function handleKeydown(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
    e.preventDefault()
    openSearch()
  }
}

// Auto-Title Generation Watcher
const titleGeneratingFor = ref<string | null>(null)

watch(chatStore, async (newStore) => {
  const currentId = currentChatId.value
  if (!currentId) return

  const messages = newStore[currentId]
  const session = chatSessions.value.find(s => s.id === currentId)

  if (session && messages && messages.length > 0) {
    session.messageCount = messages.length
    session.lastActive = messages[messages.length - 1].timestamp
    session.preview = messages[messages.length - 1].content.slice(0, 50)

    // Trigger debounced save
    debouncedSaveSession()

    if (messages.length >= 2 && session.title === "New Chat" && titleGeneratingFor.value !== currentId) {
      const aiMsg = messages.find(m => m.role === 'ai')
      if (aiMsg && !aiMsg.isStreaming && aiMsg.content.length > 10) {
        titleGeneratingFor.value = currentId
        session.title = ""
        try {
          await streamSummarize(
            props.id,
            messages,
            (delta) => { session.title += delta },
            async (title) => {
              session.title = title
              titleGeneratingFor.value = null
              // Save the updated title to backend
              try {
                await updateChatSession(props.id, currentId, { title })
              } catch (e) {
                console.error("Failed to save title:", e)
              }
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
provide("deleteChat", requestDeleteChat)
provide("toggleDrawer", toggleDrawer)
provide("openPreview", openPreview)
provide("togglePin", togglePin)
provide("isPinned", isPinned)
provide("pinnedEvidenceMap", pinnedEvidenceMap)
provide("manifest", manifest)
provide("projectFiles", projectFiles)
provide("selectedFiles", selectedFiles)
provide("selectedNotes", selectedNotes)
provide("chatSessions", chatSessions)
provide("setHighlightedPaths", setHighlightedPaths)
provide("currentProject", project)

onMounted(async () => {
  const pid = props.id
  try { await activateProject(pid) } catch (e) { }

  // Load pinned evidence from localStorage (shared across sessions)
  const savedPins = localStorage.getItem(`pinned_evidence_${pid}`)
  if (savedPins) {
    try {
      const parsed = JSON.parse(savedPins)
      pinnedEvidenceMap.value = new Map(parsed)
    } catch (e) { }
  }

  // Load chat sessions from backend
  isLoadingChats.value = true
  try {
    const sessions = await fetchChatSessions(pid)
    chatSessions.value = sessions

    if (sessions.length > 0) {
      // Load the most recent session
      const lastSessionId = localStorage.getItem(`active_chat_id_${pid}`)
      const targetSession = sessions.find(s => s.id === lastSessionId) || sessions[0]
      currentChatId.value = targetSession.id
      await loadSessionMessages(targetSession.id)
    } else {
      // Create a new session if none exist
      await handleNewChat()
    }
  } catch (e) {
    console.error("Failed to load chat sessions:", e)
    // Create a new session on error
    await handleNewChat()
  } finally {
    isLoadingChats.value = false
  }

  try {
    const list = await fetchProjects()
    project.value = list.find(p => p.id === pid) || null
    manifest.value = await fetchBankManifest()
    const pFiles = await fetchProjectFiles(pid)
    projectFiles.value = new Set(pFiles)
    // selectedFiles starts empty as requested
    selectedFiles.value = new Set()
  } catch (e) { console.error(e) }

  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(async () => {
  window.removeEventListener('keydown', handleKeydown)
  // Save any pending changes before unmounting
  if (savePending.value && currentChatId.value) {
    if (saveDebounceTimer.value) {
      clearTimeout(saveDebounceTimer.value)
    }
    await saveCurrentSession()
  }
})

// Save active chat ID to localStorage for persistence across page reloads
watch(() => currentChatId.value, (val) => {
  if (val) localStorage.setItem(`active_chat_id_${props.id}`, val)
})

// Save pinned evidence to localStorage (shared across sessions)
watch(() => pinnedEvidenceMap.value, (val) => {
  localStorage.setItem(`pinned_evidence_${props.id}`, JSON.stringify(Array.from(val.entries())))
}, { deep: true })
</script>

<template>
  <div class="app-container">
    <header class="top-nav">
      <div class="nav-left">
        <button class="nav-home" @click="router.push('/')">
          <Home :size="18" />
        </button>
        <div class="project-info">
          <span class="p-label">Study</span>
          <span class="p-name">{{ project?.name || id }}</span>
        </div>
      </div>
      <div class="nav-center">
        <div class="search-trigger" @click="openSearch">
          <Search :size="16" />
          <span>Search everything in this study... (Ctrl+K)</span>
        </div>
      </div>
      <div class="nav-right">
        <button class="nav-btn" @click="toggleDrawer()">
          <PanelRight :size="18" />
        </button>
      </div>
    </header>

    <div class="main-layout">
      <SidePanel :active-chat-id="currentChatId ?? undefined" :highlighted-paths="highlightedPaths" @preview="openPreview"
        @select-chat="switchChat" @new-chat="handleNewChat" />
      <main class="workspace-shell">
        <ChatWindow v-model:history="chatHistory" :highlight-id="highlightMessageId" />
      </main>
    </div>

    <div class="drawer-overlay" :class="{ open: isDrawerOpen }" @click="toggleDrawer(false)"></div>
    <RightDrawer :class="{ open: isDrawerOpen }" :is-open="isDrawerOpen" :tab="drawerTab" :evidence="activeEvidence"
      :highlight-note-id="targetNoteId" @close="toggleDrawer(false)" />
    <!-- File Preview Modal -->
    <FilePreviewModal v-model="showPreviewModal" :file="previewFile" />

    <!-- Delete Confirmation Modal -->
    <ConfirmationModal v-model="showDeleteModal" title="Delete Chat?"
      message="Are you sure you want to delete this conversation? This action cannot be undone." confirm-text="Delete"
      @confirm="confirmDeleteChat" />

    <CommandPalette :visible="isSearchOpen" :project-files="projectFiles" :pinned-evidence="pinnedEvidenceMap"
      :chat-store="chatStore" :chat-sessions="chatSessions" :manifest="manifest" @close="isSearchOpen = false"
      @navigate="handleSearchNavigate" />
  </div>
</template>

<style scoped>
.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
  background: white;
}

.top-nav {
  height: 56px;
  background: white;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  z-index: 1;
  flex-shrink: 0;
}

.nav-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.nav-home {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  background: var(--color-neutral-95);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.nav-home:hover {
  background: var(--color-neutral-180);
  border-color: var(--accent-color);
  color: var(--accent-color);
}

.project-info {
  display: flex;
  flex-direction: column;
}

.p-label {
  font-size: 10px;
  font-weight: 700;
  color: var(--text-secondary);
  text-transform: uppercase;
}

.p-name {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
}

.nav-center {
  flex: 1;
  display: flex;
  justify-content: center;
  max-width: 500px;
  padding: 0 20px;
}

.search-trigger {
  width: 100%;
  background: var(--color-neutral-160);
  padding: 8px 16px;
  border-radius: 20px;
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1px solid transparent;
}

.search-trigger:hover {
  background: white;
  border-color: var(--accent-color);
}

.nav-right {
  display: flex;
  align-items: center;
}

.nav-btn {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  border: none;
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--text-secondary);
}

.nav-btn:hover {
  background: var(--color-neutral-160);
  color: var(--text-primary);
}

.main-layout {
  display: flex;
  flex: 1;
  overflow: hidden;
  position: relative;
}

.workspace-shell {
  flex: 1;
  background: var(--bg-main);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.drawer-overlay {
  position: fixed;
  inset: 0;
  background: var(--alpha-black-20);
  z-index: 50;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.3s;
}

.drawer-overlay.open {
  opacity: 1;
  pointer-events: auto;
}

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
