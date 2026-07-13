/**
 * 跨页流水线上下文 — plan_id / trace 随导航传递
 */

export function activeTraceId(agentStore) {
  return agentStore.lastAudit?.trace_id
    || agentStore.lastExecute?.trace_id
    || agentStore.currentPlan?.trace_id
    || ''
}

/** L4 ?id= 与 L5 ?trace= 统一解析 */
export function resolveTraceId(route, agentStore) {
  const q = route?.query || {}
  const fromQuery = q.trace || q.id
  if (fromQuery) return String(fromQuery)
  return activeTraceId(agentStore) || ''
}

export function traceQuery(traceId, agentStore) {
  const tid = traceId || activeTraceId(agentStore)
  if (!tid) return {}
  return { id: tid, trace: tid }
}

export function activePlanId(agentStore) {
  return agentStore.currentPlan?.plan_id || ''
}

export function buildAgentQuery(agentStore, extra = {}) {
  const q = { ...extra }
  const planId = activePlanId(agentStore)
  const trace = activeTraceId(agentStore)
  if (planId) q.plan_id = planId
  if (trace) q.trace = trace
  return q
}

export function buildSafetyQuery(agentStore) {
  const plan = agentStore.currentPlan
  if (!plan) return {}
  const cmd = plan.message || plan.user_message_resolved || ''
  return {
    plan_id: plan.plan_id,
    cmd,
    intent: plan.message || cmd,
    trace: plan.trace_id || '',
  }
}

export function buildTraceQuery(agentStore, traceId) {
  return traceQuery(traceId, agentStore)
}

export function buildL5Query(agentStore, traceId) {
  return traceQuery(traceId, agentStore)
}
