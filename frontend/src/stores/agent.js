import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { orchestrate, executePlan } from '../api/agent'
import { defaultAgentStages, mergeAgentStages, ORCHESTRATOR } from '../constants/agents'

let _batchSeq = 0

export const useAgentStore = defineStore('agent', () => {
  const mode = ref('plan')
  const currentPlan = ref(null)
  const l2Result = ref(null)
  const agentStages = ref(defaultAgentStages())
  const batchQueue = ref([])
  const sessionId = ref(null)
  const lastExecute = ref(null)
  const lastAudit = ref(null)
  const dispatchPhase = ref('idle')

  const canExecute = computed(() => {
    if (!currentPlan.value) return false
    const v = l2Result.value?.verdict || currentPlan.value.l2_verdict
    return v === 'pass' || v === 'confirm'
  })

  const needsConfirm = computed(() => {
    const v = l2Result.value?.verdict || currentPlan.value?.l2_verdict
    return Boolean(currentPlan.value?.requires_confirm) || v === 'confirm'
  })

  const isBlocked = computed(() => {
    const v = l2Result.value?.verdict || currentPlan.value?.l2_verdict
    return v === 'deny'
  })

  function setMode(m) {
    mode.value = m
  }

  function resetAgents() {
    agentStages.value = defaultAgentStages()
    dispatchPhase.value = 'idle'
  }

  function resetPlan() {
    currentPlan.value = null
    l2Result.value = null
    lastExecute.value = null
    lastAudit.value = null
    resetAgents()
  }

  async function analyze(message, { batchId = null, autoExecute = false, userConfirmed = false } = {}) {
    resetAgents()
    dispatchPhase.value = 'analyze'
    agentStages.value[0].status = 'running'
    agentStages.value[0].detail = 'L1 analyze 阶段锁'

    const res = await orchestrate(message, {
      batchId,
      autoExecute: autoExecute && mode.value === 'execute',
      userConfirmed,
    })

    currentPlan.value = res.plan
    l2Result.value = res.l2
    sessionId.value = res.plan.trace_id
    agentStages.value = mergeAgentStages(res.agents)
    dispatchPhase.value = res.execute ? 'executed' : 'analyzed'

    if (res.execute) {
      lastExecute.value = res.execute
      lastAudit.value = res.audit || res.execute.audit || null
    }
    return res
  }

  async function runExecute({ userConfirmed = false } = {}) {
    if (!currentPlan.value?.plan_id) throw new Error('请先在计划模式完成 L1 分析')
    if (isBlocked.value) throw new Error('L2 安全防护已拒绝')
    if (needsConfirm.value && !userConfirmed) throw new Error('需二次确认后再执行')

    dispatchPhase.value = 'execute'
    agentStages.value[0].status = 'running'
    agentStages.value[0].detail = 'L3 execute 阶段锁'
    agentStages.value[2].status = 'idle'
    agentStages.value[2].detail = '等待执行完成'

    try {
      const res = await executePlan(currentPlan.value.plan_id, {
        sessionId: sessionId.value,
        userConfirmed,
      })
      lastExecute.value = res
      lastAudit.value = res.audit || null
      agentStages.value[0].status = 'done'
      agentStages.value[0].detail = 'L3 execute 完成'
      if (lastAudit.value) {
        agentStages.value[2].status = 'done'
        agentStages.value[2].detail = `审计 ${String(lastAudit.value.trace_id || '').slice(0, 8)}`
      }
      dispatchPhase.value = 'executed'
      return res
    } catch (e) {
      agentStages.value[0].status = 'error'
      agentStages.value[0].detail = e.response?.data?.detail || e.message
      throw e
    }
  }

  /** L3 执行 → L4 审计 → L5 就绪（需 plan + L2 通过） */
  async function runPipelineToEnd({ userConfirmed = false } = {}) {
    if (!currentPlan.value?.plan_id) throw new Error('请先在计划模式完成 L1 分析')
    if (isBlocked.value) throw new Error('L2 安全防护已拒绝')
    if (needsConfirm.value && !userConfirmed) throw new Error('需二次确认后再执行')
    return runExecute({ userConfirmed })
  }

  function addBatchLines(text) {
    const lines = text.split('\n').map(l => l.trim()).filter(Boolean)
    const batchId = `batch-${Date.now()}`
    for (const line of lines) {
      batchQueue.value.push({
        id: `q-${++_batchSeq}`,
        batchId,
        message: line,
        status: 'queued',
        planId: null,
        error: null,
      })
    }
    return batchId
  }

  async function processBatchQueue(onProgress) {
    for (const item of batchQueue.value) {
      if (item.status !== 'queued') continue
      item.status = 'analyzing'
      onProgress?.(item)
      try {
        const res = await analyze(item.message, { batchId: item.batchId })
        item.planId = res.plan.plan_id
        if (res.l2.verdict === 'deny') {
          item.status = 'blocked'
          continue
        }
        item.status = 'awaiting_approval'
        onProgress?.(item)
        if (res.l2.verdict === 'pass' && !res.plan.requires_confirm) {
          item.status = 'executing'
          onProgress?.(item)
          setMode('execute')
          await runExecute({ userConfirmed: true })
          item.status = 'done'
        }
      } catch (e) {
        item.status = 'failed'
        item.error = e.response?.data?.detail || e.message
      }
      onProgress?.(item)
    }
  }

  function clearBatch() {
    batchQueue.value = []
  }

  return {
    mode,
    modes: ORCHESTRATOR.modes,
    currentPlan,
    l2Result,
    agentStages,
    batchQueue,
    sessionId,
    lastExecute,
    lastAudit,
    dispatchPhase,
    canExecute,
    needsConfirm,
    isBlocked,
    setMode,
    resetPlan,
    analyze,
    runExecute,
    runPipelineToEnd,
    addBatchLines,
    processBatchQueue,
    clearBatch,
  }
})
