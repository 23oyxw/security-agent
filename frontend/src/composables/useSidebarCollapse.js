import { ref, onMounted, onUnmounted } from 'vue'

const STORAGE_KEY = 'security-agent-sidebar-collapsed'
const NARROW_MQ = '(max-width: 900px)'

export function useSidebarCollapse() {
  const collapsed = ref(localStorage.getItem(STORAGE_KEY) === '1')
  const isNarrow = ref(false)
  let mq = null
  let onChange = null

  function setCollapsed(v) {
    collapsed.value = v
    localStorage.setItem(STORAGE_KEY, v ? '1' : '0')
  }

  function toggle() {
    setCollapsed(!collapsed.value)
  }

  onMounted(() => {
    mq = window.matchMedia(NARROW_MQ)
    onChange = () => {
      isNarrow.value = mq.matches
      if (mq.matches) setCollapsed(true)
    }
    onChange()
    mq.addEventListener('change', onChange)
  })

  onUnmounted(() => {
    if (mq && onChange) mq.removeEventListener('change', onChange)
  })

  return { collapsed, isNarrow, toggle, setCollapsed }
}
