import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../api'

export const useEvalStore = defineStore('eval', () => {
  const score = ref(null)
  const loading = ref(false)
  const lastFetch = ref(0)
  let inflight = null

  async function fetchScore({ force = false, maxAgeMs = 15000 } = {}) {
    const stale = maxAgeMs > 0 && Date.now() - lastFetch.value > maxAgeMs
    if (!force && score.value && !stale) return score.value
    if (inflight) return inflight

    loading.value = true
    inflight = api.get('/eval/score')
      .then(res => {
        score.value = res
        lastFetch.value = Date.now()
        return res
      })
      .finally(() => {
        loading.value = false
        inflight = null
      })
    return inflight
  }

  return { score, loading, lastFetch, fetchScore }
})
