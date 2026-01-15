<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue'
import { Search, FileText, MessageSquare, StickyNote, CornerDownLeft } from 'lucide-vue-next'
import type { ChatMessage, EvidenceChunk, ManifestEntry, ChatSession } from '../types'

const props = defineProps<{
    visible: boolean,
    projectFiles: Set<string>,
    pinnedEvidence: Map<string, EvidenceChunk>,
    chatStore: Record<string, ChatMessage[]>,
    chatSessions: ChatSession[],
    manifest: ManifestEntry[]
}>()

const emit = defineEmits<{
    (e: 'close'): void,
    (e: 'navigate', item: any): void
}>()

const query = ref('')
const selectedIndex = ref(0)
const inputRef = ref<HTMLInputElement | null>(null)

// Focus input when opened
watch(() => props.visible, (val) => {
    if (val) {
        query.value = ''
        selectedIndex.value = 0
        nextTick(() => inputRef.value?.focus())
    }
})

interface SearchResult {
    type: 'chat' | 'note' | 'file'
    id: string
    title: string
    subtitle?: string
    icon: any
    data: any
}

const results = computed(() => {
    const q = query.value.trim().toLowerCase()
    if (!q) return []

    const res: SearchResult[] = []

    // 1. Search Files
    for (const file of props.manifest) {
        if (props.projectFiles.has(file.relPath)) {
            if (file.relPath.toLowerCase().includes(q)) {
                res.push({
                    type: 'file',
                    id: file.relPath,
                    title: file.relPath.split('/').pop() || file.relPath,
                    subtitle: file.relPath,
                    icon: FileText,
                    data: file
                })
            }
        }
    }

    // 2. Search Notebook
    for (const note of props.pinnedEvidence.values()) {
        if (note.text.toLowerCase().includes(q) || note.path.toLowerCase().includes(q)) {
            res.push({
                type: 'note',
                id: note.chunkId,
                title: note.text.slice(0, 60) + '...',
                subtitle: `Notebook • ${note.path.split('/').pop()}`,
                icon: StickyNote,
                data: note
            })
        }
    }

    // 3. Search Conversations
    for (const session of props.chatSessions) {
        // Search title
        if (session.title.toLowerCase().includes(q)) {
            res.push({
                type: 'chat',
                id: session.id,
                title: session.title,
                subtitle: 'Conversation',
                icon: MessageSquare,
                data: { sessionId: session.id, messageId: null }
            })
        }

        // Search messages
        const messages = props.chatStore[session.id] || []
        for (const msg of messages) {
            if (msg.role === 'user' && msg.content.toLowerCase().includes(q)) {
                res.push({
                    type: 'chat',
                    id: session.id + '-' + msg.id,
                    title: session.title,
                    subtitle: `User: ${msg.content.slice(0, 50)}...`,
                    icon: MessageSquare,
                    data: { sessionId: session.id, messageId: msg.id }
                })
            }
        }
    }

    // Limit results
    return res.slice(0, 20)
})

function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'ArrowDown') {
        e.preventDefault()
        if (results.value.length) {
            selectedIndex.value = (selectedIndex.value + 1) % results.value.length
        }
    } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        if (results.value.length) {
            selectedIndex.value = (selectedIndex.value - 1 + results.value.length) % results.value.length
        }
    } else if (e.key === 'Enter') {
        e.preventDefault()
        if (results.value.length) {
            selectItem(results.value[selectedIndex.value])
        }
    } else if (e.key === 'Escape') {
        emit('close')
    }
}

function selectItem(item: SearchResult) {
    if (!item) return
    emit('navigate', item)
    emit('close')
}

</script>

<template>
    <transition name="fade">
        <div v-if="visible" class="palette-backdrop" @click="emit('close')">
            <div class="palette-modal" @click.stop>
                <div class="palette-header">
                    <Search class="search-icon" :size="20" />
                    <input ref="inputRef" v-model="query" placeholder="Search files, notes, or conversations..."
                        class="palette-input" @keydown="handleKeydown" />
                    <div class="palette-esc">ESC</div>
                </div>

                <div class="palette-body">
                    <div v-if="results.length === 0 && query" class="empty-state">
                        No results found.
                    </div>
                    <div v-else-if="results.length === 0 && !query" class="empty-state">
                        Type to search...
                    </div>

                    <div v-else class="results-list">
                        <div v-for="(item, idx) in results" :key="item.id" class="result-item"
                            :class="{ selected: idx === selectedIndex }" @click="selectItem(item)"
                            @mouseenter="selectedIndex = idx">
                            <component :is="item.icon" :size="18" class="result-icon" />
                            <div class="result-content">
                                <div class="result-title">{{ item.title }}</div>
                                <div class="result-subtitle">{{ item.subtitle }}</div>
                            </div>
                            <CornerDownLeft v-if="idx === selectedIndex" :size="14" class="enter-icon" />
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </transition>
</template>

<style scoped>
.palette-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.4);
    backdrop-filter: blur(2px);
    z-index: 1000;
    display: flex;
    justify-content: center;
    align-items: flex-start;
    padding-top: 15vh;
}

.palette-modal {
    width: 600px;
    max-width: 90%;
    background: white;
    border-radius: 12px;
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.2);
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.palette-header {
    display: flex;
    align-items: center;
    padding: 16px;
    border-bottom: 1px solid #f0f0f0;
    gap: 12px;
}

.search-icon {
    color: #999;
}

.palette-input {
    flex: 1;
    border: none;
    font-size: 16px;
    outline: none;
    color: #333;
}

.palette-esc {
    font-size: 11px;
    background: #f0f0f0;
    padding: 4px 8px;
    border-radius: 4px;
    color: #777;
}

.palette-body {
    max-height: 400px;
    overflow-y: auto;
}

.empty-state {
    padding: 32px;
    text-align: center;
    color: #999;
    font-size: 14px;
}

.result-item {
    display: flex;
    align-items: center;
    padding: 12px 16px;
    gap: 12px;
    cursor: pointer;
    border-left: 2px solid transparent;
}

.result-item.selected {
    background: #f5f7fa;
    border-left-color: var(--accent-color);
}

.result-icon {
    color: #777;
}

.result-content {
    flex: 1;
    overflow: hidden;
}

.result-title {
    font-size: 14px;
    font-weight: 500;
    color: #333;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.result-subtitle {
    font-size: 12px;
    color: #888;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.enter-icon {
    color: #999;
}

.fade-enter-active,
.fade-leave-active {
    transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
    opacity: 0;
}
</style>
