<script setup lang="ts">
import { ref, watch } from "vue"

const props = defineProps<{ scope: string[] }>()

const emit = defineEmits<{ (event: "update", scope: string[]): void }>()
const local = ref<string[]>([])

watch(
  () => props.scope,
  (next) => {
    local.value = [...next]
  },
  { immediate: true }
)

function removeChip(index: number) {
  local.value.splice(index, 1)
  emitUpdate()
}

function addChip() {
  local.value.push("New scope item")
  emitUpdate()
}

function emitUpdate() {
  emit("update", local.value)
}
</script>

<template>
  <div class="scope-chips">
    <div v-for="(item, index) in local" :key="index" class="scope-chip">
      <input v-model="local[index]" @blur="emitUpdate" />
      <button class="chip-remove" @click="removeChip(index)">x</button>
    </div>
    <button class="chip-add" @click="addChip">+ Add scope</button>
  </div>
</template>
