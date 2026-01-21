<script setup lang="ts">
import { computed } from "vue"
import PdfViewer from "./PdfViewer.vue"
import type { HighlightGroup } from "../types"

const props = defineProps<{
  fileUrl: string
  highlightGroups?: HighlightGroup[]
  initialPage?: number
}>()

const emit = defineEmits<{
  (event: 'progress', percent: number): void
}>()

const startPage = computed(() => {
  if (props.initialPage) return props.initialPage
  const firstGroup = props.highlightGroups?.[0]
  if (firstGroup?.boxes?.length) return firstGroup.boxes[0].page
  return undefined
})
</script>

<template>
  <PdfViewer :file-url="fileUrl" :highlight-groups="highlightGroups" :initial-page="startPage"
    @progress="emit('progress', $event)" class="pdf-preview" />
</template>

<style scoped>
.pdf-preview {
  width: 100%;
  height: 100%;
}
</style>
