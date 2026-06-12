import api from './index'

/** 编排助手：串联三智能体 */
export function orchestrate(message, { batchId, autoExecute = false, userConfirmed = false } = {}) {
  return api.post('/agent/orchestrate', {
    message,
    batch_id: batchId,
    auto_execute: autoExecute,
    user_confirmed: userConfirmed,
  })
}

/** L1 计划感知 */
export function createPlan(message, batchId = null) {
  return api.post('/agent/plan', { message, batch_id: batchId })
}

/** L2 安全预检 */
export function precheckL2(planId) {
  return api.post('/agent/l2/precheck', { plan_id: planId })
}

/** 执行分发智能体 */
export function executePlan(planId, { sessionId, userConfirmed = false } = {}) {
  return api.post('/agent/execute', {
    plan_id: planId,
    session_id: sessionId,
    user_confirmed: userConfirmed,
  })
}

export function getPlan(planId) {
  return api.get(`/agent/plan/${planId}`)
}

export function chatDirect(message, sessionId) {
  return api.post('/agent/chat', { message, session_id: sessionId, stream: false })
}
