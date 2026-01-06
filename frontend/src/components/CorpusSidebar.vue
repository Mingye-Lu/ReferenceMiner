<script setup lang="ts">
import { computed, ref } from "vue"
import type { ManifestEntry } from "../types"

const props = defineProps<{ manifest: ManifestEntry[] }>()

const query = ref("")
const filter = ref<"all" | "pdf" | "docx" | "image" | "table" | "text">("all")

const filtered = computed(() => {
  return (props.manifest ?? []).filter((item) => {
    const matchesQuery = query.value
      ? item.relPath.toLowerCase().includes(query.value.toLowerCase()) ||
        (item.title ?? "").toLowerCase().includes(query.value.toLowerCase())
      : true
    const matchesType = filter.value === "all" || item.fileType === filter.value
    return matchesQuery && matchesType
  })
})
</script>

<template>
  <aside class="panel corpus-panel">
    <header class="panel-header">
      <h2>Corpus</h2>
      <p>Local references and extracted metadata.</p>
    </header>

    <div class="corpus-controls">
      <input
        v-model="query"
        type="search"
        placeholder="Search files or titles"
        aria-label="Search references"
      />
      <div class="filter-row">
        <button
          v-for="type in ['all','pdf','docx','image','table','text']"
          :key="type"
          :class="['filter-chip', { active: filter === type }]"
          @click="filter = type as typeof filter"
        >
          {{ type }}
        </button>
      </div>
    </div>

    <div class="corpus-list">
      <div v-if="filtered.length === 0" class="empty-state">
        No files match the current filters.
      </div>
      <article v-for="item in filtered" :key="item.relPath" class="corpus-item">
        <div class="corpus-title">
          <span class="file-name">{{ item.relPath }}</span>
          <span class="file-type">{{ item.fileType }}</span>
        </div>
        <div class="corpus-meta">
          <span v-if="item.pageCount">{{ item.pageCount }} pages</span>
          <span v-if="item.sizeBytes">{{ Math.round(item.sizeBytes / 1024) }} KB</span>
        </div>
        <p class="corpus-abstract" v-if="item.abstract">{{ item.abstract }}</p>
        <p class="corpus-abstract muted" v-else>No abstract detected.</p>
      </article>
    </div>
  </aside>
</template>
