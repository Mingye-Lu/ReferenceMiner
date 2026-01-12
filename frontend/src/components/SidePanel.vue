<script setup lang="ts">
import { ref, inject, type Ref } from "vue"
import type { ManifestEntry } from "../types"

const activeTab = ref<"corpus" | "chats">("corpus")
const manifest = inject<Ref<ManifestEntry[]>>("manifest")!
const selectedFiles = inject<Ref<Set<string>>>("selectedFiles")!

const props = defineProps<{ activeChatId?: string }>()
const emit = defineEmits<{
  (event: 'preview', file: ManifestEntry): void
  (event: 'select-chat', id: string): void
  (event: 'new-chat'): void
}>()

const mockChats = [
  { id: "1", title: "光伏成本分析", time: "2h ago", meta: "5 refs" },
  { id: "2", title: "初始调研", time: "Yesterday", meta: "2 refs" }
]

function toggleFile(path: string) {
  if (selectedFiles.value.has(path)) selectedFiles.value.delete(path)
  else selectedFiles.value.add(path)
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
      <div v-if="manifest.length === 0" class="empty-msg">No files found.</div>

      <div v-for="file in manifest" :key="file.relPath" class="file-item"
        :class="{ selected: selectedFiles.has(file.relPath) }">
        <div @click.stop="toggleFile(file.relPath)" style="display:flex; align-items:center; padding-right:8px;">
          <input type="checkbox" class="custom-checkbox" :checked="selectedFiles.has(file.relPath)" readonly />
        </div>

        <div class="file-info" @click="handlePreview(file)">
          <div class="file-name" :title="file.relPath">{{ file.relPath }}</div>
          <div class="file-meta">{{ file.fileType }} · {{ Math.round((file.sizeBytes || 0) / 1024) }}KB</div>
        </div>

        <button class="icon-btn preview-btn" @click="(e) => handlePreview(file, e)" title="Preview">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" />
            <circle cx="12" cy="12" r="3" />
          </svg>
        </button>
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
        <div v-for="chat in mockChats" :key="chat.id" class="chat-item"
          :class="{ active: props.activeChatId === chat.id }" @click="selectChat(chat.id)">
          <div class="chat-title">{{ chat.title }}</div>
          <div class="chat-meta">{{ chat.time }} · {{ chat.meta }}</div>
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.empty-msg {
  padding: 20px;
  font-size: 12px;
  color: #888;
  text-align: center;
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

.preview-btn {
  opacity: 0;
  transition: opacity 0.2s;
}

.file-item:hover .preview-btn {
  opacity: 1;
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
  transition: all 0.2s;
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
</style>