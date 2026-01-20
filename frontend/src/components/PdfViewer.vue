<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick, computed } from 'vue'
import * as pdfjsLib from 'pdfjs-dist'
import type { HighlightGroup } from '../types'

// Setup PDF.js worker
pdfjsLib.GlobalWorkerOptions.workerSrc = '/pdf.worker.mjs'

const props = defineProps<{
  fileUrl: string
  highlightGroups?: HighlightGroup[]
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
const highlightEnabled = ref(true)
const pageInput = ref('1')
const fitMode = ref<'custom' | 'width'>('custom')
const zoomInput = ref('150')

let pdfDoc: pdfjsLib.PDFDocumentProxy | null = null
let renderTask: pdfjsLib.RenderTask | null = null
let renderSeq = 0
let lastViewport: any = null
let lastPageNumber = 0
let shouldAutoScroll = false
let resizeObserver: ResizeObserver | null = null
let resizeRaf = 0

const highlightPalette = [
  '#F59E0B',
  '#10B981',
  '#3B82F6',
  '#EF4444',
  '#8B5CF6',
  '#14B8A6',
  '#E11D48',
  '#6366F1',
]

const hasHighlights = computed(() => {
  return (props.highlightGroups?.length ?? 0) > 0
})

const normalizedGroups = computed<HighlightGroup[]>(() => {
  return props.highlightGroups ?? []
})

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
    pageInput.value = `${currentPage.value}`
    zoomInput.value = `${Math.round(scale.value * 100)}`
    shouldAutoScroll = true

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
    lastViewport = viewport
    lastPageNumber = page.pageNumber

    // Render highlights
    renderHighlights(viewport, page.pageNumber)

    // Scroll to first highlight if this is the initial render
    if (shouldAutoScroll) {
      await nextTick()
      scrollToFirstHighlight()
      shouldAutoScroll = false
    }
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
  if (!overlayRef.value) return

  // Clear existing highlights
  overlayRef.value.innerHTML = ''

  if (!highlightEnabled.value || !hasHighlights.value) {
    return
  }

  const pdfHeight = (viewport.viewBox?.[3] ?? 0) - (viewport.viewBox?.[1] ?? 0)
  const groups = normalizedGroups.value
  for (let groupIndex = 0; groupIndex < groups.length; groupIndex++) {
    const group = groups[groupIndex]
    const pageHighlights = group.boxes.filter(h => h.page === pageNumber)
    if (pageHighlights.length === 0) continue

    const color = group.color || colorForGroup(group, groupIndex)
    const border = color
    const background = toAlpha(color, 0.35)

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
      highlightDiv.style.background = background
      highlightDiv.style.border = `1px solid ${border}`
      highlightDiv.style.pointerEvents = 'none'

      overlayRef.value.appendChild(highlightDiv)
    }
  }

}

const colorForGroup = (group: HighlightGroup, index: number) => {
  if (group.color) return group.color
  const id = group.id || ''
  if (id) {
    let hash = 0
    for (let i = 0; i < id.length; i++) {
      hash = (hash * 31 + id.charCodeAt(i)) >>> 0
    }
    return highlightPalette[hash % highlightPalette.length]
  }
  return highlightPalette[index % highlightPalette.length]
}

const toAlpha = (color: string, alpha: number) => {
  const hex = color.replace('#', '')
  if (hex.length === 6) {
    const r = parseInt(hex.slice(0, 2), 16)
    const g = parseInt(hex.slice(2, 4), 16)
    const b = parseInt(hex.slice(4, 6), 16)
    return `rgba(${r}, ${g}, ${b}, ${alpha})`
  }
  return color
}

const scrollToFirstHighlight = () => {
  if (!containerRef.value || !overlayRef.value || !highlightEnabled.value) return

  const firstHighlight = overlayRef.value.querySelector('.pdf-highlight')
  if (firstHighlight) {
    firstHighlight.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}

const clamp = (value: number, min: number, max: number) => {
  return Math.min(Math.max(value, min), max)
}

const applyScale = (nextScale: number) => {
  fitMode.value = 'custom'
  scale.value = clamp(nextScale, 0.5, 3)
  zoomInput.value = `${Math.round(scale.value * 100)}`
  renderPage()
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
  applyScale(scale.value + 0.25)
}

const zoomOut = () => {
  applyScale(scale.value - 0.25)
}

const toggleHighlights = () => {
  highlightEnabled.value = !highlightEnabled.value
  if (lastViewport) {
    renderHighlights(lastViewport, lastPageNumber)
  } else {
    renderPage()
  }
}

const fitToWidth = async () => {
  if (!pdfDoc || !pageContainerRef.value) return
  const page = await pdfDoc.getPage(currentPage.value)
  const viewport = page.getViewport({ scale: 1 })
  const horizontalPadding = 40
  const availableWidth = Math.max(pageContainerRef.value.clientWidth - horizontalPadding, 200)
  fitMode.value = 'width'
  scale.value = clamp(availableWidth / viewport.width, 0.5, 3)
  zoomInput.value = `${Math.round(scale.value * 100)}`
  renderPage()
}

const goToPage = () => {
  const raw = parseInt(pageInput.value, 10)
  if (!Number.isFinite(raw)) {
    pageInput.value = `${currentPage.value}`
    return
  }
  const clamped = clamp(raw, 1, totalPages.value || 1)
  if (clamped !== currentPage.value) {
    currentPage.value = clamped
  } else {
    pageInput.value = `${clamped}`
  }
}

const goToZoom = () => {
  const raw = parseInt(zoomInput.value, 10)
  if (!Number.isFinite(raw)) {
    zoomInput.value = `${Math.round(scale.value * 100)}`
    return
  }
  const clampedPercent = clamp(raw, 50, 300)
  applyScale(clampedPercent / 100)
  zoomInput.value = `${Math.round(scale.value * 100)}`
}

const refreshHighlights = () => {
  if (!lastViewport) return
  renderHighlights(lastViewport, lastPageNumber)
}

// Watch for page changes
watch(currentPage, () => {
  pageInput.value = `${currentPage.value}`
  renderPage()
})

watch([() => props.highlightGroups, highlightEnabled], () => {
  if (!pdfDoc) return
  if (lastViewport) {
    refreshHighlights()
    return
  }
  renderPage()
}, { deep: true })

// Watch for file URL changes
watch(() => props.fileUrl, () => {
  highlightEnabled.value = true
  shouldAutoScroll = true
  loadPdf()
})


watch(
  () => props.initialPage,
  (page) => {
    if (!pdfDoc || !page) return
    if (page >= 1 && page <= totalPages.value && currentPage.value !== page) {
      currentPage.value = page
      renderPage()
    }
  }
)


// Drag-to-pan functionality (H key for Hand tool - standard in PDF viewers)
const handleKeyDown = (e: KeyboardEvent) => {
  const target = e.target as HTMLElement | null
  if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) {
    return
  }
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
  if ('ResizeObserver' in window) {
    resizeObserver = new ResizeObserver(() => {
      if (resizeRaf) cancelAnimationFrame(resizeRaf)
      resizeRaf = requestAnimationFrame(() => {
        resizeRaf = 0
        if (fitMode.value === 'width') {
          fitToWidth()
        }
      })
    })
    if (pageContainerRef.value) {
      resizeObserver.observe(pageContainerRef.value)
    }
  }
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
  if (resizeObserver && pageContainerRef.value) {
    resizeObserver.unobserve(pageContainerRef.value)
  }
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
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
        <div class="control-group">
          <button class="nav-btn" @click="prevPage" :disabled="currentPage <= 1" title="Previous page">
            Prev
          </button>
          <div class="page-input">
            <input
              v-model="pageInput"
              type="number"
              min="1"
              :max="totalPages"
              @keydown.enter="goToPage"
              @blur="goToPage"
              aria-label="Page number"
            />
            <span>/ {{ totalPages }}</span>
          </div>
          <button class="nav-btn" @click="nextPage" :disabled="currentPage >= totalPages" title="Next page">
            Next
          </button>
        </div>

        <div class="control-group">
          <button class="zoom-btn" @click="zoomOut" :disabled="scale <= 0.5" title="Zoom out">-</button>
          <label class="zoom-input">
            <input
              v-model="zoomInput"
              type="number"
              min="50"
              max="300"
              step="10"
              @keydown.enter="goToZoom"
              @blur="goToZoom"
              aria-label="Zoom percentage"
            />
            <span>%</span>
          </label>
          <button class="zoom-btn" @click="zoomIn" :disabled="scale >= 3" title="Zoom in">+</button>
          <button class="fit-btn" @click="fitToWidth" :disabled="!totalPages" title="Fit page to width">
            Fit width
          </button>
        </div>

        <div class="control-group end">
          <button
            class="highlight-toggle"
            :class="{ active: highlightEnabled }"
            @click="toggleHighlights"
            :title="highlightEnabled ? 'Hide highlights' : 'Show highlights'"
          >
            Highlights
          </button>
          <div class="keyboard-hint" :class="{ active: isDragMode }">
            <kbd>H</kbd>
            <span v-if="isDragMode">Pan mode active</span>
            <span v-else>Hold to pan</span>
          </div>
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
  background: var(--bg-panel);
  overflow: hidden;
}

.pdf-loading,
.pdf-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-secondary);
}

.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid rgba(255, 255, 255, 0.2);
  border-top-color: var(--text-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.pdf-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px 16px;
  padding: 10px 14px;
  background: var(--bg-panel);
  border-bottom: 1px solid var(--border-color);
  box-shadow: var(--shadow-sm);
  position: sticky;
  top: 0;
  z-index: 5;
}

.pdf-controls button {
  padding: 6px 12px;
  background: var(--color-white);
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  transition: background 0.2s, box-shadow 0.2s, transform 0.2s;
}

.pdf-controls button:hover:not(:disabled) {
  background: var(--bg-card-hover);
  color: var(--text-primary);
  border-color: var(--border-card-hover);
}

.pdf-controls button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  border-color: transparent;
}

.pdf-controls button:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px rgba(var(--accent-color-rgb), 0.2);
}

.control-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.control-group.end {
  margin-left: auto;
}

.page-input {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  border-radius: 6px;
  border: 1px solid var(--border-input);
  background: var(--color-white);
  color: var(--text-secondary);
  font-size: 12px;
}

.page-input input {
  width: 64px;
  border: none;
  background: transparent;
  color: var(--text-primary);
  font-size: 12px;
  text-align: center;
  outline: none;
}

.page-input input:focus {
  outline: none;
}

.zoom-input {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 6px;
  border-radius: 6px;
  border: 1px solid var(--border-input);
  background: var(--color-white);
  color: var(--text-secondary);
  font-size: 12px;
}

.zoom-input input {
  width: 56px;
  border: none;
  background: transparent;
  color: var(--text-primary);
  font-size: 12px;
  text-align: center;
  outline: none;
  font-variant-numeric: tabular-nums;
}

.highlight-toggle {
  padding: 4px 6px;
  border-radius: 4px;
  border: 1px solid var(--border-card);
  background-color: transparent;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.2s, color 0.2s, border-color 0.2s, box-shadow 0.2s;
}

.highlight-toggle:hover {
  background-color: var(--bg-selected);
  border-color: var(--accent-bright);
  color: var(--accent-color);
}

.highlight-toggle.active {
  background-color: var(--bg-selected);
  border-color: var(--accent-bright);
  color: var(--accent-color);
}

.keyboard-hint {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--text-secondary);
  font-size: 12px;
  transition: color 0.2s;
}

.keyboard-hint.active {
  color: var(--accent-color);
}

.keyboard-hint kbd {
  display: inline-block;
  padding: 2px 6px;
  font-family: monospace;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-primary);
  background: var(--bg-button);
  border: 1px solid var(--border-color);
  border-radius: 3px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
  transition: all 0.2s;
}

.keyboard-hint.active kbd {
  background: var(--accent-color);
  border-color: var(--accent-color);
  color: var(--color-white);
  box-shadow: 0 0 8px rgba(var(--accent-color-rgb), 0.25);
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
  padding: 24px;
  background: var(--bg-app);
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
  background: var(--bg-panel);
  border-radius: 10px;
  border: 1px solid var(--border-card);
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

@media (max-width: 720px) {
  .pdf-controls {
    padding: 10px;
  }

  .control-group {
    flex-wrap: wrap;
    justify-content: center;
  }

  .control-group.end {
    width: 100%;
    justify-content: space-between;
  }

  .page-input input {
    width: 54px;
  }

  .keyboard-hint span {
    display: none;
  }
}
</style>

