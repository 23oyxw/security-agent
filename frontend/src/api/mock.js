/**
 * Mock 数据拦截器
 *
 * 当环境变量 VITE_MOCK=true 或后端不可用时，
 * 拦截 API 请求返回模拟数据，避免白屏。
 *
 * 策略：
 * 1. VITE_MOCK=true → 强制使用 mock
 * 2. 后端请求失败 → 自动降级为 mock 数据（仅首次）
 */
import MockAdapter from 'axios-mock-adapter'
import api from './index'

let mockInstance = null
let isMockEnabled = false

// Mock 数据集
const mockData = {
  // 认证
  authMe: { username: 'admin', role: 'admin' },
  authLogin: { access_token: 'mock-jwt-token', token_type: 'bearer', role: 'admin', username: 'admin' },

  // 系统指标
  metrics: {
    cpu_percent: 28.5,
    memory_percent: 45.2,
    disk_percent: 32.1,
    system_health: true,
    load_avg: [0.82, 1.12, 0.95],
    network_io: { bytes_sent: 1250000000, bytes_recv: 3400000000 },
    uptime_seconds: 1294200,
    process_count: 142,
  },

  perceptionContext: {
    snapshot: {
      summary: {
        cpu_percent: 28.5,
        memory_percent: 45.2,
        disk_percent: 32.1,
        connections: 86,
        open_ports: 24,
        process_count: 142,
        system_health: true,
        permission_flags: [],
        load_avg: [0.82, 1.12, 0.95],
        network_io: { bytes_sent: 1250000000, bytes_recv: 3400000000 },
      },
    },
    summary: {
      cpu_percent: 28.5,
      memory_percent: 45.2,
      disk_percent: 32.1,
      connections: 86,
      open_ports: 24,
      process_count: 142,
      system_health: true,
    },
  },

  listeningPorts: {
    count: 8,
    ports: [
      { port: 22, proto: 'tcp', process: 'sshd' },
      { port: 80, proto: 'tcp', process: 'nginx' },
      { port: 443, proto: 'tcp', process: 'nginx' },
      { port: 5174, proto: 'tcp', process: 'node' },
      { port: 8000, proto: 'tcp', process: 'uvicorn' },
      { port: 3306, proto: 'tcp', process: 'mysqld' },
      { port: 6379, proto: 'tcp', process: 'redis' },
      { port: 9090, proto: 'tcp', process: 'prometheus' },
    ],
  },

  // 告警
  alerts: {
    alerts: [
      { id: 'a1', title: 'CPU 使用率超过阈值', level: 'high', severity: 'high', message: 'CPU 使用率达到 85%', acknowledged: false, timestamp: new Date().toISOString() },
      { id: 'a2', title: '异常登录尝试', level: 'critical', severity: 'critical', message: '检测到来自未知 IP 的登录尝试', acknowledged: false, timestamp: new Date().toISOString() },
      { id: 'a3', title: '磁盘空间不足', level: 'medium', severity: 'medium', message: '/var 分区使用率超过 80%', acknowledged: true, timestamp: new Date().toISOString() },
    ],
    total: 3,
  },
  unreadCount: { count: 2 },

  // 工作流
  flowStatus: {
    layers: {
      collection: {
        nodes: [
          { id: 'C1', value: '28%', subtitle: '负载 0.8 1.2 0.9' },
          { id: 'C2', value: '45%' },
          { id: 'C3', value: '32%' },
          { id: 'C4', value: '156' },
        ],
      },
    },
    uptime_seconds: 1294200,
  },

  // MCP 服务
  mcpServers: [
    { name: '文件系统', status: 'active', tools: 8 },
    { name: '进程管理', status: 'active', tools: 5 },
    { name: '网络工具', status: 'inactive', tools: 3 },
  ],

  // 评估
  evalScore: {
    latest: { grade: 'B', score: 78, composite: 78 },
    total_evaluations: 12,
    efficiency_ratio: 0.85,
    dimension_scores: {
      intent_accuracy: 82,
      boundary_recall: 76,
      fix_success_rate: 88,
      schedule_utilization: 71,
      batch_compliance: 94,
      tool_hit_rate: 79,
    },
    trace_metrics: { avg_stages: 4, avg_duration_ms: 1200, total_traces: 156 },
    trend_points: [65, 70, 72, 68, 75, 78, 80, 76, 79, 78],
  },

  // 健康检查
  health: { status: 'healthy', modules: { perception: true, decision: true, execution: true } },

  // 进程
  processSummary: { total_processes: 142, zombies: 0 },

  // Skills
  skills: [],

  l1BoundaryCalibration: {
    summary: { total: 42, passed: 40, failed: 2, pass_rate: 95.2, by_category: {} },
    rows: [
      { category: '终端-允许', case_id: 'T-A01', input: 'ps aux | head', expected: 'ALLOW', actual: 'ALLOW', passed: true },
      { category: '终端-拒绝', case_id: 'T-D01', input: 'rm -rf /tmp/foo', expected: 'DENY', actual: 'DENY', passed: true },
      { category: '终端-需确认', case_id: 'T-C01', input: 'kill 99999 (confirmed=False)', expected: 'NEED_CONFIRM', actual: 'NEED_CONFIRM', passed: true },
      { category: '终端-非白名单', case_id: 'T-N01', input: 'echo hello', expected: 'DENY', actual: 'DENY', passed: true },
    ],
    probe_count: 14,
  },

  l1KnowledgeRetrieve: {
    sensitivity: 'high',
    intent_tags: ['边界', '规范'],
    expanded_query: 'sudo 权限 playbook policy',
    refs: [
      { id: 'PB-TERMINAL-01', title: '终端白名单边界', snippet: '观测类 ps/ss/df 自动；kill/sudo 写操作需确认', source: 'playbook', score: 0.88, category: 'privilege', severity: '高', suggested_actions: ['test_terminal_boundaries'], do_not: ['echo|python 绕过'] },
      { id: 'PB-MISDELETE-01', title: '误删防护', snippet: 'rm 高危路径需二次确认与快照', source: 'playbook', score: 0.72, category: 'misdelete', severity: '高', suggested_actions: ['快照回滚'], do_not: ['rm -rf /'] },
    ],
    hit_count: 2,
  },
}

function setupMock(mock) {
  const loginOk = [200, mockData.authLogin]
  const meOk = [200, mockData.authMe]

  // 认证（兼容 baseURL=/api 时的两种匹配路径）
  mock.onPost('/auth/login').reply(...loginOk)
  mock.onPost('/api/auth/login').reply(...loginOk)
  mock.onGet('/auth/me').reply(...meOk)
  mock.onGet('/api/auth/me').reply(...meOk)

  // 系统指标
  mock.onGet('/api/perception/metrics').reply(200, mockData.metrics)
  mock.onGet('/api/perception/context').reply(200, mockData.perceptionContext)
  mock.onGet('/api/perception/os/ports').reply(200, mockData.listeningPorts)
  mock.onGet('/api/health').reply(200, mockData.health)

  // 告警
  mock.onGet('/api/alerts/').reply(200, mockData.alerts)
  mock.onGet('/api/alerts/unread-count').reply(200, mockData.unreadCount)
  mock.onPost(/\/api\/alerts\/.+\/acknowledge/).reply(200, { ok: true })

  // 工作流
  mock.onGet('/api/workflow/flow-status').reply(200, mockData.flowStatus)

  // MCP
  mock.onGet('/api/mcp/servers').reply(200, mockData.mcpServers)

  // 评估
  mock.onGet('/api/eval/score').reply(200, mockData.evalScore)

  // 进程
  mock.onGet('/api/ops/processes/summary').reply(200, mockData.processSummary)

  // L1 三感知
  mock.onGet('/api/l1/boundary/calibration').reply(200, {
    layer: 'L1',
    module: 'adversarial_calibration',
    summary: mockData.l1BoundaryCalibration.summary,
    rows: mockData.l1BoundaryCalibration.rows,
    resistance_training: '权限跃迁阻力对抗训练集',
    probe_count: 14,
  })
  mock.onPost('/api/l1/boundary/evaluate').reply(config => {
    const body = JSON.parse(config.data || '{}')
    const msg = (body.message || '').toLowerCase()
    const probes = []
    if (/sudo|iptables|bash|useradd/.test(msg)) {
      probes.push({ probe_id: 'PE-01', label: 'sudo 提权未确认', matched: true })
    }
    return [200, {
      layer: 'L1',
      module: 'adversarial_boundary',
      risk_level: probes.length ? 'high' : 'low',
      hits: probes.length ? [{ type: 'terminal', input: body.message, verdict: 'NEED_CONFIRM', reasons: ['privilege probe'] }] : [],
      privilege_escalation_probes: probes,
      probe_count: 14,
    }]
  })
  mock.onPost('/api/l1/knowledge/retrieve').reply(config => {
    const body = JSON.parse(config.data || '{}')
    return [200, { layer: 'L1', module: 'sensitive_knowledge', query: body.message, ...mockData.l1KnowledgeRetrieve }]
  })

  // Skills
  mock.onGet('/api/skills').reply(200, mockData.skills)
  mock.onPost(/\/api\/skills\/flows\/.+\/run/).reply(200, { ok: true, steps: [] })

  // Agent chat（兼容旧接口）
  mock.onPost('/api/agent/chat').reply(200, {
    reply: '这是模拟回复。后端服务未启动时，前端使用 Mock 数据运行。',
    session_id: 'mock-session',
  })

  const mockPlans = {}

  mock.onPost('/api/agent/plan').reply(config => {
    const body = JSON.parse(config.data || '{}')
    const planId = `mock-${Date.now().toString(36)}`
    const plan = {
      plan_id: planId,
      trace_id: `trace-${planId}`,
      batch_id: body.batch_id || null,
      intent: 'health',
      message: body.message,
      hint: 'Mock 分析计划',
      tool_chain: ['get_system_health'],
      steps: [
        { id: 'tp1', layer: 'L1', title: '抗性边界感知', status: 'done' },
        { id: 'tp2', layer: 'L1', title: '灵敏知识库检索', status: 'done' },
        { id: 'tp3', layer: 'L1', title: '静态环境感知（眼）', status: 'done' },
        { id: 'g', layer: 'L2', title: '安全管控', status: 'pending' },
        { id: 'x', layer: 'L3', title: '推理分发', status: 'pending' },
      ],
      boundary_hits: [],
      knowledge_refs: [{ title: 'Mock 知识', snippet: '模拟知识库命中', source: 'mock' }],
      static_snapshot: mockData.metrics,
      requires_confirm: false,
      l2_verdict: null,
      status: 'planned',
    }
    mockPlans[planId] = plan
    return [200, plan]
  })

  mock.onPost('/api/agent/l2/precheck').reply(config => {
    const body = JSON.parse(config.data || '{}')
    const plan = mockPlans[body.plan_id]
    if (!plan) return [404, { detail: 'plan_id 不存在' }]
    plan.l2_verdict = 'pass'
    plan.status = 'l2_pass'
    return [200, { verdict: 'pass', detail: {}, plan_id: body.plan_id }]
  })

  mock.onPost('/api/agent/execute').reply(config => {
    const body = JSON.parse(config.data || '{}')
    const plan = mockPlans[body.plan_id]
    if (!plan) return [404, { detail: 'plan_id 不存在' }]
    return [200, {
      reply: `Mock 执行完成：${plan.message}`,
      session_id: body.session_id || plan.trace_id,
      tools_used: plan.tool_chain || [],
      plan_id: body.plan_id,
      trace_id: plan.trace_id,
      mode: 'execute',
      agent: 'core_dispatch',
      phase: 'execute',
      model_used: 'mock',
      degradation_level: 'S0',
      audit: {
        agent: 'audit_iteration',
        trace_id: plan.trace_id,
        plan_id: body.plan_id,
        audit_status: 'recorded',
        wiki_reflux: 'pending',
        tools_invoked: (plan.tool_chain || []).length,
        charts: { static_perception: 'L1', link_trace: 'L4', global_metrics: 'L5' },
      },
    }]
  })

  mock.onPost('/api/agent/orchestrate').reply(config => {
    const body = JSON.parse(config.data || '{}')
    const planId = `mock-${Date.now().toString(36)}`
    const plan = {
      plan_id: planId,
      trace_id: `trace-${planId}`,
      batch_id: body.batch_id || null,
      intent: 'health',
      message: body.message,
      hint: 'Mock 编排分析',
      tool_chain: ['get_system_health'],
      steps: [],
      boundary_hits: [],
      knowledge_refs: [],
      static_snapshot: mockData.metrics,
      requires_confirm: false,
      l2_verdict: 'pass',
      status: 'l2_pass',
    }
    mockPlans[planId] = plan
    const agents = [
      { agent: 'core_dispatch', display_name: '核心调度代理', layer: 'L1+L3', status: 'done', detail: 'L1 analyze' },
      { agent: 'safety_sandbox', display_name: '安全防护沙箱代理', layer: 'L2', status: 'done', detail: 'L2 通过' },
      { agent: 'audit_iteration', display_name: '审计迭代代理', layer: 'L4+L5', status: body.auto_execute ? 'done' : 'idle', detail: body.auto_execute ? 'Mock 审计' : '' },
    ]
    const audit = body.auto_execute ? {
      agent: 'audit_iteration',
      trace_id: plan.trace_id,
      plan_id: planId,
      audit_status: 'recorded',
      wiki_reflux: 'pending',
      tools_invoked: 1,
      charts: { static_perception: 'L1', link_trace: 'L4', global_metrics: 'L5' },
    } : null
    const execute = body.auto_execute ? {
      reply: `Mock 自动执行：${body.message}`,
      session_id: plan.trace_id,
      tools_used: ['get_system_health'],
      plan_id: planId,
      trace_id: plan.trace_id,
      mode: 'execute',
      model_used: 'mock',
      degradation_level: 'S0',
    } : null
    return [200, { plan, l2: { verdict: 'pass', plan_id: planId }, agents, execute, audit }]
  })

  // Trace / Safety / Knowledge — 避免打真实后端 401 误登出
  mock.onGet(/\/api\/trace/).reply(200, { traces: [], total: 0 })
  mock.onGet('/api/safety/status').reply(200, { status: 'active', gates: [] })
  mock.onPost('/api/knowledge/search').reply(200, { results: [] })
  mock.onGet('/api/knowledge/stats').reply(200, { total: 0 })
  mock.onGet('/api/audit/logs').reply(200, { logs: [] })

  const mockScatter = {
    model: '3σ + IQR',
    definition: 'Mock 散点 · 单点偶发异常',
    anomaly_count: 2,
    points: [
      { trace_id: 'mock-t1', path_id: 'health', latency_ms: 420, error_rate: 0, jitter_ms: 21, is_anomaly: false, service: 'agent' },
      { trace_id: 'mock-t2', path_id: 'repair', latency_ms: 2100, error_rate: 12, jitter_ms: 105, is_anomaly: true, service: 'mcp' },
      { trace_id: 'mock-t3', path_id: 'scan', latency_ms: 5200, error_rate: 100, jitter_ms: 260, is_anomaly: true, service: 'flow' },
    ],
  }
  const mockHeatmap = {
    model: 'weighted_density',
    definition: 'Mock 热力 · 时段集群异常',
    x_labels: ['08-12h', '12-16h'],
    y_labels: ['agent', 'flow', 'mcp'],
    matrix: [[12, 5, 28], [45, 80, 22]],
  }
  mock.onGet('/l5/scatter').reply(200, mockScatter)
  mock.onGet('/api/l5/scatter').reply(200, mockScatter)
  mock.onGet('/l5/heatmap').reply(200, mockHeatmap)
  mock.onGet('/api/l5/heatmap').reply(200, mockHeatmap)
  mock.onGet(/\/l5\/root-cause\/.+/).reply(200, {
    trace_id: 'mock-t2',
    root_cause: '工具/MCP 执行异常',
    steps: ['可视化异常', '提取 Trace', '拆解调用链', '对比基线', '锁定根因'],
    spans: [
      { name: 'L1_analyze', duration_ms: 120, error: false },
      { name: 'L3_execute', duration_ms: 890, error: true },
    ],
  })
  mock.onGet('/l5/integration/catalog').reply(200, {
    method: '分层集成测试',
    tests: [
      { id: 'l1_plan', name: 'L1 计划感知', layer: 'L1' },
      { id: 'l2_precheck', name: 'L2 安全预检', layer: 'L2' },
      { id: 'l3_execute', name: 'L3 执行分发', layer: 'L3' },
      { id: 'l4_audit', name: 'L4 审计卷宗', layer: 'L4' },
      { id: 'l5_metrics', name: 'L5 指标模型', layer: 'L5' },
    ],
  })
  mock.onGet('/api/l5/integration/catalog').reply(200, {
    method: '分层集成测试',
    tests: [
      { id: 'l1_plan', name: 'L1 计划感知', layer: 'L1' },
      { id: 'l2_precheck', name: 'L2 安全预检', layer: 'L2' },
    ],
  })
  mock.onPost('/l5/integration/run').reply(200, {
    total: 5,
    passed: 4,
    failed: 1,
    pass_rate: 80,
    results: [
      { id: 'l1_plan', name: 'L1 计划感知', layer: 'L1', status: 'pass', elapsed_ms: 120 },
      { id: 'l3_execute', name: 'L3 执行分发', layer: 'L3', status: 'fail', elapsed_ms: 890, error: 'mock' },
    ],
  })
  mock.onPost('/api/l5/integration/run').reply(200, {
    total: 2,
    passed: 2,
    failed: 0,
    pass_rate: 100,
    results: [{ id: 'l1_plan', name: 'L1', status: 'pass', elapsed_ms: 50 }],
  })

  // 通用 fallback — 未匹配的 GET 请求返回空对象
  mock.onAny().reply(200, {})
}

/**
 * 启用 Mock 模式
 */
export function enableMock() {
  if (isMockEnabled) return
  mockInstance = new MockAdapter(api, { delayResponse: 200 })
  setupMock(mockInstance)
  isMockEnabled = true
  console.log('[Mock] 已启用 Mock 数据模式')
}

/**
 * 禁用 Mock 模式
 */
export function disableMock() {
  if (!isMockEnabled) return
  if (mockInstance) {
    mockInstance.restore()
    mockInstance = null
  }
  isMockEnabled = false
  console.log('[Mock] 已关闭 Mock 数据模式')
}

/**
 * 检查 Mock 是否已启用
 */
export function isMockActive() {
  return isMockEnabled
}

// 环境变量控制：VITE_MOCK=true 时自动启用
if (import.meta.env.VITE_MOCK === 'true') {
  enableMock()
}
