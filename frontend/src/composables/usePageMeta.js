import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { getPageByPath, NAV_PAGES } from '../constants/navigation'

/** 页面元数据 — 单一来源 navigation.js */
export function usePageMeta(pageId = null) {
  const route = useRoute()
  const pageMeta = computed(() => {
    const hit = getPageByPath(route.path)
    if (hit) return hit
    if (pageId && NAV_PAGES[pageId]) return NAV_PAGES[pageId]
    return { id: 'unknown', label: '页面', subtitle: '', layer: '', layerLabel: '', agent: null }
  })
  return { pageMeta, route }
}
