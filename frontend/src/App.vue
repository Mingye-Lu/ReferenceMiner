<script setup lang="ts">
import { onMounted } from 'vue'
import { initTheme } from './utils/theme'

onMounted(() => {
  initTheme()
})
</script>

<template>
  <router-view />
</template>

<style>
/* Global styles can stay in style.css */
</style>
