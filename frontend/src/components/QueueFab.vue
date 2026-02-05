<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from "vue";
import { ListOrdered, X } from "lucide-vue-next";
import type { QueueJob, QueueStatus } from "../types";
import { useQueue } from "../composables/useQueue";

const {
  queueItems,
  queueCount,
  ejectBursts,
  clearQueueEject,
  launchQueueEject,
  dismissJob,
} = useQueue();

const isQueueOpen = ref(false);
const queueRef = ref<HTMLElement | null>(null);
const queueButtonRef = ref<HTMLButtonElement | null>(null);
const targetPoint = ref({ x: 0, y: 0 });
const pulseActive = ref(false);
const activeBursts = ref<
  { id: string; x: number; y: number; scale: number; opacity: number }[]
>([]);
const hasInitializedQueue = ref(false);
const seenJobIds = new Set<string>();
const burstMeta = new Map<
  string,
  {
    startX: number;
    startY: number;
    endX: number;
    endY: number;
    startTime: number;
    duration: number;
    vx: number;
    vy: number;
    gravity: number;
  }
>();
let rafId: number | null = null;

function formatQueueStatus(status: QueueStatus): string {
  switch (status) {
    case "pending":
      return "Pending";
    case "uploading":
      return "Uploading";
    case "processing":
      return "Processing";
    case "complete":
      return "Complete";
    case "error":
      return "Error";
    case "duplicate":
      return "Duplicate";
    case "cancelled":
      return "Cancelled";
    case "dismissed":
      return "Dismissed";
    default:
      return status;
  }
}

function isDismissable(item: QueueJob): boolean {
  return (
    item.status === "complete" ||
    item.status === "error" ||
    item.status === "duplicate" ||
    item.status === "cancelled"
  );
}

async function handleDismiss(item: QueueJob) {
  try {
    await dismissJob(item.id);
  } catch (error) {
    console.error("[queue] dismiss failed:", error);
  }
}

function formatQueuePhase(phase?: string): string {
  if (!phase) return "";
  switch (phase) {
    case "uploading":
      return "Uploading";
    case "hashing":
      return "Hashing";
    case "checking_duplicate":
      return "Checking";
    case "storing":
      return "Storing";
    case "extracting":
      return "Extracting";
    case "indexing":
      return "Indexing";
    case "scanning":
      return "Scanning";
    case "resetting":
      return "Resetting";
    case "downloading":
      return "Downloading";
    default:
      return phase.replace(/_/g, " ");
  }
}

function handleOutsideQueueClick(event: MouseEvent) {
  if (!isQueueOpen.value) return;
  const target = event.target as Node | null;
  if (!target) return;
  if (queueRef.value && queueRef.value.contains(target)) return;
  isQueueOpen.value = false;
}

function updateTargetPoint() {
  if (!queueButtonRef.value) return;
  requestAnimationFrame(() => {
    if (!queueButtonRef.value) return;
    const rect = queueButtonRef.value.getBoundingClientRect();
    targetPoint.value = {
      x: rect.left + rect.width / 2 - 6,
      y: rect.top + rect.height / 2 - 2,
    };
  });
}

function getBurstStyle(burst: {
  x: number;
  y: number;
  scale: number;
  opacity: number;
}) {
  return {
    transform: `translate(${burst.x}px, ${burst.y}px) scale(${burst.scale})`,
    opacity: String(burst.opacity),
  } as Record<string, string>;
}

function startBurst(burst: { id: string; x: number; y: number }) {
  const endX = targetPoint.value.x;
  const endY = targetPoint.value.y;
  const startX = burst.x;
  const startY = burst.y;
  const distance = Math.hypot(endX - startX, endY - startY);
  const duration = Math.min(780, Math.max(420, distance * 0.55));
  const t = duration / 1000;
  const baseGravity = Math.min(5200, Math.max(3200, distance * 3.8));
  const deltaY = endY - startY;
  const minGravityForUpward = (2 * deltaY) / (t * t) + 800;
  const gravity = Math.max(baseGravity, minGravityForUpward);
  const vx = (endX - startX) / t;
  const vy = (deltaY - 0.5 * gravity * t * t) / t;
  burstMeta.set(burst.id, {
    startX,
    startY,
    endX,
    endY,
    startTime: performance.now(),
    duration,
    vx,
    vy,
    gravity,
  });
  if (rafId === null) {
    rafId = requestAnimationFrame(stepBursts);
  }
}

function stepBursts(timestamp: number) {
  const nextBursts: {
    id: string;
    x: number;
    y: number;
    scale: number;
    opacity: number;
  }[] = [];
  for (const [id, meta] of burstMeta.entries()) {
    const elapsed = timestamp - meta.startTime;
    const progress = Math.min(1, elapsed / meta.duration);
    const t = elapsed / 1000;
    if (progress >= 1) {
      burstMeta.delete(id);
      clearQueueEject(id);
      pulseActive.value = true;
      setTimeout(() => {
        pulseActive.value = false;
      }, 320);
      continue;
    }
    const x = meta.startX + meta.vx * t;
    const y = meta.startY + meta.vy * t + 0.5 * meta.gravity * t * t;
    const scale = 1 - 0.35 * progress;
    const opacity = 1;
    nextBursts.push({ id, x, y, scale, opacity });
  }
  activeBursts.value = nextBursts;
  if (burstMeta.size > 0) {
    rafId = requestAnimationFrame(stepBursts);
  } else {
    rafId = null;
  }
}

onMounted(() => {
  document.addEventListener("click", handleOutsideQueueClick);
  updateTargetPoint();
  window.addEventListener("resize", updateTargetPoint);
});

onBeforeUnmount(() => {
  document.removeEventListener("click", handleOutsideQueueClick);
  window.removeEventListener("resize", updateTargetPoint);
});

watch(isQueueOpen, async () => {
  await nextTick();
  updateTargetPoint();
});

watch(ejectBursts, async (items) => {
  await nextTick();
  updateTargetPoint();
  for (const item of items) {
    if (!burstMeta.has(item.id)) {
      startBurst(item);
    }
  }
});

watch(queueItems, (items) => {
  if (!hasInitializedQueue.value) {
    items.forEach((item) => seenJobIds.add(item.id));
    hasInitializedQueue.value = true;
    return;
  }
  if (!queueButtonRef.value) return;
  const rect = queueButtonRef.value.getBoundingClientRect();
  const startX = rect.left + rect.width / 2 + (Math.random() * 120 - 60);
  const startY = rect.top + rect.height / 2 + 90 + Math.random() * 60;

  for (const item of items) {
    if (seenJobIds.has(item.id)) continue;
    launchQueueEject(startX, startY);
    seenJobIds.add(item.id);
  }
});
</script>

<template>
  <div ref="queueRef" class="queue-fab">
    <button
      ref="queueButtonRef"
      class="queue-toggle"
      :class="{ pulse: pulseActive }"
      @click="isQueueOpen = !isQueueOpen"
    >
      <ListOrdered :size="16" />
      <span v-if="queueCount > 0" class="queue-badge">{{ queueCount }}</span>
    </button>
    <Transition name="queue-panel">
      <div v-if="isQueueOpen" class="queue-panel">
        <div v-if="queueItems.length === 0" class="queue-empty">
          No active tasks.
        </div>
        <div v-else class="queue-list">
          <div v-for="item in queueItems" :key="item.id" class="queue-item">
            <div class="queue-header">
              <div class="queue-name" :title="item.name ?? ''">
                {{ item.name ?? "Untitled job" }}
              </div>
              <button
                v-if="isDismissable(item)"
                class="queue-dismiss"
                @click.stop="handleDismiss(item)"
              >
                <X :size="14" />
              </button>
            </div>
            <div class="queue-meta">
              <span class="queue-status" :class="item.status">{{
                formatQueueStatus(item.status)
              }}</span>
              <span v-if="item.phase" class="queue-phase">{{
                formatQueuePhase(item.phase)
              }}</span>
              <span
                v-if="item.progress !== null && item.progress !== undefined"
                class="queue-progress-text"
                >{{ item.progress }}%</span
              >
            </div>
            <div
              v-if="item.progress !== null && item.progress !== undefined"
              class="queue-progress"
            >
              <div
                class="queue-progress-fill"
                :style="{ width: `${item.progress}%` }"
              ></div>
            </div>
            <div
              v-if="item.status === 'error' && item.error"
              class="queue-error"
            >
              {{ item.error }}
            </div>
            <div
              v-if="item.status === 'duplicate' && item.duplicatePath"
              class="queue-duplicate"
            >
              Duplicate: {{ item.duplicatePath }}
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </div>

  <Teleport to="body">
    <div class="queue-eject-layer" aria-hidden="true">
      <span
        v-for="burst in activeBursts"
        :key="burst.id"
        class="queue-eject-ball"
        :style="getBurstStyle(burst)"
      ></span>
    </div>
  </Teleport>
</template>

<style scoped>
.queue-fab {
  position: fixed;
  right: 16px;
  bottom: 28px;
  display: flex;
  flex-direction: column-reverse;
  align-items: flex-end;
  gap: 8px;
  z-index: 2000;
}

.queue-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 999px;
  border: 1px solid var(--border-color);
  background: var(--color-white);
  color: var(--text-primary);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 8px 20px var(--alpha-black-10);
  transition: all 0.15s;
}

.queue-toggle:hover {
  background: var(--bg-card-hover);
  border-color: var(--accent-bright);
}

[data-theme="dark"] .queue-toggle {
  background: var(--bg-panel);
  border-color: var(--color-neutral-200);
  color: var(--text-primary);
  box-shadow: 0 10px 24px var(--alpha-black-20);
}

[data-theme="dark"] .queue-toggle:hover {
  background: var(--color-neutral-150);
  border-color: var(--accent-color);
}

.queue-toggle.pulse {
  animation: queuePulse 0.28s ease;
}

.queue-badge {
  min-width: 18px;
  height: 18px;
  padding: 0 6px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 700;
  background: var(--accent-color);
  color: var(--color-white);
}

.queue-toggle.pulse .queue-badge {
  animation: badgeBounce 0.32s ease;
}

.queue-panel {
  width: 280px;
  max-height: 216px;
  overflow-y: auto;
  background: var(--bg-panel);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 12px;
  box-shadow: 0 10px 24px var(--alpha-black-15);
}

[data-theme="dark"] .queue-panel {
  border-color: var(--color-neutral-200);
  box-shadow: 0 12px 28px var(--alpha-black-25);
}

.queue-empty {
  font-size: 12px;
  color: var(--text-secondary);
  text-align: center;
  padding: 12px 0;
}

.queue-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.queue-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px;
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: 10px;
}

.queue-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

[data-theme="dark"] .queue-item {
  background: var(--color-neutral-105);
  border-color: var(--color-neutral-150);
}

.queue-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.queue-dismiss {
  border: none;
  background: none;
  color: var(--text-secondary);
  font-size: 10px;
  padding: 0;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.queue-dismiss:hover {
  color: var(--text-primary);
}

.queue-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: var(--text-secondary);
}

.queue-phase {
  color: var(--text-secondary);
}

.queue-status {
  font-weight: 600;
}

.queue-status.uploading,
.queue-status.processing {
  color: var(--color-info-800);
}

.queue-status.pending {
  color: var(--color-neutral-650);
}

.queue-status.error {
  color: var(--color-danger-700);
}

.queue-status.duplicate {
  color: var(--color-warning-800);
}

.queue-progress {
  height: 4px;
  background: var(--color-neutral-240);
  border-radius: 999px;
  overflow: hidden;
}

.queue-progress-fill {
  height: 100%;
  background: var(--accent-color);
  transition: width 0.2s ease;
}

.queue-progress-text {
  color: var(--text-secondary);
  margin-left: auto;
}

.queue-error {
  font-size: 11px;
  color: var(--color-danger-700);
}

.queue-duplicate {
  font-size: 11px;
  color: var(--color-warning-800);
}

.queue-panel-enter-active,
.queue-panel-leave-active {
  transition:
    opacity 0.18s ease,
    transform 0.18s ease;
}

.queue-panel-enter-from,
.queue-panel-leave-to {
  opacity: 0;
  transform: translateY(12px) scale(0.98);
}

.queue-panel-enter-to,
.queue-panel-leave-from {
  opacity: 1;
  transform: translateY(0) scale(1);
}

.queue-eject-layer {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 2000;
}

.queue-eject-ball {
  position: fixed;
  left: 0;
  top: 0;
  width: 16px;
  height: 16px;
  border-radius: 999px;
  background: var(--color-accent-400);
}

@keyframes queuePulse {
  0% {
    transform: scale(1);
  }

  40% {
    transform: scale(1.08);
  }

  100% {
    transform: scale(1);
  }
}

@keyframes badgeBounce {
  0% {
    transform: translateY(0) scale(1);
  }

  40% {
    transform: translateY(-3px) scale(1.1);
  }

  70% {
    transform: translateY(1px) scale(0.98);
  }

  100% {
    transform: translateY(0) scale(1);
  }
}
</style>
