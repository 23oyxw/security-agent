import { defineStore } from 'pinia'

import { ref, computed } from 'vue'

import { orchestrate, executePlan, getPlan, precheckL2 } from '../api/agent'

import { defaultAgentStages, mergeAgentStages, ORCHESTRATOR } from '../constants/agents'



let _batchSeq = 0

const MAX_FLOW_SESSIONS = 20



const FLOW_STATUS_LABELS = {

  analyzing: 'L1 分析中',

  analyzed: 'L1/L2 就绪',

  executing: 'L3 执行中',

  executed: '已完成',

  blocked: 'L2 拒绝',

  failed: '失败',

}



export const useAgentStore = defineStore('agent', () => {

  const mode = ref('plan')

  const currentPlan = ref(null)

  const l2Result = ref(null)

  const agentStages = ref(defaultAgentStages())

  const batchQueue = ref([])

  const sessionId = ref(null)

  const lastExecute = ref(null)

  const lastAudit = ref(null)

  const flowSessions = ref([])

  const activeFlowKey = ref(null)

  const chatMessages = ref([])

  const dispatchPhase = ref('idle')



  function trimFlowSessions() {

    if (flowSessions.value.length > MAX_FLOW_SESSIONS) {

      flowSessions.value.length = MAX_FLOW_SESSIONS

    }

  }



  function findFlow({ planId, flowKey } = {}) {

    if (planId) {

      const hit = flowSessions.value.find(s => s.planId === planId)

      if (hit) return hit

    }

    const key = flowKey || activeFlowKey.value

    if (key) {

      const hit = flowSessions.value.find(s => s.flowKey === key || s.planId === key)

      if (hit) return hit

    }

    return flowSessions.value[0] || null

  }



  function startFlow(message) {

    const flowKey = `flow-${Date.now()}`

    activeFlowKey.value = flowKey

    flowSessions.value.unshift({

      flowKey,

      planId: null,

      traceId: null,

      message,

      intent: null,

      l2Verdict: null,

      status: 'analyzing',

      statusLabel: FLOW_STATUS_LABELS.analyzing,

      startedAt: Date.now(),

      updatedAt: Date.now(),

      steps: [{

        layer: 'L1',

        type: 'user_message',

        command: message,

        ts: Date.now(),

      }],

    })

    trimFlowSessions()

    return flowKey

  }



  function bindFlowPlan(plan) {

    const session = findFlow({ flowKey: activeFlowKey.value })

    if (!session || !plan) return

    session.planId = plan.plan_id

    session.traceId = plan.trace_id

    session.intent = plan.intent

    session.updatedAt = Date.now()

    if (plan.plan_id) activeFlowKey.value = plan.plan_id

  }



  function appendFlowStep(step, { planId, flowKey } = {}) {

    const session = findFlow({ planId, flowKey: flowKey || activeFlowKey.value })

    if (!session) return

    session.steps.push({ ...step, ts: step.ts || Date.now() })

    session.updatedAt = Date.now()

  }



  function patchFlow(patch, { planId, flowKey } = {}) {

    const session = findFlow({ planId, flowKey: flowKey || activeFlowKey.value })

    if (!session) return

    Object.assign(session, patch)

    if (patch.status) {

      session.statusLabel = FLOW_STATUS_LABELS[patch.status] || patch.status

    }

    session.updatedAt = Date.now()

  }



  /** @deprecated 使用 flowSessions；保留兼容旧引用 */

  const commandLog = computed(() => {

    const s = findFlow({ planId: currentPlan.value?.plan_id })

    return s?.steps ? [...s.steps].reverse() : []

  })



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



  const activeTraceId = computed(() =>

    lastAudit.value?.trace_id

    || lastExecute.value?.trace_id

    || currentPlan.value?.trace_id

    || '',

  )



  const activeFlowSession = computed(() =>

    findFlow({ planId: currentPlan.value?.plan_id }) || findFlow({ flowKey: activeFlowKey.value }),

  )



  function pushChatMessage(msg) {

    if (!Array.isArray(chatMessages.value)) chatMessages.value = []

    chatMessages.value.push({ ...msg, timestamp: msg.timestamp || Date.now() })

  }



  function clearChatMessages() {

    chatMessages.value = []

  }



  function inferDispatchPhaseFromPlan(plan) {

    if (!plan) return 'idle'

    const st = String(plan.status || '')

    if (st.includes('executed') || plan.phase === 'finalize') return 'executed'

    if (st.includes('execute') || plan.phase === 'execute') return 'execute'

    if (plan.l2_verdict || st.startsWith('l2_')) return 'analyzed'

    return 'analyzed'

  }



  function ensureFlowFromPlan(plan) {

    if (!plan?.plan_id) return

    let session = findFlow({ planId: plan.plan_id })

    if (!session) {

      session = {

        flowKey: plan.plan_id,

        planId: plan.plan_id,

        traceId: plan.trace_id,

        message: plan.message || '（历史任务）',

        intent: plan.intent,

        l2Verdict: plan.l2_verdict,

        status: inferDispatchPhaseFromPlan(plan),

        statusLabel: FLOW_STATUS_LABELS[inferDispatchPhaseFromPlan(plan)] || '历史',

        startedAt: plan.created_at ? Date.parse(plan.created_at) || Date.now() : Date.now(),

        updatedAt: Date.now(),

        steps: [],

      }

      if (plan.message) {

        session.steps.push({

          layer: 'L1',

          type: 'user_message',

          command: plan.message,

          ts: session.startedAt,

        })

      }

      flowSessions.value.unshift(session)

      trimFlowSessions()

    }

    activeFlowKey.value = plan.plan_id

  }



  async function hydrateFromPlan(planId) {

    if (!planId) return false

    try {

      const plan = await getPlan(planId)

      if (!plan?.plan_id) return false

      currentPlan.value = plan

      sessionId.value = plan.trace_id || sessionId.value

      dispatchPhase.value = inferDispatchPhaseFromPlan(plan)

      ensureFlowFromPlan(plan)

      try {

        const l2 = await precheckL2(planId)

        l2Result.value = l2

        if (l2?.verdict) currentPlan.value = { ...plan, l2_verdict: l2.verdict }

      } catch {

        if (plan.l2_verdict) {

          l2Result.value = { verdict: plan.l2_verdict, detail: plan.l2_detail }

        }

      }

      return true

    } catch {

      return false

    }

  }



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

    activeFlowKey.value = null

    resetAgents()

  }



  function clearFlowHistory() {

    flowSessions.value = []

    activeFlowKey.value = null

  }



  function recordL2Steps(message, l2, planId) {

    if (l2?.detail?.layers?.length) {

      for (const layer of l2.detail.layers) {

        appendFlowStep({

          layer: 'L2',

          type: 'l2_defense',

          command: l2.detail.target || message,

          verdict: layer.verdict || l2.verdict,

          detail: layer,

        }, { planId })

      }

    } else if (l2) {

      appendFlowStep({

        layer: 'L2',

        type: 'l2_defense',

        command: message,

        verdict: l2.verdict,

      }, { planId })

    }

  }



  async function analyze(message, { batchId = null, autoExecute = false, userConfirmed = false } = {}) {

    resetAgents()

    dispatchPhase.value = 'analyze'

    agentStages.value[0].status = 'running'

    agentStages.value[0].detail = 'L1 analyze 阶段锁'



    const flowKey = startFlow(message)



    try {

      const res = await orchestrate(message, {

        batchId,

        autoExecute: autoExecute && mode.value === 'execute',

        userConfirmed,

      })



      bindFlowPlan(res.plan)

      const planId = res.plan?.plan_id



      appendFlowStep({

        layer: 'L1',

        type: 'plan',

        command: res.plan?.message || message,

        intent: res.plan?.intent,

        trace_id: res.plan?.trace_id,

        plan_id: planId,

      }, { planId, flowKey })



      recordL2Steps(message, res.l2, planId)



      currentPlan.value = res.plan

      l2Result.value = res.l2

      sessionId.value = res.plan.trace_id

      agentStages.value = mergeAgentStages(res.agents)



      if (res.l2?.verdict === 'deny') {

        patchFlow({ status: 'blocked', l2Verdict: res.l2.verdict, traceId: res.plan?.trace_id }, { planId })

        dispatchPhase.value = 'analyzed'

      } else if (res.execute) {

        lastExecute.value = res.execute

        lastAudit.value = res.audit || res.execute.audit || null

        appendFlowStep({

          layer: 'L3',

          type: 'execute',

          command: res.execute.reply || '',

          tools: res.execute.tools_used,

          trace_id: res.execute.trace_id,

        }, { planId })

        if (lastAudit.value) {

          appendFlowStep({

            layer: 'L4',

            type: 'audit',

            command: `审计 trace ${String(lastAudit.value.trace_id || '').slice(0, 12)}`,

            trace_id: lastAudit.value.trace_id,

          }, { planId })

        }

        patchFlow({

          status: 'executed',

          l2Verdict: res.l2?.verdict,

          traceId: res.execute.trace_id || res.plan?.trace_id,

        }, { planId })

        dispatchPhase.value = 'executed'

      } else {

        patchFlow({

          status: 'analyzed',

          l2Verdict: res.l2?.verdict,

          traceId: res.plan?.trace_id,

        }, { planId })

        dispatchPhase.value = 'analyzed'

      }



      return res

    } catch (e) {

      patchFlow({

        status: 'failed',

        statusLabel: e.response?.data?.detail || e.message,

      }, { flowKey })

      throw e

    }

  }



  async function runExecute({ userConfirmed = false } = {}) {

    if (!currentPlan.value?.plan_id) throw new Error('请先在计划模式完成 L1 分析')

    if (isBlocked.value) throw new Error('L2 安全防护已拒绝')

    if (needsConfirm.value && !userConfirmed) throw new Error('需二次确认后再执行')



    const planId = currentPlan.value.plan_id

    patchFlow({ status: 'executing' }, { planId })

    dispatchPhase.value = 'execute'

    agentStages.value[0].status = 'running'

    agentStages.value[0].detail = 'L3 execute 阶段锁'

    agentStages.value[2].status = 'idle'

    agentStages.value[2].detail = '等待执行完成'



    try {

      const res = await executePlan(planId, {

        sessionId: sessionId.value,

        userConfirmed,

      })

      lastExecute.value = res

      lastAudit.value = res.audit || null

      appendFlowStep({

        layer: 'L3',

        type: 'execute',

        command: res.reply || '',

        tools: res.tools_used,

        trace_id: res.trace_id,

      }, { planId })

      if (lastAudit.value) {

        appendFlowStep({

          layer: 'L4',

          type: 'audit',

          command: `审计 trace ${String(lastAudit.value.trace_id || '').slice(0, 12)}`,

          trace_id: lastAudit.value.trace_id,

        }, { planId })

      }

      agentStages.value[0].status = 'done'

      agentStages.value[0].detail = 'L3 execute 完成'

      if (lastAudit.value) {

        agentStages.value[2].status = 'done'

        agentStages.value[2].detail = `审计 ${String(lastAudit.value.trace_id || '').slice(0, 8)}`

      }

      patchFlow({ status: 'executed', traceId: res.trace_id }, { planId })

      dispatchPhase.value = 'executed'

      return res

    } catch (e) {

      patchFlow({

        status: 'failed',

        statusLabel: e.response?.data?.detail || e.message,

      }, { planId })

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

    flowSessions,

    activeFlowKey,

    activeFlowSession,

    commandLog,

    chatMessages,

    dispatchPhase,

    activeTraceId,

    canExecute,

    needsConfirm,

    isBlocked,

    setMode,

    resetPlan,

    clearFlowHistory,

    pushChatMessage,

    clearChatMessages,

    hydrateFromPlan,

    analyze,

    runExecute,

    runPipelineToEnd,

    addBatchLines,

    processBatchQueue,

    clearBatch,

    findFlow,

  }

}, {

  persist: {

    key: 'security-agent-pipeline',

    pick: [

      'mode',

      'currentPlan',

      'l2Result',

      'lastExecute',

      'lastAudit',

      'sessionId',

      'dispatchPhase',

      'chatMessages',

      'flowSessions',

      'activeFlowKey',

    ],

  },

})


