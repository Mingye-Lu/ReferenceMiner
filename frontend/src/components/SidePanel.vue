<script setup lang="ts">
import { ref, inject, type Ref, computed } from "vue"
import type { ManifestEntry, ChatSession, EvidenceChunk, Project } from "../types"
import FileUploader from "./FileUploader.vue"
import ConfirmationModal from "./ConfirmationModal.vue"
import AlertModal from "./AlertModal.vue"
import { deleteFile, fetchManifest } from "../api/client"

const activeTab = ref<"corpus" | "chats">("corpus")
const isDeleting = ref<string | null>(null)

// Modal state for file deletion
const showDeleteFileModal = ref(false)
const pendingDeleteFile = ref<ManifestEntry | null>(null)
const showErrorModal = ref(false)
const errorMessage = ref("")
const manifest = inject<Ref<ManifestEntry[]>>("manifest")!
const selectedFiles = inject<Ref<Set<string>>>("selectedFiles")!
const selectedNotes = inject<Ref<Set<string>>>("selectedNotes")!
const pinnedEvidenceMap = inject<Ref<Map<string, EvidenceChunk>>>("pinnedEvidenceMap")!
const chatSessions = inject<Ref<ChatSession[]>>("chatSessions")!
const deleteChat = inject<(id: string) => void>("deleteChat")!
const openNoteLocation = inject<(id: string) => void>("openNoteLocation")!
const currentProject = inject<Ref<Project | null>>("currentProject")!
const projectId = computed(() => currentProject.value?.id || "default")

const props = defineProps<{
  activeChatId?: string
  highlightedPaths?: Set<string>
}>()
const emit = defineEmits<{
  (event: 'preview', file: ManifestEntry): void
  (event: 'select-chat', id: string): void
  (event: 'new-chat'): void
}>()

const notesList = computed(() => Array.from(pinnedEvidenceMap.value.values()))

function toggleFile(path: string) {
  if (selectedFiles.value.has(path)) selectedFiles.value.delete(path)
  else selectedFiles.value.add(path)
}

function toggleNote(id: string) {
  if (selectedNotes.value.has(id)) selectedNotes.value.delete(id)
  else selectedNotes.value.add(id)
}

function handlePreview(file: ManifestEntry, e?: Event) {
  if (e) e.stopPropagation()
  emit('preview', file)
}

function selectChat(id: string) {
  emit('select-chat', id)
}

function handleNewChat() {
  emit('new-chat')
}

function handleDeleteChat(id: string, e: Event) {
  e.stopPropagation()
  deleteChat(id)
}

function formatTime(ts: number) {
  const diff = Date.now() - ts
  if (diff < 60000) return 'Just now'
  if (diff < 3600000) return Math.floor(diff / 60000) + 'm ago'
  if (diff < 86400000) return Math.floor(diff / 3600000) + 'h ago'
  return new Date(ts).toLocaleDateString()
}

async function handleUploadComplete(_entry: ManifestEntry) {
  // Refresh the manifest to include the new file
  try {
    manifest.value = await fetchManifest(projectId.value)
  } catch (e) {
    console.error("Failed to refresh manifest", e)
  }
}

function requestDeleteFile(file: ManifestEntry, e: Event) {
  e.stopPropagation()
  if (isDeleting.value) return
  pendingDeleteFile.value = file
  showDeleteFileModal.value = true
}

function cancelDeleteFile() {
  showDeleteFileModal.value = false
  pendingDeleteFile.value = null
}

async function confirmDeleteFile() {
  if (!pendingDeleteFile.value) return

  const file = pendingDeleteFile.value
  showDeleteFileModal.value = false
  isDeleting.value = file.relPath

  try {
    await deleteFile(projectId.value, file.relPath)
    // Remove from selection
    selectedFiles.value.delete(file.relPath)
    // Refresh manifest
    manifest.value = await fetchManifest(projectId.value)
  } catch (e) {
    console.error("Failed to delete file", e)
    errorMessage.value = e instanceof Error ? e.message : "Unknown error"
    showErrorModal.value = true
  } finally {
    isDeleting.value = null
    pendingDeleteFile.value = null
  }
}

function closeErrorModal() {
  showErrorModal.value = false
  errorMessage.value = ""
}
</script>

<template>
  <aside class="sidebar-shell">
    <div class="brand-area">
      <div class="brand-title">ReferenceMiner</div>
    </div>

    <div class="sidebar-tabs">
      <button class="sidebar-tab-btn" :class="{ active: activeTab === 'corpus' }" @click="activeTab = 'corpus'">
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
          style="margin-right:6px">
          <path d="M20 20a2 2 0 0 0 2-2V8l-6-6H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h14z" />
          <polyline points="14 2 14 8 20 8" />
          <line x1="16" x2="8" y1="13" y2="13" />
          <line x1="16" x2="8" y1="17" y2="17" />
          <polyline points="10 9 9 9 8 9" />
        </svg>
        Corpus
      </button>
      <button class="sidebar-tab-btn" :class="{ active: activeTab === 'chats' }" @click="activeTab = 'chats'">
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
          style="margin-right:6px">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
        Chats
      </button>
    </div>

    <!-- CORPUS TAB -->
    <div class="sidebar-content" v-if="activeTab === 'corpus'">
      <!-- File Uploader -->
      <FileUploader :project-id="projectId" @upload-complete="handleUploadComplete" />

      <!-- Files Section -->
      <div class="section-header" v-if="manifest.length > 0">FILES ({{ manifest.length }})</div>
      <div v-if="manifest.length === 0" class="empty-msg">No files indexed yet. Upload files above.</div>

      <div v-for="file in manifest" :key="file.relPath" class="file-item"
        :class="{ selected: selectedFiles.has(file.relPath), deleting: isDeleting === file.relPath, highlighted: highlightedPaths?.has(file.relPath) }">
        <div @click.stop="toggleFile(file.relPath)" style="display:flex; align-items:center; padding-right:8px;">
          <input type="checkbox" class="custom-checkbox" :checked="selectedFiles.has(file.relPath)" readonly />
        </div>

        <div class="file-info" @click="handlePreview(file)">
          <div class="file-name" :title="file.relPath">{{ file.relPath }}</div>
          <div class="file-meta">{{ file.fileType }} · {{ Math.round((file.sizeBytes || 0) / 1024) }}KB</div>
        </div>

        <div class="file-actions">
          <button class="icon-btn preview-btn" @click="(e) => handlePreview(file, e)" title="Preview">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" />
              <circle cx="12" cy="12" r="3" />
            </svg>
          </button>
          <button class="icon-btn delete-btn" @click="(e) => requestDeleteFile(file, e)" title="Delete"
            :disabled="isDeleting === file.relPath">
            <svg v-if="isDeleting !== file.relPath" xmlns="http://www.w3.org/2000/svg" width="14" height="14"
              viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"
              stroke-linejoin="round">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
            <svg v-else xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="spin">
              <path d="M21 12a9 9 0 1 1-6.219-8.56" />
            </svg>
          </button>
        </div>
      </div>

      <!-- Notes Section -->
      <div class="section-header" style="margin-top: 20px;">PINNED NOTES ({{ notesList.length }})</div>
      <div v-if="notesList.length === 0" class="empty-msg">No pinned notes.</div>

      <div v-for="note in notesList" :key="note.chunkId" class="file-item"
        :class="{ selected: selectedNotes.has(note.chunkId) }">
        <div @click.stop="toggleNote(note.chunkId)" style="display:flex; align-items:center; padding-right:8px;">
          <input type="checkbox" class="custom-checkbox" :checked="selectedNotes.has(note.chunkId)" readonly />
        </div>
        <div class="file-info" @click="openNoteLocation(note.chunkId)">
          <div class="file-name" :title="note.text">{{ note.text.slice(0, 40) }}...</div>
          <div class="file-meta">Page {{ note.page || 1 }}</div>
        </div>
      </div>

    </div>

    <!-- CHATS TAB -->
    <div class="sidebar-content" v-else>
      <button class="new-chat-btn" @click="handleNewChat">
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
          style="margin-right: 6px;">
          <path d="M5 12h14" />
          <path d="M12 5v14" />
        </svg>
        New Chat
      </button>
      <div class="chat-list">
        <div v-for="chat in chatSessions" :key="chat.id" class="chat-item"
          :class="{ active: props.activeChatId === chat.id }" @click="selectChat(chat.id)">
          <div class="chat-content-wrapper">
            <div class="chat-title">{{ chat.title }}</div>
            <div class="chat-meta">{{ formatTime(chat.lastActive) }} · {{ chat.messageCount }} msgs</div>
          </div>
          <button class="delete-chat-btn" @click="handleDeleteChat(chat.id, $event)">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
          </button>
        </div>
      </div>
    </div>

    <!-- Delete File Confirmation Modal -->
    <Transition name="modal">
      <ConfirmationModal
        v-if="showDeleteFileModal && pendingDeleteFile"
        title="Delete File?"
        :message="`Delete &quot;${pendingDeleteFile.relPath}&quot;? This action cannot be undone.`"
        confirm-text="Delete"
        @confirm="confirmDeleteFile"
        @cancel="cancelDeleteFile"
      />
    </Transition>

    <!-- Error Modal -->
    <Transition name="modal">
      <AlertModal
        v-if="showErrorModal"
        title="Delete Failed"
        :message="errorMessage"
        type="error"
        @close="closeErrorModal"
      />
    </Transition>
  </aside>
</template>

<style scoped>
.empty-msg {
  padding: 10px 20px;
  font-size: 12px;
  color: #888;
  text-align: center;
}

.section-header {
  padding: 0 10px 6px 10px;
  font-size: 11px;
  font-weight: 700;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.file-item {
  display: flex;
  gap: 12px;
  padding: 10px;
  border-radius: 8px;
  cursor: pointer;
  align-items: center;
  transition: background 0.1s;
  border: 1px solid transparent;
  margin-bottom: 4px;
}

.file-item:hover {
  background: #fff;
  border-color: var(--border-color);
}

.file-item.selected {
  background: #eef1f8;
  border-color: transparent;
}

.file-item.highlighted {
  background: #fff8e1;
}

.file-info {
  flex: 1;
  overflow: hidden;
}

.file-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-meta {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 2px;
  text-transform: uppercase;
}

.icon-btn {
  background: transparent;
  border: none;
  color: var(--text-secondary);
  padding: 4px;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
}

.icon-btn:hover {
  background: rgba(0, 0, 0, 0.05);
  color: var(--text-primary);
}

.file-actions {
  display: flex;
  gap: 2px;
}

.preview-btn,
.delete-btn {
  opacity: 0;
  transition: opacity 0.2s;
}

.file-item:hover .preview-btn,
.file-item:hover .delete-btn {
  opacity: 1;
}

.delete-btn:hover {
  color: #ff4d4f !important;
}

.delete-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.file-item.deleting {
  opacity: 0.5;
  pointer-events: none;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}

.new-chat-btn {
  width: 100%;
  padding: 10px;
  background: var(--text-primary);
  color: #fff;
  border: none;
  border-radius: 8px;
  margin-bottom: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
}

.chat-item {
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 4px;
  border: 1px solid transparent;
  border: 1px solid transparent;
  transition: all 0.2s;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.chat-content-wrapper {
  flex: 1;
  overflow: hidden;
}

.delete-chat-btn {
  background: transparent;
  border: none;
  color: #ccc;
  cursor: pointer;
  padding: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.chat-item:hover .delete-chat-btn {
  opacity: 1;
}

.delete-chat-btn:hover {
  color: #ff4d4f;
}

.chat-item:hover {
  background: #fff;
  border-color: var(--border-color);
}

.chat-item.active {
  background: #fff;
  border-color: var(--accent-color);
  box-shadow: var(--shadow-sm);
}

.chat-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 4px;
  color: var(--text-primary);
}

.chat-meta {
  font-size: 12px;
  color: var(--text-secondary);
}

/* Modal transition animations */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-active :deep(.modal-box),
.modal-leave-active :deep(.modal-box) {
  transition: transform 0.2s ease, opacity 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from :deep(.modal-box) {
  transform: scale(0.95) translateY(-10px);
  opacity: 0;
}

.modal-leave-to :deep(.modal-box) {
  transform: scale(0.95) translateY(10px);
  opacity: 0;
}
</style>