<script setup lang="ts">
import { onMounted, onBeforeUnmount } from "vue";
import { initTheme } from "./utils/theme";
import QueueFab from "./components/QueueFab.vue";
import { useQueue } from "./composables/useQueue";

const { refreshQueue, startQueueStream, stopQueueStream } = useQueue();

onMounted(() => {
  initTheme();
  void refreshQueue({ includeCompleted: true });
  startQueueStream();
});

onBeforeUnmount(() => {
  stopQueueStream();
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
