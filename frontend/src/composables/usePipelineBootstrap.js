import { watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAgentStore } from '../stores/agent'

export function usePipelineBootstrap() {
  const route = useRoute()
  const agentStore = useAgentStore()

  async function bootstrapFromRoute() {
    const planId = route.query.plan_id
    if (!planId) return
    if (agentStore.currentPlan?.plan_id === planId) return
    await agentStore.hydrateFromPlan(String(planId))
  }

  watch(
    () => route.query.plan_id,
    id => {
      if (id) bootstrapFromRoute()
    },
    { immediate: true },
  )

  return { bootstrapFromRoute }
}
