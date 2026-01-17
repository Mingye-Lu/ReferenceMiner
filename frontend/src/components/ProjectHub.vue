<script setup lang="ts">
import { ref, onMounted, computed } from "vue"
import { useRouter } from "vue-router"
import { fetchProjects, createProject, fetchBankManifest, deleteFile, deleteProject, selectProjectFiles } from "../api/client"
import type { Project, ManifestEntry } from "../types"
import ProjectCard from "./ProjectCard.vue"
import FileUploader from "./FileUploader.vue"
import FilePreviewModal from "./FilePreviewModal.vue"
import ConfirmationModal from "./ConfirmationModal.vue"
import BankFileSelectorModal from "./BankFileSelectorModal.vue"
import SettingsModal from "./SettingsModal.vue"
import { Plus, Search, Loader2, Upload, FileText, Trash2, Settings } from "lucide-vue-next"
import { getFileName } from "../utils"

const router = useRouter()
const activeTab = ref<'projects' | 'bank' | 'settings'>('projects')
const settingsSection = ref<'preferences' | 'advanced'>('preferences')
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
const showSettingsModal = ref(false)

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

onMounted(loadProjects)
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
                                <div class="settings-control">
                                    <select class="settings-select" disabled>
                                        <option>Light</option>
                                        <option>Dark</option>
                                        <option>System</option>
                                    </select>
                                    <span class="settings-badge">Coming Soon</span>
                                </div>
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
                    <div v-else-if="settingsSection === 'advanced'" class="settings-section">
                        <h2 class="settings-section-title">Advanced</h2>
                        <p class="settings-section-desc">Manage API configuration and perform advanced operations.</p>

                        <!-- API Key -->
                        <div class="settings-group">
                            <h3 class="settings-group-title">API Key</h3>
                            <div class="settings-item">
                                <div class="settings-item-info">
                                    <label class="settings-label">OpenAI API Key</label>
                                    <p class="settings-desc">Configure your API key for AI features</p>
                                </div>
                                <div class="settings-control">
                                    <button class="btn-secondary" @click="showSettingsModal = true">Configure</button>
                                </div>
                            </div>
                        </div>

                        <!-- Danger Zone -->
                        <div class="settings-group danger-zone">
                            <h3 class="settings-group-title">Danger Zone</h3>
                            <div class="settings-item">
                                <div class="settings-item-info">
                                    <label class="settings-label">Reset All Data</label>
                                    <p class="settings-desc">Permanently delete all projects and data</p>
                                </div>
                                <div class="settings-control">
                                    <button class="btn-danger" @click="showSettingsModal = true">Reset</button>
                                </div>
                            </div>
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

    <!-- Settings Modal -->
    <SettingsModal v-model="showSettingsModal" @reset="handleDataReset" />
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
    background: white;
    border-bottom: 1px solid var(--color-neutral-215);
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
    border: 2px dashed var(--color-neutral-350);
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
    background: var(--color-neutral-180);
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
    background: white;
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
    border: 1px solid var(--color-neutral-350);
    border-radius: 8px;
    font-size: 14px;
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
    background: white;
    border-bottom: 1px solid var(--color-neutral-215);
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

.file-card {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px;
    background: white;
    border: 1px solid var(--color-neutral-240);
    border-radius: 12px;
    transition: all 0.2s;
    cursor: pointer;
}

.file-card:hover {
    border-color: var(--accent-color);
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
    border: 1px solid var(--color-neutral-240);
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
    background: white;
    border: 1px solid var(--color-neutral-300);
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

.btn-icon {
    background: transparent;
    border: none;
    padding: 6px;
    border-radius: 6px;
    cursor: pointer;
    color: var(--text-secondary);
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
}

.btn-icon:hover {
    background: var(--color-neutral-220);
    color: var(--text-primary);
}

.btn-icon.delete:hover {
    background: var(--color-danger-25);
    color: var(--color-danger-700);
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
    border-right: 1px solid var(--color-neutral-240);
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
    background: var(--color-neutral-120);
    color: var(--text-primary);
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
    border-right: 1px solid var(--color-neutral-215);
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
    border-bottom: 1px solid var(--color-neutral-200);
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
    border: 1px solid var(--color-neutral-250);
    border-radius: 6px;
    font-size: 14px;
    color: var(--text-primary);
    background: var(--color-white);
    cursor: pointer;
    transition: all 0.2s;
}

.settings-select:hover:not(:disabled) {
    border-color: var(--color-neutral-350);
}

.settings-select:disabled {
    opacity: 0.5;
    cursor: not-allowed;
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
    border: 1px solid var(--color-neutral-250);
    border-radius: 6px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
}

.btn-secondary:hover {
    background: var(--color-neutral-200);
    border-color: var(--color-neutral-350);
}
</style>
