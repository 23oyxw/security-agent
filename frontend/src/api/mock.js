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
    latest: { grade: 'B', score: 78 },
    total_evaluations: 12,
    efficiency_ratio: 0.85,
    dimension_scores: { stability: 82, security: 75, performance: 68, reliability: 88, compliance: 71, efficiency: 84 },
    trace_metrics: { avg_stages: 4, avg_duration_ms: 1200, total_traces: 156 },
    trend_points: [65, 70, 72, 68, 75, 78, 80, 76, 79, 78],
  },

  // 健康检查
  health: { status: 'healthy', modules: { perception: true, decision: true, execution: true } },

  // 进程
  processSummary: { total_processes: 142, zombies: 0 },

  // Skills
  skills: [],
}

function setupMock(mock) {
  // 认证
  mock.onPost('/api/auth/login').reply(200, mockData.authLogin)
  mock.onGet('/api/auth/me').reply(200, mockData.authMe)

  // 系统指标
  mock.onGet('/api/perception/metrics').reply(200, mockData.metrics)
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

  // Skills
  mock.onGet('/api/skills').reply(200, mockData.skills)
  mock.onPost(/\/api\/skills\/flows\/.+\/run/).reply(200, { ok: true, steps: [] })

  // Agent chat
  mock.onPost('/api/agent/chat').reply(200, { response: '这是模拟回复。后端服务未启动时，前端使用 Mock 数据运行。', session_id: 'mock-session' })

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
