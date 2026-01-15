<script setup lang="ts">
import { ref, inject, type Ref, computed } from "vue"
import type { ManifestEntry, ChatSession, EvidenceChunk, Project } from "../types"
import FileUploader from "./FileUploader.vue"
import BankFileSelectorModal from "./BankFileSelectorModal.vue"
import ConfirmationModal from "./ConfirmationModal.vue"
import AlertModal from "./AlertModal.vue"
import { fetchBankManifest, fetchProjectFiles, selectProjectFiles, removeProjectFiles } from "../api/client"

const activeTab = ref<"corpus" | "chats">("corpus")
const isDeleting = ref<string | null>(null)


const showDeleteFileModal = ref(false)
const pendingDeleteFile = ref<ManifestEntry | null>(null)
const showErrorModal = ref(false)
const errorMessage = ref("")


const batchMode = ref(false)
const batchSelected = ref<Set<string>>(new Set())
const showBatchDeleteModal = ref(false)
const isBatchDeleting = ref(false)

const aiSelectionBackup = ref<Set<string>>(new Set())
const manifest = inject<Ref<ManifestEntry[]>>("manifest")!
const projectFiles = inject<Ref<Set<string>>>("projectFiles")!
const selectedFiles = inject<Ref<Set<string>>>("selectedFiles")!
const selectedNotes = inject<Ref<Set<string>>>("selectedNotes")!
const pinnedEvidenceMap = inject<Ref<Map<string, EvidenceChunk>>>("pinnedEvidenceMap")!
const chatSessions = inject<Ref<ChatSession[]>>("chatSessions")!
const deleteChat = inject<(id: string) => void>("deleteChat")!
const currentProject = inject<Ref<Project | null>>("currentProject")!
const openEvidence = inject<(item: EvidenceChunk) => void>("openEvidence")!
const projectId = computed(() => currentProject.value?.id || "default")


const showBankSelector = ref(false)

const showUnpinNoteModal = ref(false)
const pendingUnpinNote = ref<EvidenceChunk | null>(null)

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


const displayedFiles = computed(() => {
  if (!projectFiles.value) return []
  return manifest.value.filter(f => projectFiles.value.has(f.relPath))
})

async function handleUploadComplete(_entry: ManifestEntry) {
  // Refresh the manifest and project files
  try {
    manifest.value = await fetchBankManifest()
    const currentFiles = await fetchProjectFiles(projectId.value)
    // Update the list of files in the project
    projectFiles.value = new Set(currentFiles)

    // Do NOT auto-select the new file (User requirement)
    // Do NOT reset selectedFiles (User requirement)
  } catch (e) {
    console.error("Failed to refresh manifest", e)
  }
}

function openBankSelector() {
  showBankSelector.value = true
}



async function handleBankFilesSelected(files: string[]) {
  // Update project files: replace with new set
  projectFiles.value = new Set(files)
  showBankSelector.value = false

  // Persist to backend
  selectProjectFiles(projectId.value, files).catch(console.error)
}

function toggleNote(id: string) {
  if (selectedNotes.value.has(id)) selectedNotes.value.delete(id)
  else selectedNotes.value.add(id)
}

// Jump to note in Reader tab
function jumpToNoteInReader(note: EvidenceChunk, e: Event) {
  e.stopPropagation()
  // Use openEvidence to open in Reader tab
  openEvidence(note)
}

// Request to unpin a note (with confirmation)
function requestUnpinNote(note: EvidenceChunk, e: Event) {
  e.stopPropagation()
  pendingUnpinNote.value = note
  showUnpinNoteModal.value = true
}

// Confirm unpin note
function confirmUnpinNote() {
  if (!pendingUnpinNote.value) return
  try {
    // Remove from pinned evidence map
    pinnedEvidenceMap.value.delete(pendingUnpinNote.value.chunkId)
    // Trigger reactivity
    pinnedEvidenceMap.value = new Map(pinnedEvidenceMap.value)
    // Also remove from selected notes if it was selected
    selectedNotes.value.delete(pendingUnpinNote.value.chunkId)
    selectedNotes.value = new Set(selectedNotes.value)
    showUnpinNoteModal.value = false
    pendingUnpinNote.value = null
  } catch (err) {
    console.error("Failed to unpin note:", err)
  }
}

// Cancel unpin note
function cancelUnpinNote() {
  showUnpinNoteModal.value = false
  pendingUnpinNote.value = null
}

function toggleFile(path: string) {
  try {
    if (selectedFiles.value.has(path)) {
      selectedFiles.value.delete(path)
    } else {
      selectedFiles.value.add(path)
    }
    // Trigger reactivity
    selectedFiles.value = new Set(selectedFiles.value)
  } catch (e) {
    console.error("Failed to toggle file selection", e)
  }
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


async function requestDeleteFile(file: ManifestEntry, e: Event) {
  e.stopPropagation()
  pendingDeleteFile.value = file
  showDeleteFileModal.value = true
}

function cancelDeleteFile() {
  showDeleteFileModal.value = false
  pendingDeleteFile.value = null
}

async function confirmDeleteFile() {
  if (!pendingDeleteFile.value) return
  try {
    isDeleting.value = pendingDeleteFile.value.relPath
    // Remove from project
    await removeProjectFiles(projectId.value, [pendingDeleteFile.value.relPath])

    // Update local state
    projectFiles.value.delete(pendingDeleteFile.value.relPath)
    projectFiles.value = new Set(projectFiles.value)

    selectedFiles.value.delete(pendingDeleteFile.value.relPath)
    selectedFiles.value = new Set(selectedFiles.value)

    showDeleteFileModal.value = false
    pendingDeleteFile.value = null
  } catch (err) {
    console.error("Failed to remove file from project:", err)
    errorMessage.value = err instanceof Error ? err.message : "Unknown error"
    showErrorModal.value = true
  } finally {
    isDeleting.value = null
  }
}

function closeErrorModal() {
  showErrorModal.value = false
  errorMessage.value = ""
}

// Batch delete functions
function toggleBatchMode() {
  if (batchMode.value) {
    cancelBatchMode()
  } else {
    startBatchMode()
  }
}

function startBatchMode() {
  // Backup AI selection
  aiSelectionBackup.value = new Set(selectedFiles.value)
  // Clear AI selection visually (actual state cleared temporarily or just visually overridden?)
  // We'll visually override in template, but to be safe let's clear selectedFiles so checkboxes don't confuse
  // actually, let's keep selectedFiles as is, but in template use batchSelected for style
  batchMode.value = true
}

function cancelBatchMode() {
  batchMode.value = false
  batchSelected.value.clear()
  // No need to restore if we didn't touch selectedFiles, but wait
  // If we want "pure" batch selection state, we should rely on template logic
}

function toggleBatchSelect(path: string) {
  if (batchSelected.value.has(path)) {
    batchSelected.value.delete(path)
  } else {
    batchSelected.value.add(path)
  }
  batchSelected.value = new Set(batchSelected.value)
}

function selectAllForBatch() {
  if (batchSelected.value.size === displayedFiles.value.length) {
    batchSelected.value.clear()
  } else {
    batchSelected.value = new Set(displayedFiles.value.map(f => f.relPath))
  }
}

function requestBatchDelete() {
  if (batchSelected.value.size === 0) return
  showBatchDeleteModal.value = true
}

function cancelBatchDelete() {
  showBatchDeleteModal.value = false
}

async function confirmBatchDelete() {
  if (batchSelected.value.size === 0) return
  try {
    isBatchDeleting.value = true
    const filesToRemove = Array.from(batchSelected.value)

    // Remove from project
    await removeProjectFiles(projectId.value, filesToRemove)

    // Update local state
    // 1. Remove from projectFiles
    for (const f of filesToRemove) projectFiles.value.delete(f)
    projectFiles.value = new Set(projectFiles.value)

    // 2. Remove from selectedFiles (AI context) if present
    for (const f of filesToRemove) selectedFiles.value.delete(f)
    selectedFiles.value = new Set(selectedFiles.value)

    // 3. Update backup if we were backing up (not strictly needed if we didn't clear selectedFiles)

    batchSelected.value.clear()
    showBatchDeleteModal.value = false
    batchMode.value = false

    // Refresh manifest not needed for removal from project, but maybe good practice
    // manifest.value = await fetchBankManifest() // Not strictly needed as files stay in bank
  } catch (err) {
    console.error("Failed to remove files from project:", err)
    errorMessage.value = err instanceof Error ? err.message : "Unknown error"
    showErrorModal.value = true
  } finally {
    isBatchDeleting.value = false
  }
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
      <FileUploader :project-id="projectId" upload-mode="project" @upload-complete="handleUploadComplete" />

      <!-- Add from Bank Button -->
      <button class="add-files-btn" @click="openBankSelector">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="7 10 12 15 17 10" />
          <line x1="12" y1="15" x2="12" y2="3" />
        </svg>
        Manage Project Files
      </button>

      <!-- Files Section -->
      <div class="section-header-row" v-if="displayedFiles.length > 0">
        <div class="section-header">PROJECT FILES ({{ displayedFiles.length }})</div>
        <button class="batch-toggle-btn" :class="{ active: batchMode }" @click="toggleBatchMode"
          :title="batchMode ? 'Exit Batch Mode' : 'Batch Selection'">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="3" width="7" height="7"></rect>
            <rect x="14" y="3" width="7" height="7"></rect>
            <rect x="14" y="14" width="7" height="7"></rect>
            <rect x="3" y="14" width="7" height="7"></rect>
          </svg>
        </button>
      </div>

      <!-- Batch Action Toolbar (Below Header) -->
      <div v-if="batchMode && displayedFiles.length > 0" class="batch-toolbar">
        <button class="batch-tool-btn" @click="selectAllForBatch">
          {{ batchSelected.size === displayedFiles.length ? 'Deselect All' : 'Select All' }}
        </button>
        <div style="flex:1"></div>
        <button class="batch-tool-btn delete" @click="requestBatchDelete" :disabled="batchSelected.size === 0">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="3 6 5 6 21 6"></polyline>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
          </svg>
          Remove ({{ batchSelected.size }})
        </button>
      </div>

      <!-- Batch Action Bar -->
      <!-- This section is now integrated into the section-header-row -->
      <!-- <div v-if="batchMode && displayedFiles.length > 0" class="batch-action-bar">
        <button class="batch-select-all" @click="selectAllForBatch">
          {{ batchSelected.size === displayedFiles.length ? 'Deselect All' : 'Select All' }}
        </button>
        <button class="batch-delete-btn" @click="requestBatchDelete"
          :disabled="batchSelected.size === 0 || isBatchDeleting">
          <svg v-if="!isBatchDeleting" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"
            fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="spin">
            <path d="M21 12a9 9 0 1 1-6.219-8.56" />
          </svg>
          Remove ({{ batchSelected.size }})
        </button>
      </div> -->

      <div v-if="displayedFiles.length === 0" class="empty-msg">No files selected. Click "Add from Reference Bank" to
        add files.</div>

      <div v-for="file in displayedFiles" :key="file.relPath" class="file-item" :class="{
        deleting: isDeleting === file.relPath || (isBatchDeleting && batchSelected.has(file.relPath)),
        highlighted: highlightedPaths?.has(file.relPath),
        selected: batchMode ? batchSelected.has(file.relPath) : selectedFiles.has(file.relPath),
        'batch-mode': batchMode && batchSelected.has(file.relPath)
      }">

        <!-- Checkbox: Show AI selection in normal mode, Batch selection in batch mode -->
        <div class="checkbox-wrapper"
          @click.stop="batchMode ? toggleBatchSelect(file.relPath) : toggleFile(file.relPath)">
          <input type="checkbox" class="custom-checkbox"
            :checked="batchMode ? batchSelected.has(file.relPath) : selectedFiles.has(file.relPath)" readonly />
        </div>

        <div class="file-info" @click="batchMode ? toggleBatchSelect(file.relPath) : toggleFile(file.relPath)">
          <div class="file-name" :title="file.relPath">{{ file.relPath }}</div>
          <div class="file-meta">{{ file.fileType }} · {{ Math.round((file.sizeBytes || 0) / 1024) }}KB</div>
        </div>

        <div class="file-actions" v-if="!batchMode">
          <button class="icon-btn preview-btn" @click="(e) => handlePreview(file, e)" title="Preview">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" />
              <circle cx="12" cy="12" r="3" />
            </svg>
          </button>
          <button class="icon-btn delete-btn" @click="(e) => requestDeleteFile(file, e)" title="Remove from project"
            :disabled="isDeleting === file.relPath">
            <svg v-if="isDeleting !== file.relPath" xmlns="http://www.w3.org/2000/svg" width="14" height="14"
              viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"
              stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
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

        <!-- Checkbox for AI selection -->
        <div @click.stop="toggleNote(note.chunkId)" style="display:flex; align-items:center;"
          title="Select for AI context">
          <input type="checkbox" class="custom-checkbox" :checked="selectedNotes.has(note.chunkId)" readonly />
        </div>

        <!-- Note info - click to toggle selection -->
        <div class="file-info" @click="toggleNote(note.chunkId)">
          <div class="file-name" :title="note.text">{{ note.text.slice(0, 40) }}...</div>
          <div class="file-meta">Page {{ note.page || 1 }}</div>
        </div>

        <!-- Note actions -->
        <div class="file-actions">
          <!-- Jump to Reader button -->
          <button class="icon-btn preview-btn" @click="(e) => jumpToNoteInReader(note, e)" title="View in Reader">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
              <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
            </svg>
          </button>

          <!-- Unpin button -->
          <button class="icon-btn delete-btn" @click="(e) => requestUnpinNote(note, e)" title="Unpin note">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
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
      <ConfirmationModal v-if="showDeleteFileModal && pendingDeleteFile" title="Remove File?"
        :message="`Remove \&quot;${pendingDeleteFile.relPath}\&quot; from this project? The file will remain in the Reference Bank.`"
        confirmText="Remove" @confirm="confirmDeleteFile" @cancel="cancelDeleteFile" />
    </Transition>

    <!-- Batch Delete Confirmation Modal -->
    <Transition name="modal">
      <ConfirmationModal v-if="showBatchDeleteModal && batchSelected.size > 0" title="Remove Files?"
        :message="`Remove ${batchSelected.size} files from this project? They will remain in the Reference Bank.`"
        confirmText="Remove" @confirm="confirmBatchDelete" @cancel="cancelBatchDelete" />
    </Transition>

    <!-- Unpin Note Confirmation Modal -->
    <Transition name="modal">
      <ConfirmationModal v-if="showUnpinNoteModal && pendingUnpinNote" title="Unpin Note?"
        :message="`Unpin note: &quot;${pendingUnpinNote.text.slice(0, 50)}${pendingUnpinNote.text.length > 50 ? '...' : ''}&quot;?`"
        confirmText="Unpin" @confirm="confirmUnpinNote" @cancel="cancelUnpinNote" />
    </Transition>

    <!-- Bank File Selector Modal -->
    <Transition name="modal">
      <BankFileSelectorModal v-if="showBankSelector" :project-id="projectId" :selected-files="projectFiles"
        @close="showBankSelector = false" @confirm="handleBankFilesSelected" />
    </Transition>

    <!-- Error Alert Modal -->
    <Transition name="modal">
      <AlertModal v-if="showErrorModal" title="Delete Failed" :message="errorMessage" type="error"
        @close="closeErrorModal" />
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

.info-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  margin-bottom: 16px;
  background: #e3f2fd;
  border: 1px solid #90caf9;
  border-radius: 8px;
  font-size: 12px;
  color: #1565c0;
}

.info-banner svg {
  flex-shrink: 0;
}

.section-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 10px 6px 10px;
}

.section-header {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.add-from-bank-btn {
  width: 100%;
  padding: 10px 12px;
  margin-bottom: 16px;
  background: linear-gradient(135deg, var(--accent-color) 0%, #5e72e4 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all 0.2s;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.add-from-bank-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
}

.add-from-bank-btn:active {
  transform: translateY(0);
}


.batch-toggle-btn {
  background: transparent;
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  padding: 4px 6px;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  transition: all 0.2s;
}

.batch-toggle-btn:hover {
  background: rgba(0, 0, 0, 0.05);
  color: var(--text-primary);
}

.batch-toggle-btn.active {
  background: var(--accent-color);
  border-color: var(--accent-color);
  color: white;
}

.batch-action-bar {
  display: flex;
  gap: 8px;
  padding: 8px 10px;
  background: #f8f9fa;
  border-radius: 6px;
  margin-bottom: 8px;
}

.batch-select-all {
  flex: 1;
  padding: 6px 10px;
  background: white;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.batch-select-all:hover {
  background: #f0f0f0;
}

.batch-delete-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: #ff4d4f;
  border: none;
  border-radius: 4px;
  color: white;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.batch-delete-btn:hover:not(:disabled) {
  background: #ff1f1f;
}

.batch-delete-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.file-item.batch-selected {
  background: #fff1f0;
  border-color: #ffccc7;
}

.batch-checkbox:checked {
  accent-color: #ff4d4f;
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

.add-files-btn {
  width: 100%;
  padding: 10px;
  background: #fff;
  color: var(--text-primary);
  border: 1px dashed var(--border-color);
  border-radius: 8px;
  margin-bottom: 24px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.2s;
}

.add-files-btn:hover {
  border-color: var(--accent-color);
  color: var(--accent-color);
  background: #f8faff;
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

/* Batch Toolbar Styles */
.batch-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 16px 12px 16px;
  /* Below header */
  padding: 8px;
  background: #f0f4ff;
  border-radius: 8px;
  border: 1px dashed #aabbdd;
}

.batch-tool-btn {
  font-size: 11px;
  font-weight: 600;
  padding: 4px 8px;
  border-radius: 4px;
  border: 1px solid #e0e0e0;
  background: white;
  color: #555;
  cursor: pointer;
  transition: all 0.2s;
}

.batch-tool-btn:hover {
  background: #f9f9f9;
  border-color: #ccc;
  color: #333;
}

.batch-tool-btn.delete {
  background: #fff0f0;
  color: #d32f2f;
  border-color: #ffcccc;
  display: flex;
  align-items: center;
  gap: 4px;
}

.batch-tool-btn.delete:hover {
  background: #ffe0e0;
  border-color: #ffaaaa;
}

.batch-tool-btn.delete:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  background: #f5f5f5;
  color: #aaa;
  border-color: transparent;
}

.batch-toggle-btn {
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  color: #999;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-left: auto;
  /* Push to right if needed */
}

.batch-toggle-btn:hover {
  background: rgba(0, 0, 0, 0.05);
  color: #333;
}

.batch-toggle-btn.active {
  background: #e6f0ff;
  color: #3b82f6;
}
</style>
