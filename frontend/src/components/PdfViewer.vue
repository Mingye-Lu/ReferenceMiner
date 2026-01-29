<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick, computed, onBeforeUnmount } from 'vue'
import * as pdfjsLib from 'pdfjs-dist'
import type { HighlightGroup } from '../types'
import { usePdfSettings } from '../composables/usePdfSettings'

// Setup PDF.js worker
pdfjsLib.GlobalWorkerOptions.workerSrc = '/pdf.worker.mjs'

const props = defineProps<{
  fileUrl: string
  highlightGroups?: HighlightGroup[]
  initialPage?: number
}>()

const emit = defineEmits<{
  (event: 'progress', percent: number): void
}>()

const canvasRef = ref<HTMLCanvasElement>()
const overlayRef = ref<HTMLDivElement>()
const containerRef = ref<HTMLDivElement>()
const pageContainerRef = ref<HTMLDivElement>()
const currentPage = ref(1)
const totalPages = ref(0)
const isLoading = ref(true)
const error = ref<string>()
const scale = ref(1.0)
const highlightEnabled = ref(true)
const pageInput = ref('1')
const fitMode = ref<'custom' | 'width'>('custom')
const zoomInput = ref('100')

let pdfDoc: pdfjsLib.PDFDocumentProxy | null = null
let renderTask: pdfjsLib.RenderTask | null = null
let renderSeq = 0
let lastViewport: any = null
let lastPageNumber = 0
let shouldAutoScroll = false
let resizeObserver: ResizeObserver | null = null
let resizeRaf = 0
const { settings: pdfSettings } = usePdfSettings()
const viewMode = computed(() => pdfSettings.value.viewMode)

// Continuous scroll state
const pageRefs = ref<(HTMLElement | null)[]>([])
const visiblePages = ref<Set<number>>(new Set())
let pageObserver: IntersectionObserver | null = null
// Map of page number -> render task mainly for continuous mode cancellation
const renderTasks = new Map<number, pdfjsLib.RenderTask>()

// Read highlight palette from CSS variables for consistency with design system
const getHighlightPalette = () => {
  const style = getComputedStyle(document.documentElement)
  return [
    style.getPropertyValue('--color-highlight-amber').trim() || '#F59E0B',
    style.getPropertyValue('--color-highlight-emerald').trim() || '#10B981',
    style.getPropertyValue('--color-highlight-blue').trim() || '#3B82F6',
    style.getPropertyValue('--color-highlight-red').trim() || '#EF4444',
    style.getPropertyValue('--color-highlight-violet').trim() || '#8B5CF6',
    style.getPropertyValue('--color-highlight-teal').trim() || '#14B8A6',
    style.getPropertyValue('--color-highlight-rose').trim() || '#E11D48',
    style.getPropertyValue('--color-highlight-indigo').trim() || '#6366F1',
  ]
}

const highlightPalette = computed(() => getHighlightPalette())

const hasHighlights = computed(() => {
  return (props.highlightGroups?.length ?? 0) > 0
})

const normalizedGroups = computed<HighlightGroup[]>(() => {
  return props.highlightGroups ?? []
})

// Page progress percentage
const progressPercent = computed(() => {
  if (totalPages.value === 0) return 0
  return (currentPage.value / totalPages.value) * 100
})

// Emit progress to parent
watch(progressPercent, (percent) => {
  emit('progress', percent)
})

// Drag-to-pan state
const isDragMode = ref(false)
const isDragging = ref(false)
let dragStartX = 0
let dragStartY = 0
let scrollStartX = 0
let scrollStartY = 0

// Hold-to-zoom state
const isZoomMode = ref(false)

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
    await nextTick()
    if (viewMode.value === 'continuous') {
      setupObserver()
      const el = pageRefs.value[currentPage.value - 1]
      if (el) el.scrollIntoView({ block: 'start' })
    } else {
      await renderPage()
    }
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

    const canvas = viewMode.value === 'single' ? canvasRef.value : (pageRefs.value[currentPage.value - 1]?.querySelector('canvas') as HTMLCanvasElement)
    const overlay = viewMode.value === 'single' ? overlayRef.value : (pageRefs.value[currentPage.value - 1]?.querySelector('.pdf-overlay') as HTMLDivElement)
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

// Continuous mode rendering
const renderSpecificPage = async (pageNum: number) => {
  if (!pdfDoc) return

  const pageEl = pageRefs.value[pageNum - 1]
  if (!pageEl) return

  const canvas = pageEl.querySelector('canvas') as HTMLCanvasElement
  const overlay = pageEl.querySelector('.pdf-overlay') as HTMLElement
  if (!canvas || !overlay) return

  // Skip if already rendered with same scale (simple check, can be improved)
  if (canvas.hasAttribute('data-rendered-scale') &&
    canvas.getAttribute('data-rendered-scale') === String(scale.value)) {
    return
  }

  try {
    // Cancel existing task for this page if any
    if (renderTasks.has(pageNum)) {
      renderTasks.get(pageNum)?.cancel()
      renderTasks.delete(pageNum)
    }

    const page = await pdfDoc.getPage(pageNum)
    const viewport = page.getViewport({ scale: scale.value })

    // Resize canvas
    canvas.height = viewport.height
    canvas.width = viewport.width
    // Resize overlay
    overlay.style.width = `${viewport.width}px`
    overlay.style.height = `${viewport.height}px`

    const context = canvas.getContext('2d')
    if (!context) return

    const renderContext = {
      canvasContext: context,
      viewport: viewport,
      canvas, // Include canvas to satisfy type requirements if needed
    }

    const task = page.render(renderContext)
    renderTasks.set(pageNum, task)

    await task.promise
    renderTasks.delete(pageNum)

    canvas.setAttribute('data-rendered-scale', String(scale.value))

    // Render highlights for this page
    renderHighlightsForPage(viewport, pageNum, overlay)

  } catch (err: any) {
    if (err?.name !== 'RenderingCancelledException') {
      console.error(`Error rendering page ${pageNum}:`, err)
    }
  }
}

const renderHighlightsForPage = (viewport: any, pageNum: number, overlay: HTMLElement) => {
  overlay.innerHTML = ''
  if (!highlightEnabled.value || !hasHighlights.value) return

  const groups = normalizedGroups.value
  const pdfHeight = (viewport.viewBox?.[3] ?? 0) - (viewport.viewBox?.[1] ?? 0)

  groups.forEach((group, groupIndex) => {
    // Determine color from palette
    const color = group.color || colorForGroup(group, groupIndex)
    const border = color
    const background = toAlpha(color, 0.35)

    group.boxes.forEach(box => {
      // Filter strictly by page
      if (box.page !== pageNum) return

      const rect = document.createElement('div')
      rect.className = 'pdf-highlight'

      // Use same coordinate conversion as renderHighlights
      const [x0, y0, x1, y1] = viewport.convertToViewportRectangle([
        box.x0,
        pdfHeight - box.y1,
        box.x1,
        pdfHeight - box.y0,
      ])

      const left = Math.min(x0, x1)
      const top = Math.min(y0, y1)
      const width = Math.abs(x1 - x0)
      const height = Math.abs(y1 - y0)

      rect.style.position = 'absolute'
      rect.style.left = `${left}px`
      rect.style.top = `${top}px`
      rect.style.width = `${width}px`
      rect.style.height = `${height}px`
      rect.style.background = background
      rect.style.border = `1px solid ${border}`
      rect.style.pointerEvents = 'none'

      overlay.appendChild(rect)
    })
  })
}

// Setup IntersectionObserver for continuous mode
const setupObserver = () => {
  if (pageObserver) pageObserver.disconnect()

  visiblePages.value.clear()

  pageObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      const pageNum = parseInt((entry.target as HTMLElement).dataset.page || '0')
      if (!pageNum) return

      if (entry.isIntersecting) {
        visiblePages.value.add(pageNum)
        renderSpecificPage(pageNum)
      } else {
        visiblePages.value.delete(pageNum)
        // Optional: clear canvas to save memory if very far off screen?
        // For now, keep rendered to avoid flickering when scrolling back
      }
    })

    // Update current page to the most visible one
    updateCurrentPageFromScroll()
  }, {
    root: pageContainerRef.value,
    threshold: [0.1, 0.5]
  })

  // Observe all pages
  nextTick(() => {
    pageRefs.value.forEach(el => {
      if (el) pageObserver?.observe(el)
    })
  })
}

const updateCurrentPageFromScroll = () => {
  // Find the page closest to center or top
  // Simple heuristic: min page number in visible set, or sort by intersection ratio if available
  if (visiblePages.value.size === 0) return

  const sorted = Array.from(visiblePages.value).sort((a, b) => a - b)
  // Prefer the middle-ish page if multiple are visible, or just the first fully visible one.
  // Let's just take the first one for simplicity, or we can improve logic.
  // If we are scrolling down, the bottom page enters. If we scroll up, top enters.
  // A robust way is to check element positions relative to container.
  // For now: just take the smallest page number visible (top-most in view).
  const topMost = sorted[0]
  if (topMost !== currentPage.value) {
    currentPage.value = topMost
    pageInput.value = String(topMost)
  }
}

watch(viewMode, async (newMode) => {
  // Reset state when switching modes
  if (newMode === 'continuous') {
    await nextTick()
    setupObserver()
    // Scroll to current page
    const el = pageRefs.value[currentPage.value - 1]
    el?.scrollIntoView({ block: 'start' })
  } else {
    if (pageObserver) {
      pageObserver.disconnect()
      pageObserver = null
    }
    await nextTick()
    renderPage()
  }
})

onBeforeUnmount(() => {
  if (pageObserver) pageObserver.disconnect()
  renderTasks.forEach(task => task.cancel())
})

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
  const palette = highlightPalette.value
  const id = group.id || ''
  if (id) {
    let hash = 0
    for (let i = 0; i < id.length; i++) {
      hash = (hash * 31 + id.charCodeAt(i)) >>> 0
    }
    return palette[hash % palette.length]
  }
  return palette[index % palette.length]
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
  if (viewMode.value === 'continuous') {
    rerenderVisiblePages()
  } else {
    renderPage()
  }
}

const rerenderVisiblePages = () => {
  // Clear rendered scale attribute to force re-render
  pageRefs.value.forEach((el) => {
    const canvas = el?.querySelector('canvas')
    if (canvas) {
      canvas.removeAttribute('data-rendered-scale')
    }
  })
  // Re-render currently visible pages
  visiblePages.value.forEach(pageNum => {
    renderSpecificPage(pageNum)
  })
}



const zoomIn = () => {
  applyScale(scale.value + 0.25)
}

const zoomOut = () => {
  applyScale(scale.value - 0.25)
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
  if (viewMode.value === 'continuous') {
    rerenderVisiblePages()
  } else {
    renderPage()
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

const toggleHighlights = () => {
  highlightEnabled.value = !highlightEnabled.value
  if (lastViewport) {
    renderHighlights(lastViewport, lastPageNumber)
  } else {
    renderPage()
  }
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
// Hold-to-zoom functionality (Z key for zoom mode)
// Arrow keys for page navigation
const handleKeyDown = (e: KeyboardEvent) => {
  const target = e.target as HTMLElement | null
  if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) {
    return
  }

  // H key for pan mode
  if (e.key === 'h' && !isDragMode.value && pageContainerRef.value) {
    isDragMode.value = true
  }

  // Z key for zoom mode
  if (e.key === 'z' && !isZoomMode.value && pageContainerRef.value) {
    isZoomMode.value = true
  }

  // Arrow keys for page navigation
  if (e.key === 'ArrowLeft') {
    prevPage()
    e.preventDefault()
  } else if (e.key === 'ArrowRight') {
    nextPage()
    e.preventDefault()
  } else if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
    // Allow native scroll
  }
}


const scrollToPage = (pageNum: number) => {
  if (viewMode.value === 'single') {
    currentPage.value = pageNum
    renderPage()
  } else {
    // Continuous: just scroll to it
    currentPage.value = pageNum
    const el = pageRefs.value[pageNum - 1]
    el?.scrollIntoView({ block: 'start' })
  }
}

const goToPage = () => {
  let p = parseInt(pageInput.value)
  if (isNaN(p)) return
  if (p < 1) p = 1
  if (p > totalPages.value) p = totalPages.value

  scrollToPage(p)
  pageInput.value = String(p)
}

const prevPage = () => {
  if (currentPage.value > 1) {
    scrollToPage(currentPage.value - 1)
  }
}

const nextPage = () => {
  if (currentPage.value < totalPages.value) {
    scrollToPage(currentPage.value + 1)
  }
}

const handleKeyUp = (e: KeyboardEvent) => {
  if (e.key === 'h') {
    isDragMode.value = false
    isDragging.value = false
  }
  if (e.key === 'z') {
    isZoomMode.value = false
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

const handleWheel = (e: WheelEvent) => {
  if (!isZoomMode.value || !pageContainerRef.value) return

  e.preventDefault()

  const container = pageContainerRef.value
  const rect = container.getBoundingClientRect()

  // Get mouse position relative to container
  const mouseX = e.clientX - rect.left
  const mouseY = e.clientY - rect.top

  // Get current scroll position
  const scrollLeft = container.scrollLeft
  const scrollTop = container.scrollTop

  // Calculate zoom factor (scroll up = zoom in, scroll down = zoom out)
  const zoomFactor = e.deltaY > 0 ? 0.9 : 1.1
  const oldScale = scale.value
  const newScale = clamp(oldScale * zoomFactor, 0.5, 3)

  if (newScale === oldScale) return

  // Calculate the point relative to the viewport (in document coordinates)
  const pointX = mouseX + scrollLeft
  const pointY = mouseY + scrollTop

  // Apply new scale
  scale.value = newScale
  zoomInput.value = `${Math.round(scale.value * 100)}`
  fitMode.value = 'custom'

  // Re-render pages
  if (viewMode.value === 'continuous') {
    rerenderVisiblePages()
  } else {
    renderPage()
  }

  // After rendering, adjust scroll to keep the mouse point centered
  nextTick(() => {
    const newScrollLeft = pointX * (newScale / oldScale) - mouseX
    const newScrollTop = pointY * (newScale / oldScale) - mouseY

    container.scrollLeft = newScrollLeft
    container.scrollTop = newScrollTop
  })
}

onMounted(() => {
  loadPdf()
  window.addEventListener('keydown', handleKeyDown)
  window.addEventListener('keyup', handleKeyUp)
  window.addEventListener('mouseup', handleMouseUp)
  window.addEventListener('wheel', handleWheel, { passive: false })
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
    pdfDoc.destroy().catch(() => { })
    pdfDoc = null
  }
  window.removeEventListener('keydown', handleKeyDown)
  window.removeEventListener('keyup', handleKeyUp)
  window.removeEventListener('mouseup', handleMouseUp)
  window.removeEventListener('wheel', handleWheel)
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
  <div ref="containerRef" class="pdf-viewer" :style="{ '--pdf-progress': progressPercent + '%' }">
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
          <button class="nav-btn" @click="prevPage" :disabled="currentPage <= 1" title="Previous page (←)">
            Prev
          </button>
          <div class="page-input">
            <input v-model="pageInput" type="number" min="1" :max="totalPages" @keydown.enter="goToPage"
              @blur="goToPage" aria-label="Page number" />
            <span class="separator">/</span>
            <span class="total">{{ totalPages }}</span>
          </div>
          <button class="nav-btn" @click="nextPage" :disabled="currentPage >= totalPages" title="Next page (→)">
            Next
          </button>
        </div>

        <div class="control-group">
          <button class="nav-btn" @click="zoomOut" :disabled="scale <= 0.5" title="Zoom out">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="11" cy="11" r="8"></circle>
              <path d="m21 21-4.35-4.35"></path>
              <line x1="8" y1="11" x2="14" y2="11"></line>
            </svg>
          </button>
          <label class="zoom-input">
            <input v-model="zoomInput" type="number" min="50" max="300" step="10" @keydown.enter="goToZoom"
              @blur="goToZoom" aria-label="Zoom percentage" />
            <span>%</span>
          </label>
          <button class="nav-btn" @click="zoomIn" :disabled="scale >= 3" title="Zoom in">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="11" cy="11" r="8"></circle>
              <path d="m21 21-4.35-4.35"></path>
              <line x1="11" y1="8" x2="11" y2="14"></line>
              <line x1="8" y1="11" x2="14" y2="11"></line>
            </svg>
          </button>
          <button class="nav-btn" @click="fitToWidth" :disabled="!totalPages" title="Fit page to width">
            Fit width
          </button>
        </div>

        <div class="control-group end">
          <button class="highlight-toggle" :class="{ active: highlightEnabled }" @click="toggleHighlights"
            :title="highlightEnabled ? 'Hide highlights' : 'Show highlights'">
            Highlights
          </button>
          <div class="keyboard-hint" :class="{ active: isDragMode }">
            <kbd>H</kbd>
            <span v-if="isDragMode">Pan mode</span>
            <span v-else>Hold to pan</span>
          </div>
          <div class="keyboard-hint" :class="{ active: isZoomMode }">
            <kbd>Z</kbd>
            <span v-if="isZoomMode">Zoom mode</span>
            <span v-else>Hold to zoom</span>
          </div>
        </div>

        <!-- Progress Bar (Sticky with controls) -->
        <div class="pdf-progress-bar"></div>
      </div>

      <div ref="pageContainerRef" class="pdf-page-container"
        :class="{ 'drag-mode': isDragMode, 'dragging': isDragging, 'continuous-mode': viewMode === 'continuous' }"
        @mousedown="handleMouseDown" @mousemove="handleMouseMove" @scroll="viewMode === 'continuous' ? null : null">
        <!-- Scroll listener can be handled by observer in continuous -->

        <!-- Single Page View -->
        <div v-if="viewMode === 'single'" class="pdf-canvas-wrapper">
          <canvas ref="canvasRef"></canvas>
          <div ref="overlayRef" class="pdf-overlay"></div>
        </div>

        <!-- Continuous View -->
        <div v-else class="pdf-continuous-list">
          <div v-for="page in totalPages" :key="page" ref="pageRefs" class="pdf-page-wrapper" :data-page="page"
            :style="{ minHeight: '800px', marginBottom: '16px' }">
            <!-- Height placeholder until loaded? Ideally we know aspect ratio. 
                      For now just a min-height. Once rendered it snaps to size. 
                      Better to have a loader or static size if possible. -->
            <div class="pdf-canvas-wrapper">
              <canvas></canvas>
              <div class="pdf-overlay"></div>
            </div>

          </div>
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
  min-height: 0;
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
  to {
    transform: rotate(360deg);
  }
}

.pdf-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px 16px;
  padding: 10px 14px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-card);
  box-shadow: 0 2px 8px var(--alpha-black-05);
  position: sticky;
  top: 0;
  z-index: 5;
}

/* Dark mode controls */
[data-theme="dark"] .pdf-controls {
  background: var(--color-neutral-900);
  border-bottom-color: var(--color-neutral-800);
  box-shadow: 0 2px 12px var(--alpha-black-20);
}



/* Control groups with visual separation */
.control-group {
  display: flex;
  align-items: center;
  gap: 4px;
  background: var(--color-neutral-100);
  padding: 4px;
  border-radius: 8px;
}

[data-theme="dark"] .control-group {
  background: var(--color-neutral-850);
}

.control-group.end {
  margin-left: auto;
  background: transparent;
  padding: 0;
  gap: 8px;
}

/* Icon buttons (zoom +/-) */


/* Page indicator with progress bar */
.page-indicator-wrapper {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.page-input {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  border-radius: 6px;
  border: 1px solid var(--border-card);
  background: transparent;
  color: var(--text-secondary);
  font-size: 12px;
  transition: all 0.2s;
}

.page-input:hover {
  border-color: var(--border-card-hover);
  background: var(--bg-card-hover);
}

.page-input:focus-within {
  border-color: var(--accent-color);
  background: var(--bg-card);
  box-shadow: 0 0 0 3px var(--accent-soft);
}

[data-theme="dark"] .page-input {
  background: var(--color-neutral-800);
  border-color: var(--color-neutral-700);
}

[data-theme="dark"] .page-input:hover {
  background: var(--color-neutral-750);
  border-color: var(--color-neutral-600);
}

[data-theme="dark"] .page-input:focus-within {
  background: var(--color-neutral-750);
  box-shadow: 0 0 0 3px rgba(var(--accent-color-rgb), 0.2);
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

[data-theme="dark"] .page-input input {
  color: var(--text-primary);
}

.page-input .separator {
  color: var(--text-secondary);
}

.page-input .total {
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

/* Hide input number arrows */
.page-input input::-webkit-outer-spin-button,
.page-input input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.page-input input[type=number] {
  -moz-appearance: textfield;
  appearance: textfield;
}

/* Page progress bar */
.page-progress-bar {
  position: absolute;
  bottom: -2px;
  left: 0;
  right: 0;
  height: 2px;
  background: var(--color-neutral-200);
  border-radius: 1px;
  overflow: hidden;
}

[data-theme="dark"] .page-progress-bar {
  background: var(--color-neutral-700);
}

.page-progress-fill {
  height: 100%;
  background: var(--accent-color);
  transition: width 0.3s ease;
  border-radius: 1px;
}

/* Zoom input */
.zoom-input {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 6px;
  border-radius: 6px;
  border: 1px solid var(--border-card);
  background: transparent;
  color: var(--text-secondary);
  font-size: 12px;
  transition: all 0.2s;
}

.zoom-input:hover {
  border-color: var(--border-card-hover);
  background: var(--bg-card-hover);
}

.zoom-input:focus-within {
  border-color: var(--accent-color);
  background: var(--bg-card);
  box-shadow: 0 0 0 3px var(--accent-soft);
}

[data-theme="dark"] .zoom-input {
  background: var(--color-neutral-800);
  border-color: var(--color-neutral-700);
}

[data-theme="dark"] .zoom-input:hover {
  background: var(--color-neutral-750);
  border-color: var(--color-neutral-600);
}

[data-theme="dark"] .zoom-input:focus-within {
  background: var(--color-neutral-750);
  box-shadow: 0 0 0 3px rgba(var(--accent-color-rgb), 0.2);
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

[data-theme="dark"] .zoom-input input {
  color: var(--text-primary);
}

/* Hide input number arrows */
.zoom-input input::-webkit-outer-spin-button,
.zoom-input input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.zoom-input input[type=number] {
  -moz-appearance: textfield;
  appearance: textfield;
}


/* Highlight toggle button */
.highlight-toggle {
  padding: 6px 12px;
  border-radius: 6px;
  border: 1px solid var(--border-card);
  background: transparent;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.highlight-toggle.active {
  background: var(--accent-soft);
  border-color: var(--accent-color);
  color: var(--accent-color);
  box-shadow: 0 0 0 1px var(--accent-soft);
}

[data-theme="dark"] .highlight-toggle.active {
  background: rgba(var(--accent-color-rgb), 0.15);
  border-color: var(--accent-bright);
  color: var(--accent-bright);
}

.highlight-toggle:not(.active):hover {
  background: var(--bg-card-hover);
  border-color: var(--border-card-hover);
  color: var(--text-primary);
}

/* Keyboard hint */
.keyboard-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  background: var(--color-neutral-100);
  border-radius: 6px;
  color: var(--text-secondary);
  font-size: 12px;
  transition: all 0.2s;
}

[data-theme="dark"] .keyboard-hint {
  background: var(--color-neutral-850);
}

.keyboard-hint.active {
  color: var(--accent-color);
  background: var(--accent-soft);
}

[data-theme="dark"] .keyboard-hint.active {
  background: rgba(var(--accent-color-rgb), 0.15);
  color: var(--accent-bright);
}

.keyboard-hint kbd {
  display: inline-block;
  padding: 3px 7px;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  color: var(--text-primary);
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: 4px;
  box-shadow: 0 1px 3px var(--alpha-black-10);
  transition: all 0.2s;
}

[data-theme="dark"] .keyboard-hint kbd {
  background: var(--color-neutral-700);
  border-color: var(--color-neutral-600);
  color: var(--color-neutral-100);
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
  min-height: 0;
}

.pdf-page-container {
  flex: 1;
  overflow: auto;
  padding: 12px;
  background: var(--bg-app);
  position: relative;
  min-height: 0;
}

/* PDF progress bar */
.pdf-progress-bar {
  position: absolute;
  bottom: 0;
  left: 0;
  height: 3px;
  width: var(--pdf-progress, 0%);
  background: var(--accent-color);
  z-index: 10;
  transition: width 0.3s ease;
  pointer-events: none;
}

[data-theme="dark"] .pdf-progress-bar {
  background: var(--accent-bright);
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

/* Improve dark mode text contrast */
[data-theme="dark"] .pdf-controls {
  color: var(--color-neutral-200);
}





[data-theme="dark"] .page-input .separator,
[data-theme="dark"] .page-input .total,
[data-theme="dark"] .zoom-input span {
  color: var(--color-neutral-400);
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
