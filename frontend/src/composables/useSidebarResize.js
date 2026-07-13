import { ref, onMounted, onUnmounted } from 'vue'

const STORAGE_KEY = 'security-agent-sidebar-width'
const DEFAULT = 360
const MIN = 300
const MAX = 520

export function useSidebarResize() {
  const width = ref(DEFAULT)
  const isResizing = ref(false)
  const start = { x: 0, w: DEFAULT }

  function loadWidth() {
    const raw = Number(localStorage.getItem(STORAGE_KEY))
    if (raw >= MIN && raw <= MAX) width.value = raw
    document.documentElement.style.setProperty('--sidebar-width', `${width.value}px`)
  }

  function saveWidth() {
    localStorage.setItem(STORAGE_KEY, String(width.value))
    document.documentElement.style.setProperty('--sidebar-width', `${width.value}px`)
  }

  function onPointerMove(e) {
    if (!isResizing.value) return
    const next = Math.min(MAX, Math.max(MIN, start.w + (e.clientX - start.x)))
    width.value = next
    document.documentElement.style.setProperty('--sidebar-width', `${next}px`)
  }

  function stopResize() {
    if (!isResizing.value) return
    isResizing.value = false
    saveWidth()
    document.body.classList.remove('sidebar-resizing')
    window.removeEventListener('pointermove', onPointerMove)
    window.removeEventListener('pointerup', stopResize)
  }

  function startResize(e) {
    e.preventDefault()
    e.stopPropagation?.()
    start.x = e.clientX
    start.w = width.value
    isResizing.value = true
    document.body.classList.add('sidebar-resizing')
    try { e.currentTarget?.setPointerCapture?.(e.pointerId) } catch {}
    window.addEventListener('pointermove', onPointerMove)
    window.addEventListener('pointerup', stopResize)
  }

  onMounted(loadWidth)
  onUnmounted(stopResize)

  return { width, isResizing, startResize, loadWidth }
}
