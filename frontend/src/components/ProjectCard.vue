<script setup lang="ts">
import type { Project } from "../types"
import { Folder, Clock, FileText, StickyNote, Trash2 } from "lucide-vue-next"

const props = defineProps<{
    project: Project
}>()

const emit = defineEmits<{
    (e: "open", id: string): void
    (e: "delete", id: string): void
}>()

function formatTime(epoch: number) {
    return new Date(epoch * 1000).toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    })
}

function handleDelete(e: Event) {
    e.stopPropagation()
    emit('delete', props.project.id)
}
</script>

<template>
    <div class="project-card" @click="emit('open', project.id)">
        <div class="card-top">
            <div class="project-icon">
                <Folder v-if="!project.icon" :size="24" />
                <span v-else class="emoji-icon">{{ project.icon }}</span>
            </div>
            <div class="card-top-right">
                <button class="delete-btn" @click="handleDelete" title="Delete project">
                    <Trash2 :size="14" />
                </button>
                <div class="last-active">
                    <Clock :size="12" />
                    <span>{{ formatTime(project.lastActive) }}</span>
                </div>
            </div>
        </div>

        <div class="card-body">
            <h3 class="project-name">{{ project.name }}</h3>
            <p v-if="project.description" class="project-desc">{{ project.description }}</p>
        </div>

        <div class="card-footer">
            <div class="stat">
                <FileText :size="14" />
                <span>{{ project.fileCount }} files</span>
            </div>
            <div class="stat">
                <StickyNote :size="14" />
                <span>{{ project.noteCount }} notes</span>
            </div>
        </div>
    </div>
</template>

<style scoped>
.project-card {
    background: white;
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 20px;
    cursor: pointer;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    display: flex;
    flex-direction: column;
    gap: 16px;
    position: relative;
    overflow: hidden;
}

.project-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 12px 24px rgba(0, 0, 0, 0.08);
    border-color: var(--accent-color);
}

.card-top {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
}

.card-top-right {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 8px;
}

.delete-btn {
    background: transparent;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
    padding: 4px;
    border-radius: 4px;
    display: flex;
    align-items: center;
    opacity: 0;
    transition: all 0.2s;
}

.project-card:hover .delete-btn {
    opacity: 1;
}

.delete-btn:hover {
    background: #fff0f0;
    color: #d32f2f;
}

.project-icon {
    width: 44px;
    height: 44px;
    background: #f0f4ff;
    color: var(--accent-color);
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.emoji-icon {
    font-size: 24px;
}

.last-active {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 11px;
    color: var(--text-secondary);
}

.card-body {
    flex: 1;
}

.project-name {
    margin: 0 0 6px 0;
    font-size: 16px;
    font-weight: 700;
    color: var(--text-primary);
}

.project-desc {
    margin: 0;
    font-size: 13px;
    color: var(--text-secondary);
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

.card-footer {
    display: flex;
    gap: 16px;
    padding-top: 16px;
    border-top: 1px solid #f5f5f5;
}

.stat {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--text-secondary);
}
</style>
