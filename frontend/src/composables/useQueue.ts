import { computed, ref } from 'vue'
import type { UploadPhase, UploadQueueItem, UploadStatus } from '../types'
import { getFileName } from '../utils'

const uploadQueueItems = ref<UploadQueueItem[]>([])
const reprocessQueueItems = ref<UploadQueueItem[]>([])
const ejectBursts = ref<{ id: string; x: number; y: number }[]>([])
const lastEjectId = ref<string | null>(null)

const queueItems = computed(() => {
  const combined = [...uploadQueueItems.value, ...reprocessQueueItems.value]
  return combined.filter((item) => item.status !== 'complete')
})

const queueCount = computed(() => {
  const combined = [...uploadQueueItems.value, ...reprocessQueueItems.value]
  return combined.filter(
    (item) =>
      item.status === 'pending' ||
      item.status === 'uploading' ||
      item.status === 'processing',
  ).length
})

function setQueueItems(items: UploadQueueItem[]) {
  uploadQueueItems.value = items
}

function clearReprocessQueue() {
  reprocessQueueItems.value = []
}

function upsertReprocessQueueItem(
  relPath: string,
  status: UploadStatus,
  phase?: UploadPhase,
) {
  const existing = reprocessQueueItems.value.find((item) => item.id === relPath)
  const progress = status === 'complete' ? 100 : 0
  const name = getFileName(relPath)
  if (!existing) {
    reprocessQueueItems.value = [
      ...reprocessQueueItems.value,
      {
        id: relPath,
        name,
        status,
        progress,
        phase,
      },
    ]
    return
  }
  const next = [...reprocessQueueItems.value]
  const idx = next.findIndex((item) => item.id === relPath)
  next[idx] = {
    ...next[idx],
    name,
    status,
    progress,
    phase,
  }
  reprocessQueueItems.value = next
}

function launchQueueEject(x: number, y: number) {
  const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`
  ejectBursts.value = [...ejectBursts.value, { id, x, y }]
  lastEjectId.value = id
}

function clearQueueEject(id: string) {
  ejectBursts.value = ejectBursts.value.filter((item) => item.id !== id)
}

export function useQueue() {
  return {
    uploadQueueItems,
    reprocessQueueItems,
    ejectBursts,
    lastEjectId,
    queueItems,
    queueCount,
    setQueueItems,
    clearReprocessQueue,
    upsertReprocessQueueItem,
    launchQueueEject,
    clearQueueEject,
  }
}
