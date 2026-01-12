<script setup lang="ts">
import { ref, reactive, provide, onMounted, computed } from "vue"
import SidePanel from "./components/SidePanel.vue"
import ChatWindow from "./components/ChatWindow.vue"
import RightDrawer from "./components/RightDrawer.vue"
import FilePreviewModal from "./components/FilePreviewModal.vue"
import { fetchManifest } from "./api/client"
import type { ChatMessage, EvidenceChunk, ManifestEntry } from "./types"

// UI state
const isDrawerOpen = ref(false)
const drawerTab = ref<"reader" | "notebook">("reader")
const activeEvidence = ref<EvidenceChunk | null>(null)
const previewFile = ref<ManifestEntry | null>(null)

// Data state
const manifest = ref<ManifestEntry[]>([])
const selectedFiles = ref<Set<string>>(new Set())

// Chat + history store (supports switching)
const currentChatId = ref("1")
const chatStore = reactive<Record<string, ChatMessage[]>>({
  "1": [],
  "2": [
    { id: "m1", role: "user", content: "What is the main purpose of the assignment?", timestamp: Date.now() - 100000 },
    { id: "m2", role: "ai", content: "The assignment focuses on Object-Oriented Technology...", timestamp: Date.now() - 90000, sources: [] }
  ]
})

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

function handleNewChat() {
  const newId = Date.now().toString()
  chatStore[newId] = []
  currentChatId.value = newId
}

function openPreview(file: ManifestEntry) {
  previewFile.value = file
}

function switchChat(id: string) {
  if (!chatStore[id]) chatStore[id] = []
  currentChatId.value = id
}

// Provide to children
provide("openEvidence", openEvidence)
provide("handleNewChat", handleNewChat)
provide("toggleDrawer", toggleDrawer)
provide("openPreview", openPreview)
provide("togglePin", togglePin)
provide("isPinned", isPinned)
provide("pinnedEvidenceMap", pinnedEvidenceMap)
provide("manifest", manifest)
provide("selectedFiles", selectedFiles)

onMounted(async () => {
  try { manifest.value = await fetchManifest() } catch (e) { console.error(e) }
})
</script>

<template>
  <div class="app-container">
    <!-- Sidebar listens for preview and chat-select events -->
    <SidePanel :active-chat-id="currentChatId" @preview="openPreview" @select-chat="switchChat"
      @new-chat="handleNewChat" />

    <main class="workspace-shell">
      <ChatWindow v-model:history="chatHistory" />
    </main>

    <div class="drawer-overlay" :class="{ open: isDrawerOpen }" @click="toggleDrawer(false)"></div>
    <RightDrawer :class="{ open: isDrawerOpen }" :tab="drawerTab" :evidence="activeEvidence"
      @close="toggleDrawer(false)" />

    <!-- File Preview Modal -->
    <FilePreviewModal v-if="previewFile" :file="previewFile" @close="previewFile = null" />
  </div>
</template>