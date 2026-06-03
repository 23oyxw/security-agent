/** 共享知识库检索 composable — 消除 Executor/SafetyGate 之间 ~50 行重复代码 */
import { ref, onMounted } from 'vue'
import api from '../api'
import { sevTypeCN } from '../utils/severity'

export function useKnowledgeSearch(options = {}) {
  const { limit = 20, endpoint = '/safety/knowledge/search', tagsEndpoint = '/safety/knowledge/tags' } = options

  const query = ref('')
  const activeTag = ref('')
  const results = ref([])
  const tags = ref([])
  const total = ref(0)
  const loading = ref(false)
  const searched = ref(false)
  const detailItem = ref(null)

  function sevType(s) { return sevTypeCN(s) }

  async function loadTags() {
    try {
      const data = await api.get(tagsEndpoint)
      tags.value = data.tags || []
    } catch { tags.value = [] }
  }

  async function search() {
    loading.value = true
    searched.value = true
    try {
      const params = { q: query.value, tag: activeTag.value, limit }
      const data = await api.get(endpoint, { params })
      results.value = data.items || []
      total.value = data.total || 0
    } catch {
      results.value = []
    } finally {
      loading.value = false
    }
  }

  function toggleTag(name) {
    activeTag.value = activeTag.value === name ? '' : name
    search()
  }

  function toggleDetail(item) {
    detailItem.value = detailItem.value?.id === item.id ? null : item
  }

  function clearSearch() {
    query.value = ''
    activeTag.value = ''
    results.value = []
    searched.value = false
    detailItem.value = null
  }

  onMounted(loadTags)

  return {
    query, activeTag, results, tags, total, loading, searched, detailItem,
    sevType, loadTags, search, toggleTag, toggleDetail, clearSearch,
  }
}
