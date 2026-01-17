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
const activeTab = ref<'projects' | 'bank'>('projects')
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
                <button class="btn-icon-header" @click="showSettingsModal = true" title="Settings">
                    <Settings :size="20" />
                </button>
                <button class="btn-primary" @click="showCreateModal = true">
                    <Plus :size="18" />
                    <span>New Study</span>
                </button>
            </div>
        </header>

        <!-- Tabs -->
        <div class="hub-tabs">
            <button class="tab-btn" :class="{ active: activeTab === 'projects' }" @click="activeTab = 'projects'">
                <Search :size="16" />
                <span>Projects</span>
            </button>
            <button class="tab-btn" :class="{ active: activeTab === 'bank' }" @click="switchToBank">
                <FileText :size="16" />
                <span>Reference Bank</span>
            </button>
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
            <div v-else class="bank-content">
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
                            <div class="file-name" :title="getFileName(file.relPath)">{{ getFileName(file.relPath) }}</div>
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
        </main>

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
                        <button class="btn-primary" :disabled="!newProjectName.trim() || creating"
                            @click="handleCreate">
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
    </div>
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
    gap: 8px;
    padding: 0 60px;
    background: white;
    border-bottom: 1px solid var(--color-neutral-215);
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
</style>
