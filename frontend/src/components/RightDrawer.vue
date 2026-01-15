<script setup lang="ts">
import { ref, inject, watch, nextTick, type Ref } from "vue"
import type { EvidenceChunk, ManifestEntry } from "../types"

const props = defineProps<{
  tab: "reader" | "notebook"
  evidence: EvidenceChunk | null
  highlightNoteId: string | null
  isOpen?: boolean
}>()

defineEmits<{ (event: 'close'): void }>()

const togglePin = inject<(item: EvidenceChunk) => void>("togglePin")!
const isPinned = inject<(id: string) => boolean>("isPinned")!
const pinnedEvidenceMap = inject<Ref<Map<string, EvidenceChunk>>>("pinnedEvidenceMap")!
const openPreview = inject<(file: ManifestEntry) => void>("openPreview")!
const manifest = inject<Ref<ManifestEntry[]>>("manifest")!

const currentTab = ref(props.tab)
watch(() => props.tab, (v) => currentTab.value = v)

// Notebook Logic
const notebookList = ref<EvidenceChunk[]>([])
// [新增] 暂存被移除的 ID，防止列表抖动
const pendingRemovals = ref(new Set<string>())

function refreshNotebook() {
  if (pinnedEvidenceMap.value) {
    // 重新加载时，清除 pending 状态
    pendingRemovals.value.clear()
    notebookList.value = Array.from(pinnedEvidenceMap.value.values())
  }
}

// [逻辑修正] 在笔记本中点击取消钉选
function handleNotebookUnpin(item: EvidenceChunk) {
  if (pendingRemovals.value.has(item.chunkId)) {
    // 撤销待移除状态
    pendingRemovals.value.delete(item.chunkId)
  } else {
    // 标记为待移除 (视觉变灰)
    pendingRemovals.value.add(item.chunkId)
  }
  // 全局状态移除/恢复 (影响其他地方的状态)
  togglePin(item)
}

watch(currentTab, (val) => {
  if (val === 'notebook') refreshNotebook()
})

// [NEW] Refresh notebook when drawer closes to clean up pending removals
watch(() => props.isOpen, (val) => {
  if (val === false) {
    refreshNotebook()
  }
})

// 监听全局 Map 变化
watch(pinnedEvidenceMap, (newMap) => {
  // 如果是新增的，加入列表
  for (const [id, item] of newMap.entries()) {
    if (!notebookList.value.find(i => i.chunkId === id)) {
      notebookList.value.unshift(item)
    }
  }

  // 如果是移除的，只有在不在 pendingRemovals 里才移除
  // (意味着是在外部 Reference Card 点击的取消)
  if (currentTab.value === 'notebook') {
    notebookList.value = notebookList.value.filter(item => {
      // 如果还在全局 map 里，保留
      if (newMap.has(item.chunkId)) return true
      // 如果不在全局 map，但在 pendingRemovals，保留显示（直到刷新）
      if (pendingRemovals.value.has(item.chunkId)) return true
      // 否则移除
      return false
    })
  }
}, { deep: true })

const contentRef = ref<HTMLElement | null>(null)
watch(() => props.evidence, (newVal) => {
  if (newVal) {
    currentTab.value = 'reader'
    nextTick(() => {
      // [修正] 简单定位到顶部
      if (contentRef.value) contentRef.value.scrollTop = 0
    })
  }
})

// [新增] Notebook 定位高亮
watch(() => props.highlightNoteId, (id) => {
  if (id && currentTab.value === 'notebook') {
    nextTick(() => {
      const el = document.getElementById(`note-${id}`)
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' })
        el.classList.add('flash-highlight')
        setTimeout(() => el.classList.remove('flash-highlight'), 2000)
      }
    })
  }
})

function handlePin() {
  if (props.evidence) togglePin(props.evidence)
}

function handleOpenDoc() {
  if (props.evidence) {
    let fType: "pdf" | "docx" | "image" | "table" | "text" = "pdf"

    const entry = manifest.value.find(f => f.relPath === props.evidence?.path)

    if (entry) {
      fType = entry.fileType
    } else {
      const lower = props.evidence.path.toLowerCase()
      if (lower.endsWith(".docx") || lower.endsWith(".doc")) fType = "docx"
      else if (lower.endsWith(".png") || lower.endsWith(".jpg") || lower.endsWith(".jpeg")) fType = "image"
      else if (lower.endsWith(".txt") || lower.endsWith(".md")) fType = "text"
      else if (lower.endsWith(".csv") || lower.endsWith(".xlsx")) fType = "table"
    }

    openPreview({ relPath: props.evidence.path, fileType: fType } as ManifestEntry)
  }
}
</script>

<template>
  <div class="drawer-panel">
    <div class="drawer-header">
      <div class="drawer-tabs">
        <div class="tab-btn" :class="{ active: currentTab === 'reader' }" @click="currentTab = 'reader'">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
            style="margin-right:4px">
            <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
            <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
          </svg>
          Reader
        </div>
        <div class="tab-btn" :class="{ active: currentTab === 'notebook' }" @click="currentTab = 'notebook'">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
            style="margin-right:4px">
            <path d="M16 12V4H17V2H7V4H8V12L6 14V16H11V22H13V16H18V14L16 12Z" />
          </svg>
          Notebook <span v-if="notebookList.length" class="badge">{{ notebookList.length }}</span>
        </div>
      </div>

      <div class="header-actions">
        <!-- Notebook Refresh (Clean up removed items) -->
        <button v-if="currentTab === 'notebook'" class="icon-btn" title="Refresh List" @click="refreshNotebook">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
            <path d="M3 3v5h5" />
            <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
            <path d="M16 21h5v-5" />
          </svg>
        </button>
        <button class="close-btn" @click="$emit('close')">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M18 6 6 18" />
            <path d="M6 6 18 18" />
          </svg>
        </button>
      </div>
    </div>

    <!-- READER TAB -->
    <div class="drawer-content" v-if="currentTab === 'reader'" ref="contentRef">
      <div v-if="props.evidence" class="reader-container">

        <!-- Sticky Floating Actions (Top Right Overlay) -->
        <div class="sticky-actions">
          <button class="pill-btn" @click="handleOpenDoc" title="Open Full Document">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M15 3h6v6" />
              <path d="M10 14 21 3" />
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
            </svg>
            Open
          </button>
          <button class="pill-btn" :class="{ active: isPinned(props.evidence.chunkId) }" @click="handlePin"
            title="Pin to Notebook">
            <svg v-if="isPinned(props.evidence.chunkId)" xmlns="http://www.w3.org/2000/svg" width="14" height="14"
              viewBox="0 0 24 24" fill="currentColor" stroke="none">
              <path d="M16 12V4H17V2H7V4H8V12L6 14V16H11V22H13V16H18V14L16 12Z" />
            </svg>
            <svg v-else xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M16 12V4H17V2H7V4H8V12L6 14V16H11V22H13V16H18V14L16 12Z" />
            </svg>
            {{ isPinned(props.evidence.chunkId) ? 'Saved' : 'Save' }}
          </button>
        </div>

        <div class="doc-header">
          <div class="doc-title">{{ props.evidence.path.split('/').pop() }}</div>
          <div class="doc-meta-row">
            <span class="meta-tag" v-if="props.evidence.page">Page {{ props.evidence.page }}</span>
            <span class="meta-tag">Score: {{ props.evidence.score.toFixed(2) }}</span>
          </div>
          <div class="doc-path">{{ props.evidence.path }}</div>
        </div>

        <div class="evidence-highlight-box">
          <div class="highlight-text">{{ props.evidence.text }}</div>
        </div>
      </div>
      <div v-else class="empty-state">
        <svg class="empty-icon" xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24"
          fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="m15 18-6-6 6-6" />
        </svg>
        <p>Select a source to view.</p>
      </div>
    </div>

    <!-- NOTEBOOK TAB -->
    <div class="drawer-content" v-else>
      <div v-if="notebookList.length === 0" class="empty-state">
        <p>Notebook is empty.</p>
      </div>
      <div v-else class="notebook-list">
        <div v-for="item in notebookList" :key="item.chunkId" :id="`note-${item.chunkId}`" class="note-item"
          :class="{ 'pending-removal': pendingRemovals.has(item.chunkId) }">
          <div class="note-header">
            <span class="note-source">{{ item.path.split('/').pop() }}</span>
            <button class="unpin-btn" @click="handleNotebookUnpin(item)" title="Toggle Pin">
              <!-- 显示实心或空心图标 -->
              <svg v-if="!pendingRemovals.has(item.chunkId)" xmlns="http://www.w3.org/2000/svg" width="14" height="14"
                viewBox="0 0 24 24" fill="currentColor" stroke="none">
                <path d="M16 12V4H17V2H7V4H8V12L6 14V16H11V22H13V16H18V14L16 12Z" />
              </svg>
              <svg v-else xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                style="opacity:0.5">
                <path d="M16 12V4H17V2H7V4H8V12L6 14V16H11V22H13V16H18V14L16 12Z" />
              </svg>
            </button>
          </div>
          <div class="note-text">{{ item.text.slice(0, 80) }}...</div>
          <div class="note-footer" v-if="item.page">
            <span class="note-loc">p.{{ item.page }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color);
  background: #fcfcfc;
  border-radius: 12px 12px 0 0;
}

.drawer-tabs {
  display: flex;
  gap: 8px;
  background: #f0f0f5;
  padding: 4px;
  border-radius: 8px;
}

.tab-btn {
  font-size: 12px;
  font-weight: 600;
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
  color: var(--text-secondary);
  user-select: none;
  display: flex;
  align-items: center;
}

.tab-btn.active {
  background: #fff;
  color: var(--text-primary);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.badge {
  background: var(--accent-color);
  color: #fff;
  padding: 1px 5px;
  border-radius: 99px;
  font-size: 9px;
  margin-left: 6px;
  min-width: 16px;
  text-align: center;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.close-btn {
  background: none;
  border: none;
  cursor: pointer;
  color: #999;
  display: flex;
  align-items: center;
  padding: 4px;
}

.close-btn:hover {
  color: #333;
  background: rgba(0, 0, 0, 0.05);
  border-radius: 4px;
}

.icon-btn {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-secondary);
  padding: 4px;
  display: flex;
}

.icon-btn:hover {
  color: var(--text-primary);
  background: rgba(0, 0, 0, 0.05);
  border-radius: 4px;
}

.drawer-content {
  padding: 20px;
  overflow-y: auto;
  flex: 1;
  position: relative;
}

.reader-container {
  position: relative;
  min-height: 100%;
}

/* Sticky Actions */
.sticky-actions {
  position: sticky;
  top: 0;
  float: right;
  display: flex;
  gap: 8px;
  z-index: 20;
  margin-bottom: 12px;
  margin-left: 12px;
}

.pill-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  padding: 6px 12px;
  background: #fff;
  border: 1px solid var(--border-color);
  border-radius: 99px;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  transition: all 0.2s;
  color: var(--text-secondary);
  opacity: 0.9;
}

.pill-btn:hover {
  border-color: var(--accent-color);
  color: var(--text-primary);
  opacity: 1;
  transform: translateY(-1px);
}

.pill-btn.active {
  background: #fffdf5;
  color: #5f4b0e;
  border-color: #e0c060;
}

.doc-header {
  margin-bottom: 20px;
  padding-right: 0;
  clear: both;
}

.doc-title {
  font-family: var(--font-serif);
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 4px;
  line-height: 1.2;
  color: var(--text-primary);
}

.doc-meta-row {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: var(--text-secondary);
  font-family: var(--font-mono);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.doc-path {
  font-size: 11px;
  color: var(--text-secondary);
  font-family: var(--font-mono);
  word-break: break-all;
}

.evidence-highlight-box {
  background: #fffeed;
  border: 1px solid #f3c969;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 4px 12px rgba(243, 201, 105, 0.1);
}

/* ... rest styles ... */
.highlight-text {
  font-size: 15px;
  line-height: 1.8;
  color: #2c2c2c;
  white-space: pre-wrap;
}

.notebook-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.note-item {
  background: #fff;
  border: 1px solid var(--border-color);
  padding: 12px;
  border-radius: 8px;
  transition: all 0.3s ease;
}

/* 视觉上置灰 */
.note-item.pending-removal {
  opacity: 0.5;
  background: #f9f9f9;
  border-style: dashed;
}

/* 高亮闪烁 */
.flash-highlight {
  animation: flash 1.5s ease-out;
  border-color: var(--accent-color);
  box-shadow: 0 0 0 2px var(--accent-soft);
}

@keyframes flash {
  0% {
    background-color: var(--gold-highlight);
  }

  100% {
    background-color: #fff;
  }
}

.note-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
  font-size: 12px;
  font-weight: 600;
}

.note-text {
  font-size: 12px;
  color: #555;
  line-height: 1.5;
  margin-bottom: 8px;
}

.note-loc {
  font-size: 10px;
  color: #999;
  font-family: monospace;
}

.unpin-btn {
  border: none;
  background: transparent;
  cursor: pointer;
  color: var(--accent-color);
  padding: 2px;
}

.empty-state {
  text-align: center;
  color: var(--text-secondary);
  margin-top: 60px;
}

.empty-icon {
  margin-bottom: 12px;
  color: #ccc;
}
</style>