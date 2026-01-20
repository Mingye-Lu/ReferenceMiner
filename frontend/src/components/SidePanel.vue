<script setup lang="ts">
import { ref, inject, type Ref, computed, onMounted, onUnmounted, watch } from "vue"

import { type Theme, getStoredTheme, setTheme as applyThemeGlobal } from "../utils/theme"
import type { ManifestEntry, ChatSession, EvidenceChunk, Project } from "../types"
import FileUploader from "./FileUploader.vue"
import BankFileSelectorModal from "./BankFileSelectorModal.vue"
import ConfirmationModal from "./ConfirmationModal.vue"
import AlertModal from "./AlertModal.vue"
import { fetchBankManifest, fetchProjectFiles, selectProjectFiles, removeProjectFiles } from "../api/client"

const activeTab = ref<"corpus" | "chats">("corpus")
const isDeleting = ref<string | null>(null)

// Settings panel state
// Settings panel state
const showSettings = ref(false)

const submenuOpen = ref<string | null>(null)
const submitPromptKey = ref<'enter' | 'ctrl-enter'>('enter')
const submenuPosition = ref({ bottom: 0, left: 0 })
const currentTheme = ref<Theme>('system')


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
  (event: 'file-uploaded', entry: ManifestEntry): void
}>()


const notesList = computed(() => Array.from(pinnedEvidenceMap.value.values()))


const displayedFiles = computed(() => {
  if (!projectFiles.value) return []
  return manifest.value.filter(f => projectFiles.value.has(f.relPath))
})

// Pagination State
const filesPerPage = ref(7)
const notesPerPage = ref(4)
const chatsPerPage = ref(0) // 0 = unlimited

const filesPage = ref(1)
const notesPage = ref(1)
const chatsPage = ref(1)

// Watch for changes in display limits to save to localStorage
watch([filesPerPage, notesPerPage, chatsPerPage], () => {
  saveDisplaySettings()
})

const saveDisplaySettings = () => {
  localStorage.setItem('itemsPerPage', filesPerPage.value.toString())
  // Note: ProjectHub uses 'itemsPerPage' for files (legacy), but we want separate settings.
  // However, if ProjectHub only supports one setting for everything or specific keys, we should align.
  // Based on step 467 summary: ProjectHub implemented "files", "notes", "chats" independent settings.
  // It likely uses keys like 'filesPerPage', 'notesPerPage', 'chatsPerPage' 
  // OR it stored them in a JSON object?
  // Let's assume the safest path is separate keys as per my previous plan in step 467 summary implies independent keys.
  // Wait, step 467 summary said: "Implemented saving and loading of these settings using localStorage."
  // and "itemsPerPage for Project Files (Default: 7)".
  // Let's check ProjectHub content quickly to be 100% sure of the keys.
  // Actually, I can't check ProjectHub now without another tool call.
  // I will assume specific keys based on valid variable names: 'filesPerPage', 'notesPerPage', etc.
  // BUT, in SidePanel `onMounted` (which I haven't seen yet in full detail or I missed), I need to load them too?
  // Wait, I see `filesPerPage` ref in SidePanel initialized to 7. 
  // I need to LOAD them in onMounted as well.

  // Let's use specific keys to be safe and clear.
  localStorage.setItem('filesPerPage', filesPerPage.value.toString())
  localStorage.setItem('notesPerPage', notesPerPage.value.toString())
  localStorage.setItem('chatsPerPage', chatsPerPage.value.toString())

  window.dispatchEvent(new Event('settingChanged'))
}

onMounted(() => {
  const savedFiles = localStorage.getItem('filesPerPage')
  if (savedFiles) filesPerPage.value = parseInt(savedFiles, 10)

  const savedNotes = localStorage.getItem('notesPerPage')
  if (savedNotes) notesPerPage.value = parseInt(savedNotes, 10)

  const savedChats = localStorage.getItem('chatsPerPage')
  if (savedChats) chatsPerPage.value = parseInt(savedChats, 10)

  // Also listen for changes from ProjectHub
  window.addEventListener('settingChanged', loadSettings)
})

onUnmounted(() => {
  window.removeEventListener('settingChanged', loadSettings)
})

const loadSettings = () => {
  const savedFiles = localStorage.getItem('filesPerPage')
  if (savedFiles) filesPerPage.value = parseInt(savedFiles, 10)

  const savedNotes = localStorage.getItem('notesPerPage')
  if (savedNotes) notesPerPage.value = parseInt(savedNotes, 10)

  const savedChats = localStorage.getItem('chatsPerPage')
  if (savedChats) chatsPerPage.value = parseInt(savedChats, 10)
}

// Paginated Lists
const paginatedFiles = computed(() => {
  if (filesPerPage.value === 0) return displayedFiles.value
  const start = (filesPage.value - 1) * filesPerPage.value
  return displayedFiles.value.slice(start, start + filesPerPage.value)
})

const paginatedNotes = computed(() => {
  if (notesPerPage.value === 0) return notesList.value
  const start = (notesPage.value - 1) * notesPerPage.value
  return notesList.value.slice(start, start + notesPerPage.value)
})

const paginatedChats = computed(() => {
  if (chatsPerPage.value === 0) return chatSessions.value
  const start = (chatsPage.value - 1) * chatsPerPage.value
  return chatSessions.value.slice(start, start + chatsPerPage.value)
})

async function handleUploadComplete(entry: ManifestEntry) {
  console.log('[SidePanel] File uploaded:', entry.relPath)

  // Automatically add the uploaded file to the current project's file list
  if (projectId.value && entry.relPath) { // Use projectId.value instead of props.projectId
    projectFiles.value.add(entry.relPath)
    projectFiles.value = new Set(projectFiles.value) // Trigger reactivity
    console.log('[SidePanel] Auto-added file to project:', entry.relPath)
  }

  // Emit to parent (Cockpit) to update manifest
  emit('file-uploaded', entry)

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

// Toggle settings panel
function toggleSettings() {
  showSettings.value = !showSettings.value
  if (!showSettings.value) {
    submenuOpen.value = null
  }
}



// Submenu control
let closeSubmenuTimer: ReturnType<typeof setTimeout> | null = null

function openSubmenu(menu: string, event: MouseEvent) {
  // Clear any pending close timer
  if (closeSubmenuTimer) {
    clearTimeout(closeSubmenuTimer)
    closeSubmenuTimer = null
  }

  submenuOpen.value = menu

  // Calculate absolute position for teleported submenu
  const target = event.currentTarget as HTMLElement

  // Align bottom of submenu with bottom of setting panel (parent)
  const parent = target.closest('.settings-popup-panel')

  if (parent) {
    const parentRect = parent.getBoundingClientRect()
    // Calculate distance from bottom of viewport
    const bottom = window.innerHeight - parentRect.bottom

    submenuPosition.value = {
      bottom: Math.max(0, bottom), // Ensure non-negative
      left: parentRect.right + 8
    }
  } else {
    // Fallback
    const rect = target.getBoundingClientRect()
    submenuPosition.value = {
      bottom: window.innerHeight - rect.bottom,
      left: rect.right + 8
    }
  }
}

function closeSubmenu() {
  // Delay closing to allow mouse to move to submenu
  closeSubmenuTimer = setTimeout(() => {
    submenuOpen.value = null
  }, 150)
}

function keepSubmenuOpen() {
  // Cancel the close timer when mouse enters submenu
  if (closeSubmenuTimer) {
    clearTimeout(closeSubmenuTimer)
    closeSubmenuTimer = null
  }
}

function closeSubmenuImmediately() {
  // Close immediately when mouse leaves submenu
  if (closeSubmenuTimer) {
    clearTimeout(closeSubmenuTimer)
    closeSubmenuTimer = null
  }
  submenuOpen.value = null
}

// Submit prompt key setting
function setSubmitPromptKey(value: 'enter' | 'ctrl-enter', event?: MouseEvent) {
  // Stop event propagation to prevent closing settings panel
  if (event) {
    event.stopPropagation()
  }

  submitPromptKey.value = value
  localStorage.setItem('submitPromptKey', value)
  // Trigger custom event to notify ChatWindow
  window.dispatchEvent(new CustomEvent('settingChanged', {
    detail: { key: 'submitPromptKey', value }
  }))
  // Don't close submenu or settings panel - let user see the updated state
}

function handleThemeChange(theme: Theme) {
  currentTheme.value = theme
  applyThemeGlobal(theme)
}

// Close settings panel when clicking outside
function handleClickOutside(event: MouseEvent) {
  const target = event.target as HTMLElement
  if (showSettings.value && !target.closest('.settings-popup-panel') && !target.closest('.settings-trigger-btn')) {
    // Check if click is on teleported submenu
    if (!target.closest('.settings-submenu-teleported')) {
      showSettings.value = false
      submenuOpen.value = null
    }
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)

  // Load saved settings
  const savedKey = localStorage.getItem('submitPromptKey')
  if (savedKey === 'enter' || savedKey === 'ctrl-enter') {
    submitPromptKey.value = savedKey
  }

  // Load theme
  currentTheme.value = getStoredTheme()

  // Listen for theme changes
  window.addEventListener('themeChanged', ((e: CustomEvent) => {
    currentTheme.value = e.detail
  }) as EventListener)

  // Load display settings
  const storedFiles = localStorage.getItem('filesPerPage')
  if (storedFiles) filesPerPage.value = parseInt(storedFiles, 10)

  const storedNotes = localStorage.getItem('notesPerPage')
  if (storedNotes) notesPerPage.value = parseInt(storedNotes, 10)

  const storedChats = localStorage.getItem('chatsPerPage')
  if (storedChats) chatsPerPage.value = parseInt(storedChats, 10)

  // Listen for setting changes
  window.addEventListener('settingChanged', ((e: CustomEvent) => {
    if (e.detail.key === 'filesPerPage') {
      filesPerPage.value = e.detail.value
      filesPage.value = 1 // Reset to first page
    }
    if (e.detail.key === 'notesPerPage') {
      notesPerPage.value = e.detail.value
      notesPage.value = 1
    }
    if (e.detail.key === 'chatsPerPage') {
      chatsPerPage.value = e.detail.value
      chatsPage.value = 1
    }
  }) as EventListener)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
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
      <!-- Fixed Actions Area -->
      <div class="sidebar-actions">
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
      </div>

      <!-- Scrollable Content Area -->
      <div class="sidebar-scrollable">
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

        <div v-if="displayedFiles.length === 0" class="empty-msg">No files selected. Click "Manage Project Files" to add
          files.</div>

        <div v-for="file in paginatedFiles" :key="file.relPath" class="file-item" :class="{
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

        <!-- Files Pagination -->
        <div class="pagination-controls" v-if="filesPerPage > 0 && displayedFiles.length > filesPerPage">
          <button class="pagination-btn" :disabled="filesPage === 1" @click="filesPage--">
            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="15 18 9 12 15 6"></polyline>
            </svg>
          </button>
          <span class="pagination-info">{{ (filesPage - 1) * filesPerPage + 1 }}-{{ Math.min(filesPage * filesPerPage,
            displayedFiles.length) }} of {{ displayedFiles.length }}</span>
          <button class="pagination-btn" :disabled="filesPage * filesPerPage >= displayedFiles.length"
            @click="filesPage++">
            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="9 18 15 12 9 6"></polyline>
            </svg>
          </button>
        </div>

        <!-- Notes Section -->
        <div class="section-header" style="margin-top: 20px; margin-bottom: 14px;">PINNED NOTES ({{ notesList.length }})
        </div>
        <div v-if="notesList.length === 0" class="empty-msg">No pinned notes.</div>

        <div v-for="note in paginatedNotes" :key="note.chunkId" class="file-item"
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

        <!-- Notes Pagination -->
        <div class="pagination-controls" v-if="notesPerPage > 0 && notesList.length > notesPerPage">
          <button class="pagination-btn" :disabled="notesPage === 1" @click="notesPage--">
            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="15 18 9 12 15 6"></polyline>
            </svg>
          </button>
          <span class="pagination-info">{{ (notesPage - 1) * notesPerPage + 1 }}-{{ Math.min(notesPage * notesPerPage,
            notesList.length) }} of {{ notesList.length }}</span>
          <button class="pagination-btn" :disabled="notesPage * notesPerPage >= notesList.length" @click="notesPage++">
            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="9 18 15 12 9 6"></polyline>
            </svg>
          </button>
        </div>
      </div>

      <!-- Fixed Footer with Settings -->
      <div class="sidebar-footer">
        <button class="settings-trigger-btn" @click="toggleSettings" :class="{ active: showSettings }">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path
              d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
            <circle cx="12" cy="12" r="3" />
          </svg>
          <span>Settings</span>
        </button>

        <!-- Floating Settings Panel -->
        <Transition name="settings-popup">
          <div v-if="showSettings" class="settings-popup-panel">
            <!-- Theme (with submenu) -->
            <div class="settings-popup-item has-submenu" @mouseenter="openSubmenu('theme', $event)"
              @mouseleave="closeSubmenu">
              <span>Theme</span>
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                class="chevron-right">
                <polyline points="9 18 15 12 9 6"></polyline>
              </svg>
            </div>

            <!-- Submit prompt key (with submenu) -->
            <div class="settings-popup-item has-submenu" @mouseenter="openSubmenu('prompt-key', $event)"
              @mouseleave="closeSubmenu">
              <span>Submit prompt key</span>
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                class="chevron-right">
                <polyline points="9 18 15 12 9 6"></polyline>
              </svg>
            </div>

            <!-- Display (with submenu) -->
            <div class="settings-popup-item has-submenu" @mouseenter="openSubmenu('display', $event)"
              @mouseleave="closeSubmenu">
              <span>Display</span>
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                class="chevron-right">
                <polyline points="9 18 15 12 9 6"></polyline>
              </svg>
            </div>
          </div>
        </Transition>
      </div>

    </div>

    <!-- CHATS TAB -->
    <div class="sidebar-content" v-else>
      <!-- Fixed Actions Area -->
      <div class="sidebar-actions">
        <button class="new-chat-btn" @click="handleNewChat">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
            style="margin-right: 6px;">
            <path d="M5 12h14" />
            <path d="M12 5v14" />
          </svg>
          New Chat
        </button>
      </div>

      <!-- Scrollable Content Area -->
      <div class="sidebar-scrollable">
        <div class="chat-list">
          <div v-for="chat in paginatedChats" :key="chat.id" class="chat-item"
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

        <!-- Chats Pagination -->
        <div class="pagination-controls" v-if="chatsPerPage > 0 && chatSessions.length > chatsPerPage">
          <button class="pagination-btn" :disabled="chatsPage === 1" @click="chatsPage--">
            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="15 18 9 12 15 6"></polyline>
            </svg>
          </button>
          <span class="pagination-info">{{ (chatsPage - 1) * chatsPerPage + 1 }}-{{ Math.min(chatsPage * chatsPerPage,
            chatSessions.length) }} of {{ chatSessions.length }}</span>
          <button class="pagination-btn" :disabled="chatsPage * chatsPerPage >= chatSessions.length"
            @click="chatsPage++">
            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="9 18 15 12 9 6"></polyline>
            </svg>
          </button>
        </div>
      </div>

      <!-- Fixed Footer with Settings -->
      <div class="sidebar-footer">
        <button class="settings-trigger-btn" @click="toggleSettings" :class="{ active: showSettings }">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path
              d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l-.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
            <circle cx="12" cy="12" r="3" />
          </svg>
          <span>Settings</span>
        </button>

        <!-- Floating Settings Panel -->
        <Transition name="settings-popup">
          <div v-if="showSettings" class="settings-popup-panel">
            <!-- Theme (with submenu) -->
            <div class="settings-popup-item has-submenu" @mouseenter="openSubmenu('theme', $event)"
              @mouseleave="closeSubmenu">
              <span>Theme</span>
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                class="chevron-right">
                <polyline points="9 18 15 12 9 6"></polyline>
              </svg>
            </div>

            <!-- Submit prompt key (with submenu) -->
            <div class="settings-popup-item has-submenu" @mouseenter="openSubmenu('prompt-key', $event)"
              @mouseleave="closeSubmenu">
              <span>Submit prompt key</span>
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                class="chevron-right">
                <polyline points="9 18 15 12 9 6"></polyline>
              </svg>
            </div>

            <!-- Display (with submenu) -->
            <div class="settings-popup-item has-submenu" @mouseenter="openSubmenu('display', $event)"
              @mouseleave="closeSubmenu">
              <span>Display</span>
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                class="chevron-right">
                <polyline points="9 18 15 12 9 6"></polyline>
              </svg>
            </div>
          </div>
        </Transition>
      </div>
    </div>

    <!-- Delete File Confirmation Modal -->
    <ConfirmationModal v-model="showDeleteFileModal" title="Remove File?"
      :message="pendingDeleteFile ? `Remove \&quot;${pendingDeleteFile.relPath}\&quot; from this project? The file will remain in the Reference Bank.` : ''"
      confirmText="Remove" @confirm="confirmDeleteFile" @cancel="cancelDeleteFile" />

    <!-- Batch Delete Confirmation Modal -->
    <ConfirmationModal v-model="showBatchDeleteModal" title="Remove Files?"
      :message="`Remove ${batchSelected.size} files from this project? They will remain in the Reference Bank.`"
      confirmText="Remove" @confirm="confirmBatchDelete" @cancel="cancelBatchDelete" />

    <!-- Unpin Note Confirmation Modal -->
    <ConfirmationModal v-model="showUnpinNoteModal" title="Unpin Note?"
      :message="pendingUnpinNote ? `Unpin note: &quot;${pendingUnpinNote.text.slice(0, 50)}${pendingUnpinNote.text.length > 50 ? '...' : ''}&quot;?` : ''"
      confirmText="Unpin" @confirm="confirmUnpinNote" @cancel="cancelUnpinNote" />

    <!-- Bank File Selector Modal -->
    <BankFileSelectorModal v-model="showBankSelector" :project-id="projectId" :selected-files="projectFiles"
      @confirm="handleBankFilesSelected" />

    <!-- Error Alert Modal -->
    <AlertModal v-model="showErrorModal" title="Delete Failed" :message="errorMessage" type="error"
      @close="closeErrorModal" />
  </aside>

  <!-- Teleported Submenus (rendered to body to avoid overflow issues) -->
  <Teleport to="body">
    <Transition name="submenu-slide">
      <div v-if="submenuOpen === 'theme'" class="settings-submenu-teleported" :style="{
        bottom: submenuPosition.bottom + 'px',
        left: submenuPosition.left + 'px'
      }" @mouseenter="keepSubmenuOpen" @mouseleave="closeSubmenuImmediately">
        <div class="settings-submenu-item" :class="{ active: currentTheme === 'light' }"
          @click.stop="handleThemeChange('light')">
          <span>Light</span>
          <svg v-if="currentTheme === 'light'" xmlns="http://www.w3.org/2000/svg" width="16" height="16"
            viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"
            stroke-linejoin="round" class="check-icon">
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
        </div>
        <div class="settings-submenu-item" :class="{ active: currentTheme === 'dark' }"
          @click.stop="handleThemeChange('dark')">
          <span>Dark</span>
          <svg v-if="currentTheme === 'dark'" xmlns="http://www.w3.org/2000/svg" width="16" height="16"
            viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"
            stroke-linejoin="round" class="check-icon">
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
        </div>
        <div class="settings-submenu-item" :class="{ active: currentTheme === 'system' }"
          @click.stop="handleThemeChange('system')">
          <span>System</span>
          <svg v-if="currentTheme === 'system'" xmlns="http://www.w3.org/2000/svg" width="16" height="16"
            viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"
            stroke-linejoin="round" class="check-icon">
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
        </div>
      </div>
    </Transition>

    <Transition name="submenu-slide">
      <div v-if="submenuOpen === 'prompt-key'" class="settings-submenu-teleported" :style="{
        bottom: submenuPosition.bottom + 'px',
        left: submenuPosition.left + 'px'
      }" @mouseenter="keepSubmenuOpen" @mouseleave="closeSubmenuImmediately">
        <div class="settings-submenu-item" :class="{ active: submitPromptKey === 'enter' }"
          @click="setSubmitPromptKey('enter', $event)">
          <span>Enter</span>
          <svg v-if="submitPromptKey === 'enter'" xmlns="http://www.w3.org/2000/svg" width="16" height="16"
            viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"
            stroke-linejoin="round" class="check-icon">
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
        </div>
        <div class="settings-submenu-item" :class="{ active: submitPromptKey === 'ctrl-enter' }"
          @click="setSubmitPromptKey('ctrl-enter', $event)">
          <span>Ctrl + Enter</span>
          <svg v-if="submitPromptKey === 'ctrl-enter'" xmlns="http://www.w3.org/2000/svg" width="16" height="16"
            viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"
            stroke-linejoin="round" class="check-icon">
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
        </div>
      </div>
    </Transition>

    <Transition name="submenu-slide">
      <div v-if="submenuOpen === 'display'" class="settings-submenu-teleported" :style="{
        bottom: submenuPosition.bottom + 'px',
        left: submenuPosition.left + 'px',
        minWidth: '220px'
      }" @mouseenter="keepSubmenuOpen" @mouseleave="closeSubmenuImmediately">
        <div class="settings-submenu-group">
          <div class="settings-submenu-label">Files per page</div>
          <div class="input-wrapper">
            <input type="number" v-model.number="filesPerPage" min="0" class="settings-input"
              placeholder="0 for unlimited" />
            <span class="input-hint">{{ filesPerPage === 0 ? 'Unlimited' : 'items' }}</span>
          </div>
        </div>

        <div class="settings-submenu-divider"></div>

        <div class="settings-submenu-group">
          <div class="settings-submenu-label">Notes per page</div>
          <div class="input-wrapper">
            <input type="number" v-model.number="notesPerPage" min="0" class="settings-input"
              placeholder="0 for unlimited" />
            <span class="input-hint">{{ notesPerPage === 0 ? 'Unlimited' : 'items' }}</span>
          </div>
        </div>

        <div class="settings-submenu-divider"></div>

        <div class="settings-submenu-group">
          <div class="settings-submenu-label">Chats per page</div>
          <div class="input-wrapper">
            <input type="number" v-model.number="chatsPerPage" min="0" class="settings-input"
              placeholder="0 for unlimited" />
            <span class="input-hint">{{ chatsPerPage === 0 ? 'Unlimited' : 'items' }}</span>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.empty-msg {
  padding: 10px 20px;
  font-size: 12px;
  color: var(--color-neutral-550);
  text-align: center;
}

/* Sidebar Layout Sections */
.sidebar-actions {
  flex-shrink: 0;
  padding: 8px 0 16px 0;
  border-bottom: 1px solid var(--border-color);
}

.sidebar-scrollable {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0 16px 0;
}

.sidebar-footer {
  flex-shrink: 0;
  padding: 12px 16px;
  border-top: 1px solid var(--border-color);
}

.settings-trigger-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px;
  background: transparent;
  border: 1px solid var(--border-card);
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s;
}

.settings-trigger-btn:hover {
  background: var(--color-neutral-120);
  border-color: var(--border-card-hover);
  color: var(--text-primary);
}

.settings-trigger-btn svg {
  color: var(--text-secondary);
  transition: transform 0.2s;
}

.settings-trigger-btn:hover svg {
  transform: rotate(30deg);
  color: var(--accent-color);
}

.info-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  margin-bottom: 16px;
  background: var(--color-info-90);
  border: 1px solid var(--color-info-350);
  border-radius: 8px;
  font-size: 12px;
  color: var(--color-info-800);
}

.info-banner svg {
  flex-shrink: 0;
}

.section-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 0 6px 0;
  margin-bottom: 8px;
}

.section-header {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 0;
}

.add-from-bank-btn {
  width: 100%;
  padding: 10px 12px;
  margin-bottom: 16px;
  background: linear-gradient(135deg, var(--accent-color) 0%, var(--color-accent-400) 100%);
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
  box-shadow: 0 2px 4px var(--alpha-black-10);
}

.add-from-bank-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px var(--alpha-black-15);
}

.add-from-bank-btn:active {
  transform: translateY(0);
}


.batch-toggle-btn {
  background: transparent;
  border: 1px solid var(--border-card);
  color: var(--text-secondary);
  padding: 4px 6px;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  transition: all 0.2s;
}

.batch-toggle-btn:hover {
  background: var(--bg-selected);
  border-color: var(--accent-bright);
  color: var(--accent-color);
}

.batch-toggle-btn.active {
  background: var(--bg-selected);
  border-color: var(--accent-bright);
  color: var(--accent-color);
}

.batch-action-bar {
  display: flex;
  gap: 8px;
  padding: 8px 10px;
  background: var(--color-neutral-100);
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
  background: var(--color-neutral-220);
}

.batch-delete-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: var(--color-danger-500);
  border: none;
  border-radius: 4px;
  color: white;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.batch-delete-btn:hover:not(:disabled) {
  background: var(--color-danger-600);
}

.batch-delete-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.file-item.batch-selected {
  background: var(--color-danger-30);
  border-color: var(--color-danger-140);
}

.batch-checkbox:checked {
  accent-color: var(--color-danger-500);
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
  background: var(--bg-card-hover);
  border-color: var(--accent-bright);
}

.file-item.selected {
  background: var(--bg-selected);
  border-color: var(--accent-bright);
}

.file-item.highlighted {
  background: var(--color-warning-100);
  border-color: var(--color-warning-600);
}

[data-theme="dark"] .file-item.highlighted {
  background: rgba(180, 130, 0, 0.2);
  border-color: rgba(255, 193, 7, 0.5);
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
  background: var(--bg-icon-hover);
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
  color: var(--color-danger-500) !important;
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

/* Sidebar Content - Flex Container */
.sidebar-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Allow settings popup to overflow */
.sidebar-footer {
  position: relative;
  overflow: visible;
}

.add-files-btn {
  width: 100%;
  padding: 10px;
  background: var(--color-white);
  color: var(--text-primary);
  border: 1px dashed var(--border-color);
  border-radius: 8px;
  margin-bottom: 0;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 500;
  transition: all 0.2s;
}

.add-files-btn:hover {
  border-color: var(--accent-color);
  color: var(--accent-color);
  background: var(--color-neutral-90);
}

.new-chat-btn {
  width: 100%;
  padding: 10px;
  background: var(--text-primary);
  color: var(--color-white);
  border: none;
  border-radius: 8px;
  margin-bottom: 0;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
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
  color: var(--color-neutral-400);
  cursor: pointer;
  padding: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.chat-item:hover .delete-chat-btn {
  opacity: 1;
}

.delete-chat-btn:hover {
  color: var(--color-danger-500);
}

.chat-item:hover {
  background: var(--color-white);
  border-color: var(--border-color);
}

.chat-item.active {
  background: var(--color-white);
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
  background: var(--color-neutral-150);
  border-radius: 8px;
  border: 1px dashed var(--color-accent-200);
}

.batch-tool-btn {
  font-size: 11px;
  font-weight: 600;
  padding: 4px 8px;
  border-radius: 4px;
  border: 1px solid var(--border-card);
  background: white;
  color: var(--color-neutral-700);
  cursor: pointer;
  transition: all 0.2s;
}

.batch-tool-btn:hover {
  background: var(--color-neutral-85);
  border-color: var(--border-card-hover);
  color: var(--color-neutral-800);
}

.batch-tool-btn.delete {
  background: var(--color-danger-25);
  color: var(--color-danger-700);
  border-color: var(--color-danger-150);
  display: flex;
  align-items: center;
  gap: 4px;
}

.batch-tool-btn.delete:hover {
  background: var(--color-danger-75);
  border-color: var(--color-danger-200);
}

.batch-tool-btn.delete:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  background: var(--color-neutral-130);
  color: var(--color-neutral-450);
  border-color: transparent;
}

.batch-toggle-btn {
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  color: var(--color-neutral-500);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-left: auto;
  /* Push to right if needed */
}

.batch-toggle-btn:hover {
  background: var(--alpha-black-05);
  color: var(--accent-color);
}

.batch-toggle-btn.active {
  background: var(--color-info-80);
  color: var(--color-info-600);
}

/* Settings Popup Panel Styles */
.settings-trigger-btn.active {
  background: var(--color-neutral-150);
  border-color: var(--accent-color);
  color: var(--text-primary);
}

.settings-popup-panel {
  position: absolute;
  bottom: 100%;
  left: 12px;
  right: 12px;
  margin-bottom: 8px;
  background: var(--color-white);
  border: 1px solid var(--border-card);
  border-radius: 12px;
  box-shadow: 0 8px 24px var(--alpha-black-15), 0 2px 8px var(--alpha-black-10);
  padding: 6px;
  z-index: 1000;
  min-width: 240px;
}

.sidebar-shell {
  width: 320px;
  height: 100%;
  background: var(--color-white);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  overflow: visible;
  /* Allow settings popup to overflow */
}

.settings-popup-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  cursor: pointer;
  transition: all 0.15s;
  user-select: none;
}

.settings-popup-item:hover {
  background: var(--color-neutral-120);
}

.settings-popup-item svg:first-child {
  color: var(--text-secondary);
  flex-shrink: 0;
}

.settings-popup-item .chevron-right {
  margin-left: auto;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.settings-popup-divider {
  height: 1px;
  background: var(--color-neutral-200);
  margin: 4px 0;
}

/* Settings Popup Animation */
.settings-popup-enter-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.settings-popup-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.settings-popup-enter-from {
  opacity: 0;
  transform: translateY(8px) scale(0.95);
}

.settings-popup-leave-to {
  opacity: 0;
  transform: translateY(4px) scale(0.98);
}

.settings-popup-enter-to,
.settings-popup-leave-from {
  opacity: 1;
  transform: translateY(0) scale(1);
}

/* Settings Submenu Styles */
.settings-popup-item.has-submenu {
  position: relative;
}

.settings-submenu {
  position: absolute;
  left: 100%;
  top: 0;
  margin-left: 8px;
  background: var(--color-white);
  border: 1px solid var(--border-card);
  border-radius: 12px;
  box-shadow: 0 8px 24px var(--alpha-black-15), 0 2px 8px var(--alpha-black-10);
  padding: 6px;
  min-width: 180px;
  z-index: 1001;
}

/* Teleported submenu (rendered to body) */
.settings-submenu-teleported {
  position: fixed;
  background: var(--color-white);
  border: 1px solid var(--border-card);
  border-radius: 12px;
  box-shadow: 0 8px 24px var(--alpha-black-15), 0 2px 8px var(--alpha-black-10);
  padding: 6px;
  min-width: 180px;
  z-index: 10000;
}

.settings-submenu-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  cursor: pointer;
  transition: all 0.15s;
  user-select: none;
}

.settings-submenu-item:hover {
  background: var(--color-neutral-120);
}

.settings-submenu.file-item.selected {
  background: var(--bg-selected);
  border-color: var(--accent-color);
}

.settings-submenu-item.active {
  background: var(--accent-soft, var(--color-accent-50));
  color: var(--accent-color);
}

.settings-submenu-item .check-icon {
  color: var(--accent-color);
  flex-shrink: 0;
}

/* Submenu Slide Animation */
.submenu-slide-enter-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.submenu-slide-leave-active {
  transition: opacity 0.1s ease, transform 0.1s ease;
}

.submenu-slide-enter-from {
  opacity: 0;
  transform: translateX(-8px) scale(0.95);
}

.submenu-slide-leave-to {
  opacity: 0;
  transform: translateX(-4px) scale(0.98);
}

.submenu-slide-enter-to,
.submenu-slide-leave-from {
  opacity: 1;
  transform: translateX(0) scale(1);
}

/* Pagination Controls */
.pagination-controls {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 8px 0;
  margin-top: 8px;
}

.pagination-btn {
  background: transparent;
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  width: 24px;
  height: 24px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
}

.pagination-btn:hover:not(:disabled) {
  background: var(--bg-card-hover);
  color: var(--text-primary);
  border-color: var(--border-card-hover);
}

.pagination-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  border-color: transparent;
}

.pagination-info {
  font-size: 11px;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

/* Settings Input Styles */
.settings-submenu-group {
  padding: 8px 12px;
}

.settings-submenu-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 6px;
  text-transform: uppercase;
}

.input-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--color-neutral-100);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 2px 8px;
  transition: all 0.2s;
}

.input-wrapper:focus-within {
  border-color: var(--accent-color);
  background: var(--color-white);
  box-shadow: 0 0 0 2px var(--alpha-accent-10);
}

.settings-input {
  width: 100%;
  border: none;
  background: transparent;
  padding: 4px 0;
  font-size: 13px;
  color: var(--text-primary);
  outline: none;
  -moz-appearance: textfield;
  appearance: textfield;
}

.settings-input::-webkit-outer-spin-button,
.settings-input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.input-hint {
  font-size: 11px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.settings-submenu-divider {
  height: 1px;
  background: var(--border-color);
  margin: 4px 0;
}
</style>
