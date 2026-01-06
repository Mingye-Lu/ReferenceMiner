<script setup lang="ts">
import type { IndexStatus } from "../types"

defineProps<{ status: IndexStatus | null }>()
</script>

<template>
  <div class="status-banner" :class="{ ready: status?.indexed }">
    <div class="status-title">
      {{ status?.indexed ? "Index ready" : "Index missing" }}
    </div>
    <div class="status-meta">
      <span v-if="status?.lastIngest">Last ingest: {{ status.lastIngest }}</span>
      <span v-else>Run ingest to build the evidence cache.</span>
    </div>
    <div class="status-counts" v-if="status?.indexed">
      <span>{{ status.totalFiles }} files</span>
      <span>{{ status.totalChunks }} chunks</span>
    </div>
  </div>
</template>
