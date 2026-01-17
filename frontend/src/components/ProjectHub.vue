<script setup lang="ts">
import { ref, onMounted, computed } from "vue"
import { useRouter } from "vue-router"
import { fetchProjects, createProject, fetchBankManifest, deleteFile, deleteProject, selectProjectFiles, getSettings, saveApiKey, validateApiKey, deleteApiKey, resetAllData } from "../api/client"
import type { Project, ManifestEntry, BalanceInfo, Settings as AppSettings } from "../types"
import ProjectCard from "./ProjectCard.vue"
import FileUploader from "./FileUploader.vue"
import FilePreviewModal from "./FilePreviewModal.vue"
import ConfirmationModal from "./ConfirmationModal.vue"
import BankFileSelectorModal from "./BankFileSelectorModal.vue"
import { Plus, Search, Loader2, Upload, FileText, Trash2, Settings } from "lucide-vue-next"
import { type Theme, getStoredTheme, setTheme } from "../utils/theme"
import { getFileName } from "../utils"

const router = useRouter()
const activeTab = ref<'projects' | 'bank' | 'settings'>('projects')
const settingsSection = ref<'preferences' | 'advanced'>('preferences')
const currentTheme = ref<Theme>('system')
const projects = ref<Project[]>([])
const bankFiles = ref<ManifestEntry[]>([])
const loading = ref(true)
const bankLoading = ref(false)
const searchQuery = ref("")
const showCreateModal = ref(false)
const newProjectName = ref("")
const newProjectDesc = ref("")
const creating = ref(false)
const showPreviewModal = ref(false)
const previewFile = ref<ManifestEntry | null>(null)
const showDeleteModal = ref(false)
const fileToDelete = ref<ManifestEntry | null>(null)
const deleting = ref(false)
const showDeleteProjectModal = ref(false)
const projectToDelete = ref<Project | null>(null)
const deletingProject = ref(false)
const showFileSelectorForCreate = ref(false)
const selectedFilesForCreate = ref<Set<string>>(new Set())

// Advanced Settings State
const settings = ref<AppSettings | null>(null)
const apiKeyInput = ref('')
const showApiKey = ref(false)
const isLoadingSettings = ref(false)
const isSaving = ref(false)
const isValidating = ref(false)
const isResetting = ref(false)
const showResetConfirm = ref(false)
const validationStatus = ref<'none' | 'valid' | 'invalid'>('none')
const validationError = ref('')
const balanceInfos = ref<BalanceInfo[]>([])
const balanceAvailable = ref<boolean | null>(null)
const saveError = ref('')
const resetError = ref('')
const resetSuccess = ref('')

const apiKeyStatusMessage = computed(() => {
    return balanceAvailable.value === false
        ? 'API key is valid, but balance is insufficient'
        : 'API key is valid'
})

async function loadProjects() {
    try {
        loading.value = true
        projects.value = await fetchProjects()
    } catch (err) {
        console.error("Failed to load projects:", err)
    } finally {
        loading.value = false
    }
}

async function loadBankFiles() {
    try {
        bankLoading.value = true
        bankFiles.value = await fetchBankManifest()
    } catch (err) {
        console.error("Failed to load bank files:", err)
    } finally {
        bankLoading.value = false
    }
}

async function handleCreate() {
    if (!newProjectName.value.trim()) return
    try {
        creating.value = true
        const p = await createProject({
            name: newProjectName.value,
            description: newProjectDesc.value
        })


        if (selectedFilesForCreate.value.size > 0) {
            try {
                await selectProjectFiles(p.id, Array.from(selectedFilesForCreate.value))
            } catch (e) {
                console.error("Failed to add initial files", e)
            }
        }

        projects.value.push(p)
        showCreateModal.value = false
        newProjectName.value = ""
        newProjectDesc.value = ""
        selectedFilesForCreate.value = new Set()

        openProject(p.id)
    } catch (err) {
        console.error("Failed to create project:", err)
    } finally {
        creating.value = false
    }
}

const sortedBankFiles = computed(() => {
    return [...bankFiles.value].sort((a, b) => {
        const nameA = getFileName(a.relPath).toLowerCase()
        const nameB = getFileName(b.relPath).toLowerCase()
        if (nameA !== nameB) return nameA.localeCompare(nameB)
        return a.relPath.localeCompare(b.relPath)
    })
})

function upsertBankFile(entry: ManifestEntry) {
    const idx = bankFiles.value.findIndex(item => item.relPath === entry.relPath)
    if (idx === -1) {
        bankFiles.value = [...bankFiles.value, entry]
        return
    }
    const next = [...bankFiles.value]
    next[idx] = entry
    bankFiles.value = next
}

function openFileSelectorForCreate() {
    showFileSelectorForCreate.value = true
}

function handleInitialFilesSelected(files: string[]) {
    selectedFilesForCreate.value = new Set(files)
    showFileSelectorForCreate.value = false
}

function openProject(id: string) {
    router.push(`/project/${id}`)
}

function handlePreview(file: ManifestEntry) {
    previewFile.value = file
    showPreviewModal.value = true
}

function requestDelete(file: ManifestEntry) {
    fileToDelete.value = file
    showDeleteModal.value = true
}

async function confirmDelete() {
    if (!fileToDelete.value) return
    try {
        deleting.value = true
        const relPath = fileToDelete.value.relPath
        bankFiles.value = bankFiles.value.filter(file => file.relPath !== relPath)
        await deleteFile('default', relPath)
        showDeleteModal.value = false
        fileToDelete.value = null
    } catch (err) {
        await loadBankFiles()
        console.error("Failed to delete file:", err)
    } finally {
        deleting.value = false
    }
}

function cancelDelete() {
    showDeleteModal.value = false
    fileToDelete.value = null
}

function handleDeleteProject(projectId: string) {
    const project = projects.value.find(p => p.id === projectId)
    if (project) {
        projectToDelete.value = project
        showDeleteProjectModal.value = true
    }
}

async function confirmDeleteProject() {
    if (!projectToDelete.value) return
    try {
        deletingProject.value = true
        await deleteProject(projectToDelete.value.id)
        await loadProjects()
        showDeleteProjectModal.value = false
        projectToDelete.value = null
    } catch (err) {
        console.error("Failed to delete project:", err)
    } finally {
        deletingProject.value = false
    }
}

function cancelDeleteProject() {
    showDeleteProjectModal.value = false
    projectToDelete.value = null
}

async function handleUploadComplete(entry: ManifestEntry) {
    upsertBankFile(entry)
}

function handleBeforeLeave(el: Element) {
    const element = el as HTMLElement
    const parent = element.parentElement
    if (!parent) return

    const rect = element.getBoundingClientRect()
    const parentRect = parent.getBoundingClientRect()
    element.style.position = "absolute"
    element.style.top = `${rect.top - parentRect.top}px`
    element.style.left = `${rect.left - parentRect.left}px`
    element.style.width = `${rect.width}px`
    element.style.height = `${rect.height}px`
}

function switchToBank() {
    activeTab.value = 'bank'
    if (bankFiles.value.length === 0) {
        loadBankFiles()
    }
}

async function handleDataReset() {
    // Reload projects list after data reset
    await loadProjects()
    // Reload bank files if currently viewing bank tab
    if (activeTab.value === 'bank') {
        await loadBankFiles()
    }
}

// Settings Methods
async function handleValidate() {
    if (!apiKeyInput.value && !settings.value?.hasApiKey) return
    isValidating.value = true
    validationStatus.value = 'none'
    validationError.value = ''
    try {
        const result = await validateApiKey(apiKeyInput.value || undefined)
        validationStatus.value = result.valid ? 'valid' : 'invalid'
        validationError.value = formatValidationError(result.error)
        balanceInfos.value = result.balanceInfos ?? []
        balanceAvailable.value = typeof result.isAvailable === 'boolean' ? result.isAvailable : null
    } catch (e: any) {
        validationStatus.value = 'invalid'
        validationError.value = formatValidationError(e.message || 'Validation failed')
        balanceInfos.value = []
        balanceAvailable.value = null
    } finally {
        isValidating.value = false
    }
}

async function handleSave() {
    if (!apiKeyInput.value) return
    isSaving.value = true
    saveError.value = ''
    try {
        await saveApiKey(apiKeyInput.value)
        settings.value = await getSettings()
        apiKeyInput.value = ''
        validationStatus.value = 'none'
        balanceInfos.value = []
        balanceAvailable.value = null
    } catch (e: any) {
        saveError.value = e.message || 'Failed to save'
    } finally {
        isSaving.value = false
    }
}

async function handleDeleteApiKey() {
    isSaving.value = true
    try {
        await deleteApiKey()
        settings.value = await getSettings()
        validationStatus.value = 'none'
        apiKeyInput.value = ''
        balanceInfos.value = []
        balanceAvailable.value = null
    } catch (e) {
        console.error('Failed to delete API key:', e)
    } finally {
        isSaving.value = false
    }
}

function handleResetClick() {
    showResetConfirm.value = true
    resetError.value = ''
    resetSuccess.value = ''
}

async function handleResetConfirm() {
    isResetting.value = true
    resetError.value = ''
    resetSuccess.value = ''
    try {
        const result = await resetAllData()
        resetSuccess.value = result.message
        showResetConfirm.value = false
        await handleDataReset()
    } catch (e: any) {
        resetError.value = e.message || 'Failed to reset data'
    } finally {
        isResetting.value = false
    }
}

function formatValidationError(error?: string): string {
    if (!error) return ''
    const trimmed = error.trim()
    const jsonStart = trimmed.indexOf('{')
    if (jsonStart !== -1) {
        const maybeJson = trimmed.slice(jsonStart)
        try {
            const parsed = JSON.parse(maybeJson)
            const message = parsed?.error?.message
            if (typeof message === 'string' && message.trim()) {
                return message.trim()
            }
        } catch {
            // Ignore JSON parsing errors
        }
    }
    return trimmed
}

onMounted(async () => {
    await loadProjects()

    // Load current theme
    currentTheme.value = getStoredTheme()

    // Listen for theme changes
    window.addEventListener('themeChanged', ((e: CustomEvent) => {
        currentTheme.value = e.detail
    }) as EventListener)

    // Load settings
    isLoadingSettings.value = true
    try {
        settings.value = await getSettings()
    } catch (e) {
        console.error('Failed to load settings:', e)
    } finally {
        isLoadingSettings.value = false
    }
})
</script>

<template>
    <div class="project-hub-container">
        <header class="hub-header">
            <div class="header-left">
                <div class="logo">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
                    </svg>
                    <span>ReferenceMiner</span>
                </div>
                <h1>Your Dashboard</h1>
            </div>
            <div class="header-right">
                <div class="search-bar">
                    <Search :size="16" />
                    <input v-model="searchQuery" placeholder="Search studies..." />
                </div>
                <button class="btn-primary" @click="showCreateModal = true">
                    <Plus :size="18" />
                    <span>New Study</span>
                </button>
            </div>
        </header>

        <!-- Tabs -->
        <div class="hub-tabs">
            <div class="tabs-left">
                <button class="tab-btn" :class="{ active: activeTab === 'projects' }" @click="activeTab = 'projects'">
                    <Search :size="16" />
                    <span>Projects</span>
                </button>
                <button class="tab-btn" :class="{ active: activeTab === 'bank' }" @click="switchToBank">
                    <FileText :size="16" />
                    <span>Reference Bank</span>
                </button>
            </div>
            <div class="tabs-right">
                <button class="tab-btn" :class="{ active: activeTab === 'settings' }" @click="activeTab = 'settings'">
                    <Settings :size="16" />
                    <span>Settings</span>
                </button>
            </div>
        </div>

        <main class="hub-content">
            <!-- Projects Tab -->
            <div v-if="activeTab === 'projects'">
                <div v-if="loading" class="loading-state">
                    <Loader2 class="spinner" :size="32" />
                    <p>Loading your research space...</p>
                </div>

                <div v-else-if="projects.length === 0" class="empty-state">
                    <div class="empty-icon">📂</div>
                    <h2>No studies yet</h2>
                    <p>Create your first research project to get started.</p>
                    <button class="btn-primary" @click="showCreateModal = true">
                        <Plus :size="18" />
                        <span>Create New Study</span>
                    </button>
                </div>

                <div v-else class="project-grid">
                    <ProjectCard v-for="p in projects" :key="p.id" :project="p" @open="openProject"
                        @delete="handleDeleteProject" />

                    <div class="create-card" @click="showCreateModal = true">
                        <div class="plus-icon">
                            <Plus :size="32" />
                        </div>
                        <span>Start New Project</span>
                    </div>
                </div>
            </div>

            <!-- Reference Bank Tab -->
            <div v-else-if="activeTab === 'bank'" class="bank-content">
                <div class="bank-header">
                    <h2>Reference Bank</h2>
                    <p>Upload and manage your research files. Files can be selected in any project.</p>
                </div>

                <FileUploader upload-mode="bank" @upload-complete="handleUploadComplete" />

                <div v-if="bankLoading" class="loading-state">
                    <Loader2 class="spinner" :size="32" />
                    <p>Loading files...</p>
                </div>

                <div v-else-if="bankFiles.length === 0" class="empty-state">
                    <Upload :size="48" class="empty-icon-svg" />
                    <h3>No files in Reference Bank</h3>
                    <p>Upload files using the button above to get started.</p>
                </div>

                <TransitionGroup v-else name="file-list" tag="div" class="file-grid" @before-leave="handleBeforeLeave">
                    <div v-for="file in sortedBankFiles" :key="file.relPath" class="file-card">
                        <div class="file-icon">
                            <FileText :size="24" />
                        </div>
                        <div class="file-info">
                            <div class="file-name" :title="getFileName(file.relPath)">{{ getFileName(file.relPath) }}
                            </div>
                            <div class="file-meta">{{ file.fileType }} · {{ Math.round((file.sizeBytes || 0) / 1024)
                            }}KB</div>
                        </div>
                        <div class="file-actions">
                            <button class="btn-icon" @click="handlePreview(file)" title="Preview">
                                <Search :size="16" />
                            </button>
                            <button class="btn-icon delete" @click="requestDelete(file)" title="Delete">
                                <Trash2 :size="16" />
                            </button>
                        </div>
                    </div>
                </TransitionGroup>
            </div>

            <!-- Settings Tab -->
            <div v-else-if="activeTab === 'settings'" class="settings-container">
                <aside class="settings-sidebar">
                    <nav class="settings-nav">
                        <button class="settings-nav-item" :class="{ active: settingsSection === 'preferences' }"
                            @click="settingsSection = 'preferences'">
                            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
                                fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"
                                stroke-linejoin="round">
                                <path
                                    d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
                                <circle cx="12" cy="12" r="3" />
                            </svg>
                            <span>Preferences</span>
                        </button>
                        <button class="settings-nav-item" :class="{ active: settingsSection === 'advanced' }"
                            @click="settingsSection = 'advanced'">
                            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"
                                fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"
                                stroke-linejoin="round">
                                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                                <line x1="9" y1="3" x2="9" y2="21"></line>
                            </svg>
                            <span>Advanced</span>
                        </button>
                    </nav>
                </aside>

                <main class="settings-content">
                    <!-- Preferences Section -->
                    <div v-if="settingsSection === 'preferences'" class="settings-section">
                        <h2 class="settings-section-title">Preferences</h2>
                        <p class="settings-section-desc">Customize your experience with theme, keyboard shortcuts, and
                            display
                            options.</p>

                        <!-- Theme -->
                        <div class="settings-group">
                            <h3 class="settings-group-title">Theme</h3>
                            <div class="settings-item">
                                <div class="settings-item-info">
                                    <label class="settings-label">Appearance</label>
                                    <p class="settings-desc">Choose your preferred color theme</p>
                                </div>
                                <select class="settings-select" :value="currentTheme"
                                    @change="(e) => setTheme((e.target as HTMLSelectElement).value as Theme)">
                                    <option value="light">Light</option>
                                    <option value="dark">Dark</option>
                                    <option value="system">System</option>
                                </select>
                            </div>
                        </div>

                        <!-- Submit Prompt Key -->
                        <div class="settings-group">
                            <h3 class="settings-group-title">Submit Prompt Key</h3>
                            <div class="settings-item">
                                <div class="settings-item-info">
                                    <label class="settings-label">Keyboard Shortcut</label>
                                    <p class="settings-desc">Choose how to submit your prompts</p>
                                </div>
                                <div class="settings-control">
                                    <div class="radio-group">
                                        <label class="radio-label">
                                            <input type="radio" name="submitKey" value="enter" checked>
                                            <span>Enter to send, Shift+Enter for new line</span>
                                        </label>
                                        <label class="radio-label">
                                            <input type="radio" name="submitKey" value="ctrl-enter">
                                            <span>Ctrl+Enter to send, Enter for new line</span>
                                        </label>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Display -->
                        <div class="settings-group">
                            <h3 class="settings-group-title">Display</h3>
                            <div class="settings-item">
                                <div class="settings-item-info">
                                    <label class="settings-label">Items Per Page</label>
                                    <p class="settings-desc">Maximum number of items to display in lists</p>
                                </div>
                                <div class="settings-control">
                                    <span class="settings-badge">Coming Soon</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Advanced Section -->
                    <div v-else-if="settingsSection === 'advanced'" class="settings-section-container">
                        <div class="settings-header">
                            <h2 class="settings-section-title">Advanced</h2>
                            <p class="settings-section-desc">Manage API configuration and perform advanced operations.
                            </p>
                        </div>

                        <div v-if="isLoadingSettings" class="loading-settings">Loading settings...</div>

                        <div v-else class="start-settings-content">
                            <!-- API Configuration Section -->
                            <section class="settings-card">
                                <div class="section-header">
                                    <div class="section-icon">
                                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"
                                            viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                                            stroke-linecap="round" stroke-linejoin="round">
                                            <path
                                                d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4" />
                                        </svg>
                                    </div>
                                    <div>
                                        <h4 class="section-title">API Configuration</h4>
                                        <p class="section-description">Configure your DeepSeek API key for AI-powered
                                            answers</p>
                                    </div>
                                </div>

                                <div class="section-content">
                                    <label class="form-label">DeepSeek API Key</label>
                                    <p class="form-hint">Get your key from <a href="https://platform.deepseek.com"
                                            target="_blank">platform.deepseek.com</a></p>

                                    <div class="current-key" v-if="settings?.hasApiKey">
                                        <span class="key-status valid">
                                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14"
                                                viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                                                stroke-linecap="round" stroke-linejoin="round">
                                                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                                                <polyline points="22 4 12 14.01 9 11.01" />
                                            </svg>
                                            Key configured
                                        </span>
                                        <span class="masked-key">{{ settings.maskedApiKey }}</span>
                                        <button class="btn-link danger" @click="handleDeleteApiKey"
                                            :disabled="isSaving">Remove</button>
                                    </div>

                                    <div class="api-input-row">
                                        <div class="input-group">
                                            <input v-model="apiKeyInput" :type="showApiKey ? 'text' : 'password'"
                                                class="form-input"
                                                :placeholder="settings?.hasApiKey ? 'Enter new key to replace' : 'sk-xxxxxxxxxxxxxxxx'" />
                                            <button class="input-addon" @click="showApiKey = !showApiKey" type="button">
                                                <svg v-if="showApiKey" xmlns="http://www.w3.org/2000/svg" width="16"
                                                    height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                                                    stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                                    <path
                                                        d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                                                    <line x1="1" x2="23" y1="1" y2="23" />
                                                </svg>
                                                <svg v-else xmlns="http://www.w3.org/2000/svg" width="16" height="16"
                                                    viewBox="0 0 24 24" fill="none" stroke="currentColor"
                                                    stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                                                    <circle cx="12" cy="12" r="3" />
                                                </svg>
                                            </button>
                                        </div>
                                        <div class="api-actions">
                                            <button class="btn btn-outline" @click="handleValidate"
                                                :disabled="isValidating || (!apiKeyInput && !settings?.hasApiKey)">
                                                {{ isValidating ? 'Validating...' : 'Validate' }}
                                            </button>
                                            <button class="btn btn-primary-sm" @click="handleSave"
                                                :disabled="isSaving || !apiKeyInput">
                                                {{ isSaving ? 'Saving...' : 'Save' }}
                                            </button>
                                        </div>
                                    </div>

                                    <div v-if="saveError" class="error-message">{{ saveError }}</div>

                                    <div class="validation-result" v-if="validationStatus !== 'none'">
                                        <span v-if="validationStatus === 'valid'" class="status valid">
                                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14"
                                                viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                                                stroke-linecap="round" stroke-linejoin="round">
                                                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                                                <polyline points="22 4 12 14.01 9 11.01" />
                                            </svg>
                                            {{ apiKeyStatusMessage }}
                                        </span>
                                        <span v-else class="status invalid">
                                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14"
                                                viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                                                stroke-linecap="round" stroke-linejoin="round">
                                                <circle cx="12" cy="12" r="10" />
                                                <line x1="15" x2="9" y1="9" y2="15" />
                                                <line x1="9" x2="15" y1="9" y2="15" />
                                            </svg>
                                            Invalid: {{ validationError || 'API key verification failed' }}
                                        </span>
                                    </div>

                                    <div v-if="balanceInfos.length" class="balance-panel">
                                        <div class="balance-header">
                                            <span class="balance-title">Remaining balance</span>
                                            <span v-if="balanceAvailable === false" class="balance-warning">Insufficient
                                                for API calls</span>
                                        </div>
                                        <div class="balance-list">
                                            <div v-for="info in balanceInfos" :key="info.currency" class="balance-item">
                                                <div class="balance-line">
                                                    <span class="balance-currency">{{ info.currency }}</span>
                                                    <span class="balance-amount">{{ info.totalBalance }}</span>
                                                </div>
                                                <div class="balance-meta">
                                                    Granted {{ info.grantedBalance }} · Topped up {{
                                                        info.toppedUpBalance }}
                                                </div>
                                            </div>
                                        </div>
                                    </div>

                                </div>
                            </section>

                            <!-- Danger Zone Section -->
                            <section class="settings-card danger-zone-card">
                                <div class="section-header">
                                    <div class="section-icon danger-icon">
                                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"
                                            viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                                            stroke-linecap="round" stroke-linejoin="round">
                                            <path
                                                d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
                                            <line x1="12" x2="12" y1="9" y2="13" />
                                            <line x1="12" x2="12.01" y1="17" y2="17" />
                                        </svg>
                                    </div>
                                    <div>
                                        <h4 class="section-title">Danger Zone</h4>
                                        <p class="section-description">Destructive actions that cannot be undone</p>
                                    </div>
                                </div>

                                <div class="section-content">
                                    <p class="form-hint">Clear all indexed chunks and chat sessions. Files will remain
                                        in the reference folder.</p>

                                    <div v-if="resetSuccess" class="success-message">{{ resetSuccess }}</div>
                                    <div v-if="resetError" class="error-message">{{ resetError }}</div>

                                    <button class="btn btn-danger-action" @click="handleResetClick"
                                        :disabled="isResetting">
                                        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14"
                                            viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                                            stroke-linecap="round" stroke-linejoin="round">
                                            <path d="M3 6h18" />
                                            <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
                                            <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
                                            <line x1="10" x2="10" y1="11" y2="17" />
                                            <line x1="14" x2="14" y1="11" y2="17" />
                                        </svg>
                                        {{ isResetting ? 'Clearing...' : 'Clear All Data' }}
                                    </button>
                                </div>
                            </section>
                        </div>
                    </div>
                </main>
            </div>
        </main>
    </div>

    <!-- Create Modal -->
    <Transition name="fade">
        <div v-if="showCreateModal" class="modal-mask" @click.self="showCreateModal = false">
            <div class="modal-container">
                <h2>Create New Study</h2>
                <div class="form-group">
                    <label>Project Name</label>
                    <input v-model="newProjectName" placeholder="e.g. Photovoltaic Research" autofocus />
                </div>
                <div class="form-group">
                    <label>Description (Optional)</label>
                    <textarea v-model="newProjectDesc" placeholder="What is this study about?" rows="3"></textarea>
                </div>
                <div class="form-group">
                    <label>Initial Content (Optional)</label>
                    <div class="file-select-row">
                        <span class="file-count" v-if="selectedFilesForCreate.size > 0">
                            {{ selectedFilesForCreate.size }} files selected
                        </span>
                        <span class="file-count placeholder" v-else>
                            Start with some references...
                        </span>
                        <button class="btn-outline-sm" @click="openFileSelectorForCreate">
                            Select Files
                        </button>
                    </div>
                </div>
                <div class="modal-actions">
                    <button class="btn-secondary" @click="showCreateModal = false">Cancel</button>
                    <button class="btn-primary" :disabled="!newProjectName.trim() || creating" @click="handleCreate">
                        <Loader2 v-if="creating" class="spinner" :size="16" />
                        <span>{{ creating ? 'Creating...' : 'Create Project' }}</span>
                    </button>
                </div>
            </div>
        </div>
    </Transition>

    <!-- File Preview Modal -->
    <FilePreviewModal v-model="showPreviewModal" :file="previewFile" />

    <!-- Delete Confirmation Modal -->
    <ConfirmationModal v-model="showDeleteModal" title="Delete File?"
        :message="fileToDelete ? `Delete '${getFileName(fileToDelete.relPath)}'? This will remove it from all projects. This action cannot be undone.` : ''"
        confirmText="Delete" @confirm="confirmDelete" @cancel="cancelDelete" />

    <!-- Delete Project Confirmation Modal -->
    <ConfirmationModal v-model="showDeleteProjectModal" title="Delete Project?"
        :message="projectToDelete ? `Delete '${projectToDelete.name}'? This will remove the project and all its notes. Files will remain in the Reference Bank.` : ''"
        confirmText="Delete" @confirm="confirmDeleteProject" @cancel="cancelDeleteProject" />

    <!-- Initial File Selector -->
    <BankFileSelectorModal v-model="showFileSelectorForCreate" :selected-files="selectedFilesForCreate"
        @confirm="handleInitialFilesSelected" />

    <!-- Reset Confirmation Modal -->
    <ConfirmationModal v-model="showResetConfirm" title="Clear All Data?"
        message="This will permanently delete all indexed chunks, search indexes, and chat sessions. Your files will remain in the reference folder. This action cannot be undone."
        confirm-text="Clear All Data" cancel-text="Cancel" @confirm="handleResetConfirm" />
</template>

<style scoped>
.project-hub-container {
    height: 100vh;
    background: var(--color-neutral-95);
    color: var(--text-primary);
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.hub-header {
    padding: 40px 60px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: var(--bg-panel);
    border-bottom: 1px solid var(--border-color);
}

.header-left .logo {
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--accent-color);
    font-weight: 700;
    font-size: 14px;
    margin-bottom: 8px;
}

.header-left h1 {
    margin: 0;
    font-size: 28px;
    font-weight: 800;
}

.header-right {
    display: flex;
    gap: 16px;
    align-items: center;
}

.btn-icon-header {
    background: transparent;
    border: none;
    padding: 10px;
    border-radius: 8px;
    cursor: pointer;
    color: var(--text-secondary);
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
}

.btn-icon-header:hover {
    background: var(--color-neutral-170);
    color: var(--text-primary);
}

.search-bar {
    display: flex;
    align-items: center;
    gap: 10px;
    background: var(--color-neutral-170);
    padding: 10px 16px;
    border-radius: 99px;
    min-width: 300px;
}

.search-bar input {
    background: transparent;
    border: none;
    font-size: 14px;
    width: 100%;
}

.search-bar input:focus {
    outline: none;
}

.hub-content {
    padding: 60px;
    flex: 1;
    overflow-y: auto;
}

.project-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 30px;
}

.create-card {
    border: 2px dashed var(--border-card);
    background: transparent;
    border-radius: 12px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.2s;
    min-height: 200px;
}

.create-card:hover {
    border-color: var(--accent-color);
    color: var(--accent-color);
    background: rgba(var(--accent-color-rgb), 0.02);
}

.plus-icon {
    width: 60px;
    height: 60px;
    border-radius: 50%;
    background: var(--bg-button);
    display: flex;
    align-items: center;
    justify-content: center;
}

.loading-state,
.empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 400px;
    text-align: center;
}

.empty-icon {
    font-size: 64px;
    margin-bottom: 20px;
}

.empty-state h2 {
    margin: 0 0 10px 0;
}

.empty-state p {
    color: var(--text-secondary);
    margin-bottom: 30px;
}

/* Modal Styles */
.modal-mask {
    position: fixed;
    inset: 0;
    background: var(--alpha-black-40);
    backdrop-filter: blur(4px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
}

.modal-container {
    background: var(--bg-panel);
    width: 500px;
    padding: 30px;
    border-radius: 16px;
    box-shadow: 0 20px 40px var(--alpha-black-10);
}

.modal-container h2 {
    margin: 0 0 24px 0;
    font-size: 20px;
}

.form-group {
    margin-bottom: 20px;
}

.form-group label {
    display: block;
    margin-bottom: 8px;
    font-size: 13px;
    font-weight: 600;
}

.form-group input,
.form-group textarea {
    width: 100%;
    padding: 12px;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    font-size: 14px;
    background: var(--bg-input);
    color: var(--text-primary);
    transition: all 0.2s;
}

.form-group input:focus,
.form-group textarea:focus {
    outline: none;
    border-color: var(--accent-bright);
    box-shadow: 0 0 0 3px rgba(var(--accent-color-rgb), 0.1);
}

.modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    margin-top: 30px;
}

.btn-primary {
    background: var(--accent-color);
    color: white;
    border: none;
    padding: 12px 24px;
    border-radius: 8px;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
}

.btn-secondary {
    background: var(--color-neutral-170);
    color: var(--text-primary);
    border: none;
    padding: 12px 24px;
    border-radius: 8px;
    font-weight: 600;
    cursor: pointer;
}

.spinner {
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

.fade-enter-active,
.fade-leave-active {
    transition: opacity 0.2s;
}

.fade-enter-from,
.fade-leave-to {
    opacity: 0;
}

/* Tabs */
.hub-tabs {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0 60px;
    background: var(--bg-card);
    border-bottom: 1px solid var(--border-color);
}

.tabs-left,
.tabs-right {
    display: flex;
    gap: 8px;
}

.tab-btn {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 20px;
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    color: var(--text-secondary);
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
}

.tab-btn:hover {
    color: var(--text-primary);
    background: var(--color-neutral-95);
}

.tab-btn.active {
    color: var(--accent-color);
    border-bottom-color: var(--accent-color);
}

/* Reference Bank */
.bank-content {
    max-width: 1200px;
    margin: 0 auto;
}

.bank-header {
    margin-bottom: 30px;
}

.bank-header h2 {
    margin: 0 0 8px 0;
    font-size: 24px;
    font-weight: 700;
}

.bank-header p {
    margin: 0;
    color: var(--text-secondary);
    font-size: 14px;
}

.file-grid {
    position: relative;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 16px;
    margin-top: 24px;
}

.file-list-move {
    transition: transform 360ms ease-out;
}

.file-list-enter-active,
.file-list-leave-active {
    transition: opacity 240ms ease, transform 240ms ease;
}

.file-list-enter-from,
.file-list-leave-to {
    opacity: 0;
    transform: translateY(14px) scale(0.98);
}

.file-list-leave-active {
    pointer-events: none;
}

.file-card {
    will-change: transform;
}

.project-card {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 20px;
    background: var(--bg-card);
    border: 1px solid var(--border-card);
    border-radius: 12px;
    cursor: pointer;
    transition: all 0.2s;
    min-height: 180px;
}

.project-card:hover {
    background: var(--bg-card-hover);
    border-color: var(--accent-bright);
    transform: translateY(-2px);
    box-shadow: 0 4px 12px var(--alpha-black-10);
}

.file-card {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px;
    background: var(--bg-card);
    border: 1px solid var(--border-card);
    border-radius: 12px;
    transition: all 0.2s;
    cursor: pointer;
}

.file-card:hover {
    border-color: var(--accent-bright);
    box-shadow: 0 2px 8px var(--alpha-black-08);
}

.file-icon {
    flex-shrink: 0;
    width: 40px;
    height: 40px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--color-neutral-180);
    border-radius: 8px;
    color: var(--accent-color);
}

.file-info {
    flex: 1;
    min-width: 0;
}

.file-name {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    margin-bottom: 4px;
}

.file-meta {
    font-size: 12px;
    color: var(--text-secondary);
    text-transform: uppercase;
}

.file-actions {
    display: flex;
    gap: 4px;
    opacity: 0;
    transition: opacity 0.2s;
}


.file-card:hover .file-actions {
    opacity: 1;
}

/* File Selection in Create Modal */
.file-select-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: var(--color-neutral-95);
    border: 1px solid var(--border-card);
    padding: 8px 12px;
    border-radius: 8px;
}

.file-count {
    font-size: 13px;
    color: var(--text-primary);
    font-weight: 500;
}

.file-count.placeholder {
    color: var(--text-secondary);
    font-style: italic;
}

.btn-outline-sm {
    background: var(--bg-card);
    border: 1px solid var(--border-input);
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.2s;
    color: var(--text-primary);
}

.btn-outline-sm:hover {
    border-color: var(--accent-color);
    color: var(--accent-color);
}

.file-actions {
    display: flex;
    gap: 4px;
    opacity: 0;
    transition: opacity 0.2s;
}

.bank-file-item:hover .file-actions {
    opacity: 1;
}

.file-action-btn {
    width: 28px;
    height: 28px;
    border-radius: 6px;
    border: none;
    background: transparent;
    color: var(--text-secondary);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
}

.file-action-btn:hover {
    background: var(--bg-icon-hover);
    color: var(--text-primary);
}

.file-action-btn.delete:hover {
    color: var(--color-red-600);
}

.btn-icon {
    background: transparent;
    border: none;
    padding: 4px;
    width: 20px;
    height: 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    color: var(--text-secondary);
    border-radius: 4px;
    transition: all 0.2s;
}

.btn-icon:hover {
    background: var(--bg-icon-hover);
    color: var(--text-primary);
}

.btn-icon.delete:hover {
    background: var(--bg-icon-hover);
    color: var(--color-red-600);
}

.empty-icon-svg {
    color: var(--color-neutral-400);
    margin-bottom: 16px;
}

.empty-state h3 {
    margin: 0 0 8px 0;
    font-size: 18px;
}

/* Settings Layout */
.settings-layout {
    display: flex;
    height: 100%;
    max-width: 1400px;
    margin: 0 auto;
}

.settings-sidebar {
    width: 280px;
    border-right: 1px solid var(--border-card);
    padding: 40px 0;
    flex-shrink: 0;
}

.settings-nav {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 0 20px;
}

.settings-nav-item {
    display: flex;
    align-items: center;
    padding: 12px 16px;
    background: transparent;
    border: none;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    color: var(--text-secondary);
    cursor: pointer;
    text-align: left;
    transition: all 0.2s;
}

.settings-nav-item:hover {
    background: var(--bg-card-hover);
    color: var(--accent-bright);
}

.settings-nav-item.active {
    background: var(--accent-soft, var(--color-accent-50));
    color: var(--accent-color);
    font-weight: 600;
}

.settings-content {
    flex: 1;
    padding: 40px 60px;
    overflow-y: auto;
}

.settings-placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 400px;
    text-align: center;
    color: var(--text-secondary);
}

.settings-placeholder p {
    margin: 8px 0;
    font-size: 14px;
}

/* Settings Container Layout */
.settings-container {
    display: flex;
    height: 100%;
    gap: 0;
}

/* Settings Sidebar */
.settings-sidebar {
    width: 240px;
    border-right: 1px solid var(--border-color);
    background: var(--color-neutral-100);
    padding: 24px 0;
}

.settings-nav {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 0 12px;
}

.settings-nav-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 12px;
    border: none;
    background: transparent;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.2s;
    text-align: left;
}

.settings-nav-item:hover {
    background: var(--color-neutral-150);
    color: var(--text-primary);
}

.settings-nav-item.active {
    background: var(--color-white);
    color: var(--accent-color);
    box-shadow: 0 1px 3px var(--alpha-black-10);
}

.settings-nav-item svg {
    flex-shrink: 0;
    color: currentColor;
}

/* Settings Section */
.settings-section {
    max-width: 800px;
}

.settings-section-title {
    font-size: 24px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0 0 8px 0;
}

.settings-section-desc {
    font-size: 14px;
    color: var(--text-secondary);
    margin: 0 0 32px 0;
    line-height: 1.5;
}

/* Settings Group */
.settings-group {
    margin-bottom: 40px;
    padding-bottom: 32px;
    border-bottom: 1px solid var(--border-color);
}

.settings-group:last-child {
    border-bottom: none;
    margin-bottom: 0;
    padding-bottom: 0;
}

.settings-group-title {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0 0 16px 0;
}

/* Settings Item */
.settings-item {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 24px;
    padding: 16px 0;
}

.settings-item-info {
    flex: 1;
}

.settings-label {
    display: block;
    font-size: 14px;
    font-weight: 500;
    color: var(--text-primary);
    margin-bottom: 4px;
}

.settings-desc {
    font-size: 13px;
    color: var(--text-secondary);
    margin: 0;
    line-height: 1.5;
}

.settings-control {
    display: flex;
    align-items: center;
    gap: 12px;
}

/* Settings Select */
.settings-select {
    padding: 8px 12px;
    border: 1px solid var(--border-input);
    border-radius: 6px;
    font-size: 14px;
    color: var(--text-primary);
    background: var(--color-white);
    cursor: pointer;
    transition: all 0.2s;
}

/* Radio Group */
.radio-group {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.radio-label {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    color: var(--text-primary);
    cursor: pointer;
}

.radio-label input[type="radio"] {
    width: 16px;
    height: 16px;
    cursor: pointer;
}

.radio-label:hover {
    color: var(--accent-color);
}

/* Settings Badge */
.settings-badge {
    padding: 4px 8px;
    background: var(--color-neutral-150);
    border-radius: 4px;
    font-size: 12px;
    font-weight: 500;
    color: var(--text-secondary);
}

/* Danger Zone */
.settings-group.danger-zone {
    border-color: var(--color-red-200);
    background: var(--color-red-50);
    padding: 20px;
    border-radius: 8px;
}

.settings-group.danger-zone .settings-group-title {
    color: var(--color-red-700);
}

.btn-danger {
    padding: 8px 16px;
    background: var(--color-red-600);
    color: white;
    border: none;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
}

.btn-danger:hover {
    background: var(--color-red-700);
}

.btn-secondary {
    padding: 8px 16px;
    background: var(--color-neutral-150);
    color: var(--text-primary);
    border: 1px solid var(--border-card);
    border-radius: 6px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
}

.btn-secondary:hover {
    background: var(--bg-card-hover);
    border-color: var(--accent-bright);
}

.bank-file-item:hover {
    background: var(--bg-card-hover);
    border-color: var(--accent-bright);
}

/* Settings Responsive Layout */
@media (max-width: 1050px) {
    .settings-item {
        flex-direction: column;
        align-items: flex-start;
        gap: 12px;
    }

    .settings-item-info {
        width: 100%;
    }

    .settings-control {
        width: 100%;
        justify-content: flex-start;
    }

    .settings-select {
        width: 100%;
        max-width: 300px;
    }
}
</style>

<style scoped>
/* Advanced Settings Styles */
.settings-section-container {
    padding-bottom: 40px;
}

.settings-header {
    margin-bottom: 24px;
}

.loading-settings {
    text-align: center;
    color: var(--text-secondary);
    padding: 40px;
}

.start-settings-content {
    display: flex;
    flex-direction: column;
    gap: 24px;
}

.settings-card {
    border: 1px solid var(--color-neutral-250);
    border-radius: 10px;
    background: var(--bg-card);
    overflow: hidden;
}

.section-header {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 16px;
    background: var(--color-neutral-100);
    border-bottom: 1px solid var(--color-neutral-250);
}

.section-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    border-radius: 6px;
    background: var(--accent-soft, var(--color-accent-50));
    color: var(--accent-color, var(--color-accent-600));
    flex-shrink: 0;
}

.section-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0 0 2px 0;
}

.section-description {
    font-size: 12px;
    color: var(--text-secondary);
    margin: 0;
}

.section-content {
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.form-label {
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
    font-size: 14px;
}

.form-hint {
    font-size: 13px;
    color: var(--text-secondary);
    margin: 0;
}

.form-hint a {
    color: var(--accent-color, var(--color-accent-600));
}

.current-key {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    background: var(--color-neutral-100);
    border-radius: 8px;
    font-size: 13px;
}

.key-status {
    display: flex;
    align-items: center;
    gap: 4px;
    font-weight: 500;
}

.key-status.valid {
    color: var(--color-success-700);
}

.masked-key {
    font-family: monospace;
    font-size: 12px;
    color: var(--text-secondary);
    flex: 1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.btn-link {
    background: none;
    border: none;
    font-size: 13px;
    cursor: pointer;
    padding: 4px 8px;
}

.btn-link.danger {
    color: var(--color-danger-700);
}

.btn-link.danger:hover {
    text-decoration: underline;
}

.input-group {
    display: flex;
    border: 1px solid var(--color-neutral-250);
    border-radius: 8px;
    overflow: hidden;
}

.input-group:focus-within {
    border-color: var(--accent-color);
    box-shadow: 0 0 0 2px var(--alpha-accent-10);
}

.form-input {
    flex: 1;
    padding: 10px 12px;
    border: none;
    font-size: 14px;
    font-family: inherit;
    outline: none;
    background: var(--bg-input);
    color: var(--text-primary);
}

.input-addon {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0 12px;
    background: var(--color-neutral-100);
    border: none;
    border-left: 1px solid var(--color-neutral-250);
    cursor: pointer;
    color: var(--text-secondary);
}

.input-addon:hover {
    color: var(--text-primary);
    background: var(--color-neutral-220);
}

.error-message {
    color: var(--color-danger-700);
    font-size: 13px;
}

.success-message {
    color: var(--color-success-700);
    font-size: 13px;
    padding: 10px 12px;
    background: var(--color-success-50);
    border-radius: 8px;
    border: 1px solid var(--color-success-200);
}

.validation-result {
    padding: 10px 12px;
    border-radius: 8px;
    background: var(--bg-panel);
    border: 1px solid var(--border-color);
}

.validation-result .status {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    font-weight: 500;
}

.validation-result .status.valid {
    color: var(--color-success-700);
}

.validation-result .status.invalid {
    color: var(--color-danger-700);
}

.balance-panel {
    border: 1px solid var(--color-neutral-250);
    border-radius: 8px;
    background: var(--color-neutral-100);
    padding: 10px 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.balance-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
}

.balance-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
}

.balance-warning {
    font-size: 12px;
    color: var(--color-danger-700);
    background: var(--color-danger-50);
    border: 1px solid var(--color-danger-200);
    padding: 2px 8px;
    border-radius: 999px;
}

.balance-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.balance-item {
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.balance-line {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    font-size: 13px;
    color: var(--text-primary);
}

.balance-currency {
    font-weight: 600;
}

.balance-amount {
    font-variant-numeric: tabular-nums;
}

.balance-meta {
    font-size: 12px;
    color: var(--text-secondary);
}

.api-input-row {
    display: flex;
    align-items: center;
    gap: 12px;
}

.api-input-row .input-group {
    flex: 1;
}

.api-actions {
    display: flex;
    gap: 8px;
    flex-shrink: 0;
}

.btn-primary-sm {
    background: var(--accent-color);
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
}

.btn-primary-sm:hover:not(:disabled) {
    background: var(--accent-dark);
}

.btn-primary-sm:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.btn-outline {
    background: transparent;
    color: var(--accent-color);
    border: 1px solid var(--accent-color);
    padding: 8px 16px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
}

.btn-outline:hover:not(:disabled) {
    background: var(--accent-soft);
}

.btn-outline:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

/* Danger Zone specific */
.danger-zone-card {
    border-color: var(--color-danger-200);
}

.danger-zone-card .section-header {
    background: var(--color-danger-50);
    border-bottom-color: var(--color-danger-200);
}

.danger-icon {
    background: var(--color-danger-100) !important;
    color: var(--color-danger-700) !important;
}

.danger-zone-card .section-title {
    color: var(--color-danger-700);
}

.danger-zone-card .section-description {
    color: var(--color-danger-600);
}

.btn-danger-action {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    background: var(--color-danger-600);
    color: white;
    border: none;
    padding: 10px 16px;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
    width: fit-content;
}

.btn-danger-action:hover:not(:disabled) {
    background: var(--color-danger-700);
}

.btn-danger-action:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

@media (max-width: 640px) {
    .api-input-row {
        flex-direction: column;
        align-items: stretch;
    }

    .api-actions {
        justify-content: flex-end;
    }
}
</style>
