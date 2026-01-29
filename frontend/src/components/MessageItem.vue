<script setup lang="ts">
import {
  ref,
  inject,
  computed,
  watch,
  onMounted,
  onUnmounted,
  nextTick,
  type Ref,
} from "vue";
import type {
  ChatMessage,
  EvidenceChunk,
  TimelineStep,
  ManifestEntry,
  CitationCopyFormat,
} from "../types";
import { renderMarkdown, renderMermaidDiagrams } from "../utils/markdown";
import {
  formatInTextCitation,
  hasCitationData,
  type InTextCitationStyle,
} from "../utils/citations";
import { extractFileMetadata } from "../api/client";
import ConfirmExtractMetadataModal from "./ConfirmExtractMetadataModal.vue";
import { Loader2, CircleCheck, Copy, Check } from "lucide-vue-next";

const markdownBodyRef = ref<HTMLElement | null>(null);

const props = defineProps<{ message: ChatMessage }>();
const openEvidence =
  inject<(item: EvidenceChunk, related?: EvidenceChunk[]) => void>(
    "openEvidence",
  )!;
const togglePin = inject<(item: EvidenceChunk) => void>("togglePin");
const isPinned = inject<(id: string) => boolean>("isPinned")!;
const manifest = inject<Ref<ManifestEntry[]>>("manifest", ref([]));
const citationFormat = inject<Ref<CitationCopyFormat>>(
  "citationFormat",
  ref("apa"),
);

const showCopied = ref(false);
const showMetadataConfirm = ref(false);
const missingMetadataPaths = ref<string[]>([]);
const isExtractingMetadata = ref(false);

const isTimelineExpanded = ref(true);
const expandedSteps = ref<Set<number>>(new Set());
const manualStepStates = ref<Map<number, boolean>>(new Map());

const currentTime = ref(Date.now());
let timerInterval: ReturnType<typeof setInterval> | null = null;

function formatElapsed(ms: number): string {
  const totalSeconds = ms / 1000;
  const mins = Math.floor(totalSeconds / 60);
  const secs = (totalSeconds % 60).toFixed(1);
  if (mins > 0) {
    return `${mins}m ${secs}s`;
  }
  return `${secs}s`;
}

const totalElapsed = computed(() => {
  const startTime = props.message.timestamp;
  // Use completedAt if message is done, otherwise use current time
  const endTime = props.message.completedAt || currentTime.value;
  return endTime - startTime;
});

function getStepElapsed(step: TimelineStep): number {
  const stepStart = step.startTime || (step as any).timestamp || 0;
  if (!stepStart) return 0;
  if (step.endTime) {
    return step.endTime - stepStart;
  }
  if (props.message.isStreaming) {
    return currentTime.value - stepStart;
  }
  const endTime = props.message.completedAt || currentTime.value;
  return endTime - stepStart;
}

function startTimer() {
  if (timerInterval) return;
  currentTime.value = Date.now();
  timerInterval = setInterval(() => {
    currentTime.value = Date.now();
  }, 100);
}

function stopTimer() {
  if (timerInterval) {
    clearInterval(timerInterval);
    timerInterval = null;
  }
}

if (props.message.role === "ai" && props.message.content.length === 0) {
  isTimelineExpanded.value = true;
}

onMounted(() => {
  if (props.message.isStreaming) {
    startTimer();
  }
});

onUnmounted(() => {
  stopTimer();
});

watch(
  () => props.message.isStreaming,
  (isStreaming, wasStreaming) => {
    if (isStreaming) {
      startTimer();
    } else {
      if (wasStreaming && !props.message.completedAt) {
        props.message.completedAt = Date.now();
      }
      stopTimer();
    }
  },
);

watch(
  () => props.message.content,
  (newVal) => {
    if (newVal && newVal.length > 0) {
      isTimelineExpanded.value = false;
    }
  },
  { once: true },
);

// [修正] 不再排序，保持与 LLM 输出的 [C1] [C2] 顺序一致
const displaySources = computed(() => {
  const sources = props.message.sources || [];
  const unique = new Set<string>();
  const result: EvidenceChunk[] = [];
  for (const s of sources) {
    if (!unique.has(s.chunkId)) {
      unique.add(s.chunkId);
      result.push(s);
    }
  }
  return result;
});

function processMarkdown(text: string) {
  const normalized = (text ?? "").replace(
    /\*\*(.+?)\*\*/g,
    "<strong>$1</strong>",
  );
  return renderMarkdown(normalized).replace(
    /\[(C\d+(?:\s*,\s*C\d+)*)\]/g,
    (_match, group) => {
      const buttons = group
        .split(/\s*,\s*/)
        .map((token: string) => token.trim())
        .filter(Boolean)
        .map((token: string) => {
          const id = token.replace(/^C/i, "");
          return `<button class="citation-link" data-cid="${id}">${id}</button>`;
        })
        .join("");
      return buttons;
    },
  );
}

function handleBodyClick(event: MouseEvent) {
  const target = event.target as HTMLElement;

  // Handle citation link clicks
  const citationBtn = target.closest(".citation-link") as HTMLElement;
  if (citationBtn && citationBtn.dataset.cid) {
    const index = parseInt(citationBtn.dataset.cid) - 1;
    if (props.message.sources && props.message.sources[index]) {
      const source = props.message.sources[index];
      const related = props.message.sources.filter(
        (s) => s.path === source.path,
      );
      openEvidence(source, related);
    }
    return;
  }

  // Handle code copy button clicks
  const copyBtn = target.closest(".code-copy-btn") as HTMLElement;
  if (copyBtn && copyBtn.dataset.code) {
    const code = decodeURIComponent(copyBtn.dataset.code);
    navigator.clipboard.writeText(code).then(() => {
      copyBtn.classList.add("copied");
      const label = copyBtn.querySelector(".copy-label");
      if (label) label.textContent = "Copied!";
      setTimeout(() => {
        copyBtn.classList.remove("copied");
        if (label) label.textContent = "Copy";
      }, 2000);
    });
  }
}

function handleEvidenceClick(source: EvidenceChunk) {
  const related =
    props.message.sources?.filter((s) => s.path === source.path) || [];
  openEvidence(source, related);
}

function toggleStepDetails(index: number, details?: string) {
  if (!details) return;
  const current = expandedSteps.value;
  if (current.has(index)) {
    current.delete(index);
    manualStepStates.value.set(index, false);
  } else {
    current.add(index);
    manualStepStates.value.set(index, true);
  }
  expandedSteps.value = new Set(current);
}

function isStepExpanded(index: number): boolean {
  return expandedSteps.value.has(index);
}

function autoExpandLatestStep() {
  const steps = props.message.timeline || [];
  if (!steps.length) return;
  const latestIndex = steps.length - 1;
  const nextExpanded = new Set<number>();

  for (let i = 0; i < steps.length; i++) {
    if (manualStepStates.value.has(i)) {
      if (manualStepStates.value.get(i)) {
        nextExpanded.add(i);
      }
    }
  }

  if (
    !manualStepStates.value.has(latestIndex) ||
    manualStepStates.value.get(latestIndex)
  ) {
    nextExpanded.add(latestIndex);
  }

  expandedSteps.value = nextExpanded;
}

watch(
  () => props.message.timeline?.length,
  (len, prev) => {
    if (!len) return;
    if (!prev || len !== prev) {
      autoExpandLatestStep();
    }
  },
);

// Render mermaid diagrams when content changes (and streaming completes)
watch(
  () => [props.message.content, props.message.isStreaming],
  async ([content, isStreaming]) => {
    if (content && !isStreaming && markdownBodyRef.value) {
      await nextTick();
      renderMermaidDiagrams(markdownBodyRef.value);
    }
  },
  { immediate: true },
);

// Build a lookup map from path to bibliography
const bibLookup = computed(() => {
  const map = new Map<string, ManifestEntry["bibliography"]>();
  for (const entry of manifest.value || []) {
    if (entry.relPath && entry.bibliography) {
      map.set(entry.relPath, entry.bibliography);
    }
  }
  return map;
});

const manifestByPath = computed(() => {
  const map = new Map<string, ManifestEntry>();
  for (const entry of manifest.value || []) {
    if (entry.relPath) {
      map.set(entry.relPath, entry);
    }
  }
  return map;
});

function getMissingMetadataPaths(sources: EvidenceChunk[]): string[] {
  const missing: string[] = [];
  const seen = new Set<string>();
  for (const source of sources) {
    const path = source.path;
    if (!path || seen.has(path)) continue;
    seen.add(path);
    const entry = manifestByPath.value.get(path);
    if (!entry || !hasCitationData(entry.bibliography)) {
      missing.push(path);
    }
  }
  return missing;
}

function extractMetadataForPaths(paths: string[]) {
  if (paths.length === 0 || isExtractingMetadata.value) return;
  isExtractingMetadata.value = true;
  (async () => {
    try {
      const updateMap = new Map<string, ManifestEntry["bibliography"]>();
      for (const path of paths) {
        const updated = await extractFileMetadata(path);
        updateMap.set(path, updated);
      }
      if (manifest.value.length > 0) {
        manifest.value = manifest.value.map((entry) => {
          const next = updateMap.get(entry.relPath);
          return next ? { ...entry, bibliography: next } : entry;
        });
      }
    } catch (err) {
      console.error("Failed to extract metadata:", err);
    } finally {
      isExtractingMetadata.value = false;
    }
  })();
}

function resetMetadataPrompt() {
  showMetadataConfirm.value = false;
  missingMetadataPaths.value = [];
}

// Copy message with formatted citations
async function performCopyWithCitations() {
  const content = props.message.content;
  const sources = props.message.sources || [];
  const style = citationFormat.value as InTextCitationStyle;

  // Replace [Cx] and [Cx, Cy, ...] patterns with formatted citations
  const formatted = content.replace(
    /\[C(\d+)(?:\s*,\s*C(\d+))*\]/g,
    (match) => {
      // Extract all citation numbers from the match
      const nums = match.match(/\d+/g);
      if (!nums) return match;

      const citations = nums.map((numStr) => {
        const idx = parseInt(numStr) - 1;
        const source = sources[idx];
        if (!source) return `[${numStr}]`;

        const bib = bibLookup.value.get(source.path);
        return formatInTextCitation(bib, style, parseInt(numStr), source.page);
      });

      // Join multiple citations with semicolon for APA/Chicago, comma for others
      if (style === "apa" || style === "chicago") {
        // For parenthetical styles, combine inside single parentheses
        if (citations.length > 1) {
          const inner = citations
            .map((c) => c.replace(/^\(|\)$/g, ""))
            .join("; ");
          return `(${inner})`;
        }
      }
      return citations.join(", ");
    },
  );

  try {
    await navigator.clipboard.writeText(formatted);
    showCopied.value = true;
    setTimeout(() => {
      showCopied.value = false;
    }, 2000);
  } catch (err) {
    console.error("Failed to copy:", err);
  }
}

async function copyWithCitations() {
  const sources = props.message.sources || [];
  const missing = getMissingMetadataPaths(sources);
  if (missing.length > 0 && !isExtractingMetadata.value) {
    missingMetadataPaths.value = missing;
    showMetadataConfirm.value = true;
    return;
  }
  await performCopyWithCitations();
}

async function handleExtractMetadataAndCopy() {
  const paths = [...missingMetadataPaths.value];
  resetMetadataPrompt();
  extractMetadataForPaths(paths);
  await performCopyWithCitations();
}

async function handleCopyWithoutExtraction() {
  resetMetadataPrompt();
  await performCopyWithCitations();
}
</script>

<template>
  <div class="message-row" :class="message.role">
    <div v-if="message.role === 'user'" class="user-bubble">
      {{ message.content }}
    </div>

    <div v-else class="ai-container">
      <!-- 2. THINKING ACCORDION -->
      <div v-if="message.timeline?.length" class="timeline-container">
        <div
          class="timeline-trigger"
          @click="isTimelineExpanded = !isTimelineExpanded"
        >
          <div class="trigger-left">
            <Loader2 v-if="message.isStreaming" class="spinner" :size="14" />
            <CircleCheck v-else class="check-icon" :size="14" />
            <span class="trigger-text">{{
              message.isStreaming ? "Thinking Process" : "Analysis Complete"
            }}</span>
          </div>
          <div class="trigger-right">
            <span class="elapsed-time">{{ formatElapsed(totalElapsed) }}</span>
            <svg
              class="chevron"
              :class="{ 'rotate-180': isTimelineExpanded }"
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path d="m6 9 6 6 6-6" />
            </svg>
          </div>
        </div>
        <transition name="slide">
          <div v-if="isTimelineExpanded" class="timeline-content">
            <div
              v-for="(step, i) in message.timeline"
              :key="i"
              class="step-item"
              :class="{ expandable: !!step.details }"
              @click="toggleStepDetails(i, step.details)"
            >
              <div class="step-row">
                <div class="step-indicator">
                  <Loader2
                    v-if="
                      message.isStreaming && i === message.timeline!.length - 1
                    "
                    class="step-spinner"
                    :size="10"
                  />
                  <span v-else class="step-dot"></span>
                </div>
                <span class="step-msg">{{ step.message }}</span>
                <span class="step-time">{{
                  formatElapsed(getStepElapsed(step))
                }}</span>
                <svg
                  v-if="step.details"
                  class="step-chevron"
                  :class="{ 'rotate-180': isStepExpanded(i) }"
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <path d="m6 9 6 6 6-6" />
                </svg>
              </div>
              <transition name="fade">
                <div
                  v-if="step.details && isStepExpanded(i)"
                  class="step-details"
                >
                  <div class="step-details-text">{{ step.details }}</div>
                </div>
              </transition>
            </div>
          </div>
        </transition>
      </div>

      <!-- KEYWORDS (SCOPE) -->
      <div v-if="message.keywords?.length" class="keywords-row">
        <span v-for="kw in message.keywords" :key="kw" class="keyword-tag">{{
          kw
        }}</span>
      </div>

      <!-- 3. MARKDOWN BODY WITH COPY BUTTON -->
      <div class="markdown-body-wrapper">
        <!-- Copy Button - sticky to follow scroll -->
        <button
          v-if="message.content && !message.isStreaming"
          class="ai-copy-btn"
          :class="{ copied: showCopied }"
          @click="copyWithCitations"
          title="Copy with formatted citations"
        >
          <Copy v-if="!showCopied" :size="14" />
          <Check v-else :size="14" />
        </button>
        <div
          ref="markdownBodyRef"
          class="markdown-body"
          v-html="processMarkdown(message.content)"
          @click="handleBodyClick"
        ></div>
      </div>

      <!-- 4. EVIDENCE STREAM (CARDS) -->
      <div
        v-if="!message.isStreaming && displaySources.length"
        class="evidence-stream-container"
      >
        <div class="stream-label">References</div>
        <div class="stream-scroll">
          <div
            v-for="(source, idx) in displaySources"
            :key="source.chunkId"
            class="stream-card"
            @click="handleEvidenceClick(source)"
          >
            <div class="card-header">
              <span class="card-idx">{{ idx + 1 }}</span>
              <span class="card-title" :title="source.path">{{
                source.path.split("/").pop()
              }}</span>
            </div>
            <div class="card-snippet">{{ source.text.slice(0, 60) }}...</div>
            <div class="card-footer">
              <span class="card-loc" v-if="source.page"
                >p.{{ source.page }}</span
              >
              <button
                class="card-pin"
                :class="{ active: isPinned && isPinned(source.chunkId) }"
                @click.stop.prevent="togglePin && togglePin(source)"
                title="Pin Evidence"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                  stroke="none"
                  v-if="isPinned && isPinned(source.chunkId)"
                >
                  <path
                    d="M16 12V4H17V2H7V4H8V12L6 14V16H11V22H13V16H18V14L16 12Z"
                  />
                </svg>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  v-else
                >
                  <path
                    d="M16 12V4H17V2H7V4H8V12L6 14V16H11V22H13V16H18V14L16 12Z"
                  />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <ConfirmExtractMetadataModal
      v-model="showMetadataConfirm"
      action-label="copy"
      :missing-count="missingMetadataPaths.length"
      @confirm="handleExtractMetadataAndCopy"
      @skip="handleCopyWithoutExtraction"
      @cancel="resetMetadataPrompt"
    />
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
  background: var(--color-neutral-190);
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

/* --- Thinking Accordion --- */
.timeline-container {
  border: 1px solid var(--border-color);
  border-radius: 8px;
  margin-bottom: 20px;
  background: var(--color-white);
  overflow: hidden;
}

.timeline-trigger {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  cursor: pointer;
  background: var(--color-neutral-70);
  transition: background 0.2s;
}

.timeline-trigger:hover {
  background: var(--color-neutral-120);
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
  color: var(--color-success-500);
}

.chevron {
  transition: transform 0.3s ease;
  color: var(--color-neutral-450);
}

.timeline-content {
  padding: 0 14px 14px 14px;
  border-top: 1px solid var(--border-color);
}

.step-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 8px;
}

.step-item.expandable {
  cursor: pointer;
}

.step-row {
  display: flex;
  align-items: center;
  gap: 8px;
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
  color: var(--color-neutral-500);
  min-width: 50px;
  text-align: right;
}

.step-chevron {
  transition: transform 0.2s ease;
  color: var(--color-neutral-450);
  flex-shrink: 0;
}

.step-details {
  margin-left: 6px;
  padding: 6px 10px 6px 12px;
  border-left: 2px solid var(--accent-color);
  background: transparent;
  font-size: 12px;
  line-height: 1.4;
  color: var(--text-secondary);
}

.step-details-text {
  white-space: pre-wrap;
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
  background: var(--color-accent-50);
  color: var(--text-secondary);
  padding: 3px 8px;
  border-radius: 6px;
  font-weight: 500;
  border: 1px solid var(--alpha-black-05);
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
}

.stream-card {
  min-width: 200px;
  max-width: 200px;
  background: var(--color-white);
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
  background: var(--accent-soft);
  color: var(--accent-color);
  border-radius: 999px;
  width: 16px;
  height: 16px;
  font-size: 10px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
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
  color: var(--color-neutral-500);
  font-family: var(--font-mono);
  margin-right: auto;
}

.card-pin {
  height: 16px;
  width: 16px;
  background: transparent;
  border: none;
  color: var(--color-neutral-400);
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

/* Markdown Body Wrapper - for copy button positioning */
.markdown-body-wrapper {
  position: relative;
}

/* AI Copy Button */
.ai-copy-btn {
  float: right;
  position: sticky;
  top: 72px; /* Account for top nav height */
  margin-left: 12px;
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  opacity: 0;
  transition:
    opacity 0.15s,
    background 0.15s,
    color 0.15s,
    border-color 0.15s;
  z-index: 10;
}

.markdown-body-wrapper:hover .ai-copy-btn,
.ai-copy-btn:focus {
  opacity: 1;
}

.ai-copy-btn:hover {
  background: var(--color-neutral-100);
  border-color: var(--border-color);
  color: var(--text-primary);
}

.ai-copy-btn.copied {
  opacity: 1;
  background: var(--color-success-50);
  border-color: var(--color-success-200);
  color: var(--color-success-600);
}
</style>
