<script setup lang="ts">
import { ref, onMounted } from "vue"
import { useRouter } from "vue-router"
import { fetchProjects, createProject } from "../api/client"
import type { Project } from "../types"
import ProjectCard from "./ProjectCard.vue"
import { Plus, Search, Loader2 } from "lucide-vue-next"

const router = useRouter()
const projects = ref<Project[]>([])
const loading = ref(true)
const searchQuery = ref("")
const showCreateModal = ref(false)
const newProjectName = ref("")
const newProjectDesc = ref("")
const creating = ref(false)

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

async function handleCreate() {
    if (!newProjectName.value.trim()) return
    try {
        creating.value = true
        const p = await createProject({
            name: newProjectName.value,
            description: newProjectDesc.value
        })
        projects.value.push(p)
        showCreateModal.value = false
        newProjectName.value = ""
        newProjectDesc.value = ""
        // Navigate to the new project
        openProject(p.id)
    } catch (err) {
        console.error("Failed to create project:", err)
    } finally {
        creating.value = false
    }
}

function openProject(id: string) {
    router.push(`/project/${id}`)
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

        <main class="hub-content">
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
                <ProjectCard v-for="p in projects" :key="p.id" :project="p" @open="openProject" />

                <div class="create-card" @click="showCreateModal = true">
                    <div class="plus-icon">
                        <Plus :size="32" />
                    </div>
                    <span>Start New Project</span>
                </div>
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
    </div>
</template>

<style scoped>
.project-hub-container {
    min-height: 100vh;
    background: #f8f9fc;
    color: var(--text-primary);
    display: flex;
    flex-direction: column;
}

.hub-header {
    padding: 40px 60px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: white;
    border-bottom: 1px solid #eee;
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
    gap: 20px;
    align-items: center;
}

.search-bar {
    display: flex;
    align-items: center;
    gap: 10px;
    background: #f1f3f9;
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
}

.project-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 30px;
}

.create-card {
    border: 2px dashed #ddd;
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
    background: #f0f3f8;
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
    background: rgba(0, 0, 0, 0.4);
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
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
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
    border: 1px solid #ddd;
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
    background: #f1f3f9;
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
</style>
