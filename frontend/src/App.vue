<script setup lang="ts">
import { onMounted, onBeforeUnmount } from "vue";
import { initTheme } from "./utils/theme";
import QueueFab from "./components/QueueFab.vue";
// import { useQueue } from "./composables/useQueue";

onMounted(() => {
  initTheme();
  // document.addEventListener('click', handleDebugQueueEject)
});

onBeforeUnmount(() => {
//   document.removeEventListener("click", handleDebugQueueEject);
});

// function handleDebugQueueEject(event: MouseEvent) {
//   launchQueueEject(event.clientX, event.clientY);
// }
</script>

<template>
  <router-view />
  <QueueFab />
</template>

<style>
/* Global styles can stay in style.css */
</style>
