<script setup lang="ts">
import { ref, inject, computed, watch, onMounted, onUnmounted } from "vue"
import type { ChatMessage, EvidenceChunk, TimelineStep } from "../types"
import { renderMarkdown } from "../utils/markdown"
import { Loader2, CircleCheck } from "lucide-vue-next"

const props = defineProps<{ message: ChatMessage }>()
const openEvidence = inject<(item: EvidenceChunk) => void>("openEvidence")!
const togglePin = inject<(item: EvidenceChunk) => void>("togglePin")
const isPinned = inject<(id: string) => boolean>("isPinned")!
const setHighlightedPaths = inject<(paths: string[]) => void>("setHighlightedPaths")!

const isTimelineExpanded = ref(true)


const currentTime = ref(Date.now())
let timerInterval: ReturnType<typeof setInterval> | null = null

function formatElapsed(ms: number): string {
  const totalSeconds = ms / 1000
  const mins = Math.floor(totalSeconds / 60)
  const secs = (totalSeconds % 60).toFixed(1)
  if (mins > 0) {
    return `${mins}m ${secs}s`
  }
  return `${secs}s`
}


const totalElapsed = computed(() => {
  const startTime = props.message.timestamp
  // Use completedAt if message is done, otherwise use current time
  const endTime = props.message.completedAt || currentTime.value
  return endTime - startTime
})


function getStepElapsed(step: TimelineStep, index: number): number {
  const timeline = props.message.timeline || []
  const nextStep = timeline[index + 1]


  const stepStart = step.startTime || (step as any).timestamp || 0
  if (!stepStart) return 0

  if (nextStep) {
    const nextStart = nextStep.startTime || (nextStep as any).timestamp || 0
    return nextStart - stepStart
  } else if (props.message.isStreaming) {
    return currentTime.value - stepStart
  } else {
    // Use completedAt if available, otherwise use current time
    const endTime = props.message.completedAt || currentTime.value
    return endTime - stepStart
  }
}

function startTimer() {
  if (timerInterval) return
  currentTime.value = Date.now()
  timerInterval = setInterval(() => {
    currentTime.value = Date.now()
  }, 100)
}

function stopTimer() {
  if (timerInterval) {
    clearInterval(timerInterval)
    timerInterval = null
  }
}

if (props.message.role === 'ai' && props.message.content.length === 0) {
  isTimelineExpanded.value = true
}


onMounted(() => {
  if (props.message.isStreaming) {
    startTimer()
  }
})

onUnmounted(() => {
  stopTimer()
})

watch(() => props.message.isStreaming, (isStreaming, wasStreaming) => {
  if (isStreaming) {
    startTimer()
  } else {

    if (wasStreaming && !props.message.completedAt) {
      props.message.completedAt = Date.now()
    }
    stopTimer()
  }
})

watch(() => props.message.content, (newVal) => {
  if (newVal && newVal.length > 0) {
    isTimelineExpanded.value = false
  }
}, { once: true })

// [修正] 不再排序，保持与 LLM 输出的 [C1] [C2] 顺序一致
const displaySources = computed(() => {
  const sources = props.message.sources || []
  const unique = new Set<string>()
  const result: EvidenceChunk[] = []
  for (const s of sources) {
    if (!unique.has(s.chunkId)) {
      unique.add(s.chunkId)
      result.push(s)
    }
  }
  return result
})

// Capsule Auto-Hide Logic
const isCapsuleVisible = ref(false)
let hideTimer: any = null

function handleMouseMove() {
  isCapsuleVisible.value = true
  clearTimeout(hideTimer)
  // Hide after inactivity? User said "when mouse moving ... automatically show". 
  // "Usually automatically hide" -> Hide when mouse stops or leaves?
  // "Put on top of it" -> hover capsule keeps it open.
  // Let's set a debounce to hide if mouse stops moving? Or just keep showing while inside message?
  // "In message... absolute coord moving... automatically show".
  // Simple interpretation: Show when mouse is inside message.
  // "Automatically hide usually" -> Hide when mouse leaves message?
  // BUT user explicitly said "absolute coord moving or hover on it".
  // Maybe they mean: if mouse is static inside message (reading), it should hide?
  // Let's try: Show on move, hide after 2s of inactivity (unless hovering capsule).

  hideTimer = setTimeout(() => {
    if (!isCapsuleHovered.value) {
      isCapsuleVisible.value = false
    }
  }, 2000)
}

const isCapsuleHovered = ref(false)
function onCapsuleEnter() {
  isCapsuleHovered.value = true
  isCapsuleVisible.value = true
  clearTimeout(hideTimer)
}
function onCapsuleLeave() {
  isCapsuleHovered.value = false
  // Start hide timer
  hideTimer = setTimeout(() => {
    isCapsuleVisible.value = false
  }, 1000)
}

function handleMessageLeave() {
  // Hide immediately or with short delay when leaving entire message area
  clearTimeout(hideTimer)
  if (!isCapsuleHovered.value) {
    isCapsuleVisible.value = false
  }
}

function processMarkdown(text: string) {
  return renderMarkdown(text).replace(
    /\[C(\d+)\]/g,
    '<button class="citation-link" data-cid="$1">$1</button>'
  )
}

function handleBodyClick(event: MouseEvent) {
  const target = event.target as HTMLElement
  const btn = target.closest('.citation-link') as HTMLElement
  if (btn && btn.dataset.cid) {
    const index = parseInt(btn.dataset.cid) - 1
    if (props.message.sources && props.message.sources[index]) {
      openEvidence(props.message.sources[index])
    }
  }
}
</script>

<template>
  <div class="message-row" :class="message.role" @mousemove="handleMouseMove" @mouseleave="handleMessageLeave">
    <div v-if="message.role === 'user'" class="user-bubble">{{ message.content }}</div>

    <div v-else class="ai-container">

      <!-- 2. THINKING ACCORDION -->
      <div v-if="message.timeline?.length" class="timeline-container">
        <div class="timeline-trigger" @click="isTimelineExpanded = !isTimelineExpanded">
          <div class="trigger-left">
            <Loader2 v-if="message.isStreaming" class="spinner" :size="14" />
            <CircleCheck v-else class="check-icon" :size="14" />
            <span class="trigger-text">{{ message.isStreaming ? 'Thinking Process' : 'Analysis Complete' }}</span>
          </div>
          <div class="trigger-right">
            <span class="elapsed-time">{{ formatElapsed(totalElapsed) }}</span>
            <svg class="chevron" :class="{ 'rotate-180': isTimelineExpanded }" width="16" height="16"
              viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"
              stroke-linejoin="round">
              <path d="m6 9 6 6 6-6" />
            </svg>
          </div>
        </div>
        <transition name="slide">
          <div v-if="isTimelineExpanded" class="timeline-content">
            <div v-for="(step, i) in message.timeline" :key="i" class="step-item">
              <div class="step-indicator">
                <Loader2 v-if="message.isStreaming && i === message.timeline!.length - 1" class="step-spinner"
                  :size="10" />
                <span v-else class="step-dot"></span>
              </div>
              <span class="step-msg">{{ step.message }}</span>
              <span class="step-time">{{ formatElapsed(getStepElapsed(step, i)) }}</span>
            </div>
          </div>
        </transition>
      </div>

      <!-- 1. STICKY SOURCE HEADER (Moved below Timeline) -->
      <div v-if="displaySources.length" class="sticky-header-wrapper" :class="{ visible: isCapsuleVisible }">
        <div class="source-capsule" @mouseenter="onCapsuleEnter" @mouseleave="onCapsuleLeave">
          <div class="capsule-icon-area">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
              style="color:var(--accent-color)">
              <path
                d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z" />
            </svg>
          </div>
          <span class="label">Based on {{ displaySources.length }} sources</span>

          <transition name="fade">
            <div v-if="isCapsuleHovered" class="source-popover">
              <div v-for="(source, idx) in displaySources" :key="source.chunkId" class="popover-item"
                @click="openEvidence(source)" @mouseenter="setHighlightedPaths([source.path])"
                @mouseleave="setHighlightedPaths([])">
                <div class="popover-line">
                  <div class="popover-pin-icon" :class="{ visible: isPinned(source.chunkId) }">
                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24"
                      fill="currentColor" stroke="none" style="color:var(--accent-color)">
                      <path d="M16 12V4H17V2H7V4H8V12L6 14V16H11V22H13V16H18V14L16 12Z" />
                    </svg>
                  </div>
                  <div class="popover-title"><strong>{{ idx + 1 }}.</strong> {{ source.path.split('/').pop() }}</div>
                </div>
                <div class="popover-meta" v-if="source.page">p.{{ source.page }}</div>
              </div>
            </div>
          </transition>
        </div>
      </div>

      <!-- KEYWORDS (SCOPE) -->
      <div v-if="message.keywords?.length" class="keywords-row">
        <span v-for="kw in message.keywords" :key="kw" class="keyword-tag">{{ kw }}</span>
      </div>

      <!-- 3. MARKDOWN BODY -->
      <div class="markdown-body" v-html="processMarkdown(message.content)" @click="handleBodyClick"></div>

      <!-- 4. EVIDENCE STREAM (CARDS) -->
      <div v-if="!message.isStreaming && displaySources.length" class="evidence-stream-container">
        <div class="stream-label">References</div>
        <div class="stream-scroll">
          <div v-for="(source, idx) in displaySources" :key="source.chunkId" class="stream-card"
            @click="openEvidence(source)">
            <div class="card-header">
              <span class="card-idx">{{ idx + 1 }}</span>
              <span class="card-title" :title="source.path">{{ source.path.split('/').pop() }}</span>
            </div>
            <div class="card-snippet">{{ source.text.slice(0, 60) }}...</div>
            <div class="card-footer">
              <span class="card-loc" v-if="source.page">p.{{ source.page }}</span>
              <button class="card-pin" :class="{ active: isPinned && isPinned(source.chunkId) }"
                @click.stop.prevent="togglePin && togglePin(source)" title="Pin Evidence">
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="currentColor"
                  stroke="none" v-if="isPinned && isPinned(source.chunkId)">
                  <path d="M16 12V4H17V2H7V4H8V12L6 14V16H11V22H13V16H18V14L16 12Z" />
                </svg>
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
                  stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" v-else>
                  <path d="M16 12V4H17V2H7V4H8V12L6 14V16H11V22H13V16H18V14L16 12Z" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<style scoped>
.message-row {
  display: flex;
  margin-bottom: 32px;
  gap: 16px;
}

.message-row.user {
  justify-content: flex-end;
}

.message-row.ai {
  justify-content: flex-start;
}

/* Reverting layout styles */
.user-bubble {
  background: #f0f2f5;
  padding: 12px 18px;
  border-radius: 12px;
  border-bottom-right-radius: 2px;
  max-width: 80%;
  font-size: 15px;
  color: var(--text-primary);
  line-height: 1.6;
}

.ai-container {
  width: 100%;
  max-width: 100%;
  position: relative;
}

/* --- Sticky Header --- */
.sticky-header-wrapper {
  position: sticky;
  top: 0;
  right: 0;
  /* sticky doesn't use right for positioning usually, but flex handles it */
  z-index: 10;
  height: 0;
  overflow: visible;
  display: flex;
  justify-content: flex-end;
  padding-right: 16px;
  /* Offset from right edge */

  opacity: 0;
  transition: opacity 0.3s ease;
  pointer-events: none;
}

.sticky-header-wrapper.visible {
  opacity: 1;
  pointer-events: none;
  /* Wrapper itself shouldn't block, children will */
}

.source-capsule {
  pointer-events: auto;
  /* Re-enable pointer events for the button */
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: #fff;
  border: 1px solid var(--accent-color);
  color: var(--accent-color);
  padding: 6px 12px;
  border-radius: 99px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  transition: all 0.2s;
  position: relative;
  height: 30px;
  min-width: 140px;
}

.source-capsule:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.12);
}

.capsule-icon-area {
  width: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.source-popover {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  left: auto;
  background: #fff;
  border: 1px solid var(--border-color);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
  border-radius: 12px;
  width: 280px;
  max-height: 300px;
  overflow-y: auto;
  padding: 8px;
  z-index: 100;
}

.popover-item {
  padding: 8px;
  border-radius: 6px;
  cursor: pointer;
  border-bottom: 1px solid transparent;
}

.popover-item:hover {
  background: var(--bg-sidebar);
}

.popover-title {
  font-size: 13px;
  color: var(--text-primary);
  margin-bottom: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.popover-meta {
  font-size: 11px;
  color: var(--text-secondary);
  display: flex;
  gap: 8px;
  justify-content: space-between;
  margin-left: 24px;
}

.popover-line {
  display: flex;
  align-items: center;
  gap: 6px;
}

.popover-pin {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  margin-right: 4px;
}

.popover-pin-icon {
  width: 16px;
  display: flex;
  align-items: center;
  opacity: 0;
  transition: opacity 0.2s;
}

.popover-pin-icon.visible {
  opacity: 1;
}

/* --- Thinking Accordion --- */
.timeline-container {
  border: 1px solid var(--border-color);
  border-radius: 8px;
  margin-bottom: 20px;
  background: #fff;
  overflow: hidden;
}

.timeline-trigger {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  cursor: pointer;
  background: #fcfcfc;
  transition: background 0.2s;
}

.timeline-trigger:hover {
  background: #f5f5f7;
}

.trigger-left {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
}

.trigger-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.elapsed-time {
  font-size: 12px;
  font-family: var(--font-mono);
  color: var(--text-secondary);
  min-width: 45px;
  text-align: right;
}

.check-icon {
  color: #22c55e;
}

.chevron {
  transition: transform 0.3s ease;
  color: #aaa;
}

.timeline-content {
  padding: 0 14px 14px 14px;
  border-top: 1px solid var(--border-color);
}

.step-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 8px;
}

.step-indicator {
  width: 14px;
  height: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.step-dot {
  width: 6px;
  height: 6px;
  background: var(--accent-color);
  border-radius: 50%;
}

.step-spinner {
  animation: spin 1s linear infinite;
  color: var(--accent-color);
}

.step-msg {
  flex: 1;
}

.step-time {
  font-family: var(--font-mono);
  font-size: 11px;
  color: #999;
  min-width: 50px;
  text-align: right;
}

.spinner {
  animation: spin 1s linear infinite;
  color: var(--accent-color);
}

@keyframes spin {
  100% {
    transform: rotate(360deg);
  }
}

/* --- Keywords --- */
.keywords-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
}

.keyword-tag {
  font-size: 11px;
  background: #eef1f8;
  color: var(--text-secondary);
  padding: 3px 8px;
  border-radius: 6px;
  font-weight: 500;
  border: 1px solid rgba(0, 0, 0, 0.05);
}

/* --- Evidence Stream --- */
.evidence-stream-container {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px dashed var(--border-color);
}

.stream-label {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 12px;
}

.stream-scroll {
  display: flex;
  gap: 12px;
  overflow-x: auto;
  padding-top: 2px;
  padding-bottom: 8px;
  scrollbar-width: thin;
}

.stream-card {
  min-width: 200px;
  max-width: 200px;
  background: #fff;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 10px;
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
}

.stream-card:hover {
  border-color: var(--accent-color);
  transform: translateY(-2px);
  box-shadow: var(--shadow-sm);
}

.card-header {
  display: flex;
  gap: 6px;
  margin-bottom: 6px;
  align-items: center;
}

.card-idx {
  background: var(--bg-sidebar);
  font-size: 10px;
  padding: 2px 5px;
  border-radius: 4px;
  font-weight: 700;
}

.card-title {
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--text-primary);
}

.card-snippet {
  font-size: 11px;
  color: var(--text-secondary);
  line-height: 1.4;
  height: 3em;
  overflow: hidden;
  margin-bottom: 8px;
}

.card-footer {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 8px;
}

.card-loc {
  font-size: 10px;
  color: #999;
  font-family: var(--font-mono);
  margin-right: auto;
}

.card-pin {
  height: 16px;
  width: 16px;
  background: transparent;
  border: none;
  color: #ccc;
  cursor: pointer;
  padding: 2px;
  transition: color 0.2s;
}

.card-pin:hover {
  color: var(--text-primary);
}

.card-pin.active {
  color: var(--accent-color);
}
</style>