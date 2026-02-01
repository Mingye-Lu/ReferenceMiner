import { computed, ref } from "vue";
import type { QueueJob } from "../types";
import { fetchQueueJobs, streamQueueJobs } from "../api/client";

const queueJobs = ref<QueueJob[]>([]);
const ejectBursts = ref<{ id: string; x: number; y: number }[]>([]);
const lastEjectId = ref<string | null>(null);

let streamAbort: AbortController | null = null;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 5;
const BASE_RECONNECT_DELAY = 1000;

const COMPLETED_GRACE_SECONDS = 15;

const queueItems = computed(() => {
  const now = Date.now() / 1000;
  return queueJobs.value.filter((item: QueueJob) => {
    if (item.status === "cancelled") return false;
    if (item.status === "complete") {
      const updatedAt = item.updatedAt ?? 0;
      return now - updatedAt <= COMPLETED_GRACE_SECONDS;
    }
    return true;
  });
});

const queueCount = computed(
  () =>
    queueJobs.value.filter(
      (item: QueueJob) =>
        item.status === "pending" ||
        item.status === "uploading" ||
        item.status === "processing",
    ).length,
);

function upsertQueueJob(job: QueueJob) {
  const idx = queueJobs.value.findIndex((item) => item.id === job.id);
  if (idx === -1) {
    console.log(
      "[useQueue] new job:",
      job.id.slice(0, 8),
      "status:",
      job.status,
      "phase:",
      job.phase,
    );
    queueJobs.value = [job, ...queueJobs.value];
    return;
  }
  const prev = queueJobs.value[idx];
  if (prev.phase !== job.phase || prev.status !== job.status) {
    console.log(
      "[useQueue] update job:",
      job.id.slice(0, 8),
      "status:",
      prev.status,
      "->",
      job.status,
      "phase:",
      prev.phase,
      "->",
      job.phase,
    );
  }
  const next = [...queueJobs.value];
  next[idx] = { ...next[idx], ...job };
  queueJobs.value = next;
}

async function refreshQueue(params?: {
  scope?: string;
  projectId?: string;
  includeCompleted?: boolean;
}) {
  const items = await fetchQueueJobs(params);
  console.log(
    "[useQueue] refreshQueue got",
    items.length,
    "jobs, active phases:",
    items
      .filter((j) => j.phase)
      .map((j) => `${j.id.slice(0, 8)}:${j.phase}`)
      .join(", "),
  );
  queueJobs.value = items;
}

function startQueueStream(params?: { scope?: string; projectId?: string }) {
  stopQueueStream();
  reconnectAttempts = 0;

  async function connect() {
    streamAbort = new AbortController();

    try {
      await streamQueueJobs(
        params,
        (job: QueueJob) => {
          upsertQueueJob(job);
          reconnectAttempts = 0;
        },
        streamAbort.signal,
        (error: Error) => {
          console.log("[useQueue] stream error:", error.message);
          handleStreamError(params);
        },
      );
    } catch (error) {
      console.error("[useQueue] connection failed:", error);
      handleStreamError(params);
    }
  }

  async function handleStreamError(params?: {
    scope?: string;
    projectId?: string;
  }) {
    if (streamAbort?.signal.aborted) {
      console.log("[useQueue] stream was aborted, not reconnecting");
      return;
    }

    console.log("[useQueue] polling to recover state...");
    try {
      await refreshQueue({ ...params, includeCompleted: true });
      console.log("[useQueue] state recovered successfully");
    } catch (error) {
      console.error("[useQueue] recovery poll failed:", error);
    }

    if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
      reconnectAttempts++;
      const delay = BASE_RECONNECT_DELAY * Math.pow(2, reconnectAttempts - 1);
      console.log(
        `[useQueue] reconnecting in ${delay}ms (attempt ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`,
      );
      setTimeout(() => connect(), delay);
    } else {
      console.error("[useQueue] max reconnect attempts reached, giving up");
    }
  }

  connect();
}

function stopQueueStream() {
  if (streamAbort) {
    streamAbort.abort();
    streamAbort = null;
  }
  reconnectAttempts = 0;
}

function launchQueueEject(x: number, y: number) {
  const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  ejectBursts.value = [...ejectBursts.value, { id, x, y }];
  lastEjectId.value = id;
}

function clearQueueEject(id: string) {
  ejectBursts.value = ejectBursts.value.filter((item) => item.id !== id);
}

export function useQueue() {
  return {
    queueJobs,
    queueItems,
    queueCount,
    ejectBursts,
    lastEjectId,
    refreshQueue,
    startQueueStream,
    stopQueueStream,
    launchQueueEject,
    clearQueueEject,
  };
}
