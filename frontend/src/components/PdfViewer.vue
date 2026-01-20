<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as pdfjsLib from 'pdfjs-dist'
import type { BoundingBox } from '../types'

// Setup PDF.js worker
pdfjsLib.GlobalWorkerOptions.workerSrc = '/pdf.worker.mjs'

const props = defineProps<{
  fileUrl: string
  highlights?: BoundingBox[]
  initialPage?: number
}>()

const canvasRef = ref<HTMLCanvasElement>()
const overlayRef = ref<HTMLDivElement>()
const containerRef = ref<HTMLDivElement>()
const pageContainerRef = ref<HTMLDivElement>()
const currentPage = ref(1)
const totalPages = ref(0)
const isLoading = ref(true)
const error = ref<string>()
const scale = ref(1.5)

let pdfDoc: pdfjsLib.PDFDocumentProxy | null = null
let renderTask: pdfjsLib.RenderTask | null = null
let renderSeq = 0

// Drag-to-pan state
const isDragMode = ref(false)
const isDragging = ref(false)
let dragStartX = 0
let dragStartY = 0
let scrollStartX = 0
let scrollStartY = 0

const loadPdf = async () => {
  try {
    if (!props.fileUrl) return
    renderSeq += 1
    if (renderTask) {
      renderTask.cancel()
      renderTask = null
    }
    if (pdfDoc) {
      await pdfDoc.destroy()
      pdfDoc = null
    }
    isLoading.value = true
    error.value = undefined

    const resp = await fetch(props.fileUrl)
    if (!resp.ok) {
      throw new Error(`Failed to load PDF (${resp.status})`)
    }
    const data = await resp.arrayBuffer()
    const loadingTask = pdfjsLib.getDocument({ data })
    pdfDoc = await loadingTask.promise
    totalPages.value = pdfDoc.numPages

    // Set initial page if provided and valid
    if (props.initialPage && props.initialPage >= 1 && props.initialPage <= totalPages.value) {
      currentPage.value = props.initialPage
    }

    // Must set isLoading=false first so canvas renders
    isLoading.value = false

    // Wait for DOM to update before rendering
    await nextTick()
    await renderPage()
  } catch (err) {
    console.error('Error loading PDF:', err)
    error.value = 'Failed to load PDF'
    isLoading.value = false
  }
}

const renderPage = async () => {
  if (!pdfDoc || !canvasRef.value || !overlayRef.value) return

  try {
    const seq = ++renderSeq
    // Cancel any ongoing render task
    if (renderTask) {
      renderTask.cancel()
    }

    const page = await pdfDoc.getPage(currentPage.value)
    if (seq !== renderSeq) return
    const viewport = page.getViewport({ scale: scale.value })

    const canvas = canvasRef.value
    const overlay = overlayRef.value
    if (!canvas || !overlay) return
    const context = canvas.getContext('2d')
    if (!context) return

    canvas.height = viewport.height
    canvas.width = viewport.width

    const renderContext = {
      canvas,
      canvasContext: context,
      viewport: viewport,
    }

    renderTask = page.render(renderContext)
    await renderTask.promise
    if (seq !== renderSeq) return
    renderTask = null

    syncOverlay(viewport)

    // Render highlights
    renderHighlights(viewport, page.pageNumber)

    // Scroll to first highlight if this is the initial render
    await nextTick()
    scrollToFirstHighlight()
  } catch (err: any) {
    if (err?.name !== 'RenderingCancelledException') {
      console.error('Error rendering page:', err)
      error.value = 'Failed to render page'
    }
  }
}

const syncOverlay = (viewport: any) => {
  if (!overlayRef.value || !canvasRef.value) return

  // With the new wrapper, overlay just needs to match canvas size
  // Position is handled by CSS (absolute top:0 left:0 within wrapper)
  overlayRef.value.style.width = `${viewport.width}px`
  overlayRef.value.style.height = `${viewport.height}px`
}

const renderHighlights = (viewport: any, pageNumber: number) => {
  if (!overlayRef.value || !props.highlights) return

  // Clear existing highlights
  overlayRef.value.innerHTML = ''

  // Filter highlights for current page
  const pageHighlights = props.highlights.filter(h => h.page === pageNumber)
  const pdfHeight = (viewport.viewBox?.[3] ?? 0) - (viewport.viewBox?.[1] ?? 0)

  for (const highlight of pageHighlights) {
    const highlightDiv = document.createElement('div')
    highlightDiv.className = 'pdf-highlight'

    // Convert PyMuPDF (top-left) coords to PDF.js (bottom-left) coords
    const [x0, y0, x1, y1] = viewport.convertToViewportRectangle([
      highlight.x0,
      pdfHeight - highlight.y1,
      highlight.x1,
      pdfHeight - highlight.y0,
    ])

    const left = Math.min(x0, x1)
    const top = Math.min(y0, y1)
    const width = Math.abs(x1 - x0)
    const height = Math.abs(y1 - y0)

    // Set position and size (inline styles required for dynamic positioning)
    highlightDiv.style.position = 'absolute'
    highlightDiv.style.left = `${left}px`
    highlightDiv.style.top = `${top}px`
    highlightDiv.style.width = `${width}px`
    highlightDiv.style.height = `${height}px`
    highlightDiv.style.background = 'rgba(255, 235, 59, 0.4)'
    highlightDiv.style.border = '1px solid rgba(255, 193, 7, 0.8)'
    highlightDiv.style.pointerEvents = 'none'

    overlayRef.value.appendChild(highlightDiv)
  }
}

const scrollToFirstHighlight = () => {
  if (!containerRef.value || !overlayRef.value) return

  const firstHighlight = overlayRef.value.querySelector('.pdf-highlight')
  if (firstHighlight) {
    firstHighlight.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}

const nextPage = () => {
  if (currentPage.value < totalPages.value) {
    currentPage.value++
  }
}

const prevPage = () => {
  if (currentPage.value > 1) {
    currentPage.value--
  }
}

const zoomIn = () => {
  scale.value = Math.min(scale.value + 0.25, 3)
  renderPage()
}

const zoomOut = () => {
  scale.value = Math.max(scale.value - 0.25, 0.5)
  renderPage()
}

// Watch for page changes
watch(currentPage, () => {
  renderPage()
})

watch(() => props.highlights, () => {
  if (pdfDoc) {
    renderPage()
  }
}, { deep: true })

// Watch for file URL changes
watch(() => props.fileUrl, () => {
  loadPdf()
})

// Drag-to-pan functionality (H key for Hand tool - standard in PDF viewers)
const handleKeyDown = (e: KeyboardEvent) => {
  if (e.key === 'h' && !isDragMode.value && pageContainerRef.value) {
    isDragMode.value = true
  }
}

const handleKeyUp = (e: KeyboardEvent) => {
  if (e.key === 'h') {
    isDragMode.value = false
    isDragging.value = false
  }
}

const handleMouseDown = (e: MouseEvent) => {
  if (!isDragMode.value || !pageContainerRef.value) return
  isDragging.value = true
  dragStartX = e.clientX
  dragStartY = e.clientY
  scrollStartX = pageContainerRef.value.scrollLeft
  scrollStartY = pageContainerRef.value.scrollTop
  e.preventDefault()
}

const handleMouseMove = (e: MouseEvent) => {
  if (!isDragging.value || !pageContainerRef.value) return
  const dx = e.clientX - dragStartX
  const dy = e.clientY - dragStartY
  pageContainerRef.value.scrollLeft = scrollStartX - dx
  pageContainerRef.value.scrollTop = scrollStartY - dy
  e.preventDefault()
}

const handleMouseUp = () => {
  isDragging.value = false
}

onMounted(() => {
  loadPdf()
  window.addEventListener('keydown', handleKeyDown)
  window.addEventListener('keyup', handleKeyUp)
  window.addEventListener('mouseup', handleMouseUp)
})

onUnmounted(() => {
  renderSeq += 1
  if (renderTask) {
    renderTask.cancel()
    renderTask = null
  }
  if (pdfDoc) {
    pdfDoc.destroy().catch(() => {})
    pdfDoc = null
  }
  window.removeEventListener('keydown', handleKeyDown)
  window.removeEventListener('keyup', handleKeyUp)
  window.removeEventListener('mouseup', handleMouseUp)
})
</script>

<template>
  <div ref="containerRef" class="pdf-viewer">
    <div v-if="isLoading" class="pdf-loading">
      <div class="spinner"></div>
      <p>Loading PDF...</p>
    </div>

    <div v-else-if="error" class="pdf-error">
      <p>{{ error }}</p>
    </div>

    <div v-else class="pdf-content">
      <div class="pdf-controls">
        <button @click="prevPage" :disabled="currentPage <= 1">Previous</button>
        <span class="page-info">Page {{ currentPage }} / {{ totalPages }}</span>
        <button @click="nextPage" :disabled="currentPage >= totalPages">Next</button>
        <div class="zoom-controls">
          <button @click="zoomOut" :disabled="scale <= 0.5">-</button>
          <span>{{ Math.round(scale * 100) }}%</span>
          <button @click="zoomIn" :disabled="scale >= 3">+</button>
        </div>
        <div class="keyboard-hint" :class="{ active: isDragMode }">
          <kbd>H</kbd>
          <span v-if="isDragMode">Pan mode active</span>
          <span v-else>to pan</span>
        </div>
      </div>

      <div
        ref="pageContainerRef"
        class="pdf-page-container"
        :class="{ 'drag-mode': isDragMode, 'dragging': isDragging }"
        @mousedown="handleMouseDown"
        @mousemove="handleMouseMove"
      >
        <div class="pdf-canvas-wrapper">
          <canvas ref="canvasRef"></canvas>
          <div ref="overlayRef" class="pdf-overlay"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.pdf-viewer {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--pdf-bg);
  overflow: hidden;
}

.pdf-loading,
.pdf-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--pdf-muted);
}

.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid rgba(255, 255, 255, 0.2);
  border-top-color: var(--pdf-btn-text);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.pdf-controls {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: var(--pdf-panel);
  border-bottom: 1px solid var(--pdf-panel-border);
}

.pdf-controls button {
  padding: 6px 12px;
  background: var(--pdf-btn);
  color: var(--pdf-btn-text);
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.2s;
}

.pdf-controls button:hover:not(:disabled) {
  background: var(--pdf-btn-hover);
}

.pdf-controls button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.page-info {
  color: var(--pdf-muted);
  font-size: 14px;
  margin: 0 8px;
}

.zoom-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.zoom-controls span {
  color: var(--pdf-muted);
  font-size: 14px;
  min-width: 50px;
  text-align: center;
}

.keyboard-hint {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--pdf-muted);
  font-size: 12px;
  margin-left: 16px;
  transition: color 0.2s;
}

.keyboard-hint.active {
  color: var(--pdf-hint);
}

.keyboard-hint kbd {
  display: inline-block;
  padding: 2px 6px;
  font-family: monospace;
  font-size: 11px;
  font-weight: 600;
  color: var(--pdf-btn-text);
  background: var(--pdf-btn);
  border: 1px solid var(--pdf-panel-border);
  border-radius: 3px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
  transition: all 0.2s;
}

.keyboard-hint.active kbd {
  background: var(--pdf-hint);
  border-color: var(--pdf-hint);
  box-shadow: 0 0 8px rgba(76, 175, 80, 0.4);
}

.pdf-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.pdf-page-container {
  flex: 1;
  overflow: auto;
  padding: 20px;
}

.pdf-page-container.drag-mode {
  cursor: grab;
}

.pdf-page-container.dragging {
  cursor: grabbing;
  user-select: none;
}

.pdf-canvas-wrapper {
  position: relative;
  display: block;
  margin: 0 auto;
  width: fit-content;
}

canvas {
  display: block;
  box-shadow: var(--shadow-md);
}

.pdf-overlay {
  position: absolute;
  top: 0;
  left: 0;
  pointer-events: none;
  z-index: 10;
}

.pdf-highlight {
  position: absolute;
  background: var(--alpha-highlight-40);
  border: 1px solid var(--color-warning-400);
  pointer-events: none;
  animation: highlight-pulse 1s ease-out;
}

@keyframes highlight-pulse {
  0% {
    background: var(--alpha-highlight-50);
    transform: scale(1.02);
  }
  100% {
    background: var(--alpha-highlight-40);
    transform: scale(1);
  }
}
</style>

