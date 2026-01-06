<script setup lang="ts">
import type { AnswerBlock } from "../types"

defineProps<{ block: AnswerBlock }>()

defineEmits<{ (event: "cite", citation: string): void }>()
</script>

<template>
  <section class="answer-block">
    <h3>{{ block.heading }}</h3>
    <p>{{ block.body }}</p>
    <div class="answer-citations" v-if="block.citations.length">
      <button
        v-for="citation in block.citations"
        :key="citation"
        class="citation"
        @click="$emit('cite', citation)"
      >
        {{ citation }}
      </button>
    </div>
  </section>
</template>
