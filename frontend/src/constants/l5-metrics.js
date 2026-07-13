/**
 * L5 量化迭代指标 — 对齐 FINAL_ARCHITECTURE §2.3 audit_iteration
 */

export const L5_FORMULA = '各层数据共享 · 对照分析 · 策略自进化'

/** 终版 L5 六维指标（Dashboard 主卡片） */
export const L5_METRICS = [
  {
    key: 'intent_accuracy',
    label: '知识/意图相关',
    sourceLayer: 'L1',
    desc: '知识库引用覆盖（每步引用占比，上限 100%）',
    color: 'var(--color-primary-500)',
  },
  {
    key: 'boundary_recall',
    label: '边界召回',
    sourceLayer: 'L1',
    desc: '抗性边界感知 · 越界识别命中率',
    color: 'var(--color-primary-400)',
  },
  {
    key: 'fix_success_rate',
    label: '修复成功率',
    sourceLayer: 'L3',
    desc: '故障修复工具簇 · 受控修复结果',
    color: 'var(--color-success)',
  },
  {
    key: 'schedule_utilization',
    label: '调度利用率',
    sourceLayer: 'L3',
    desc: '资源调度簇 · 配额与优先级执行',
    color: 'var(--color-warning)',
  },
  {
    key: 'batch_compliance',
    label: '批量合规率',
    sourceLayer: 'L1-L5',
    desc: '批量强制全流程 · 独立 trace',
    color: 'var(--color-metric-process)',
  },
  {
    key: 'tool_hit_rate',
    label: '工具命中率',
    sourceLayer: 'L3',
    desc: 'MCP 四工具簇 · 单工具单职责选型',
    color: 'var(--color-metric-uptime)',
  },
]

/** API 中文维度 → L5 六维键 */
export const EVAL_CN_MAP = {
  成功率: 'fix_success_rate',
  安全合规: 'boundary_recall',
  效率比: 'schedule_utilization',
  步骤效率: 'tool_hit_rate',
  稳定性: 'batch_compliance',
  知识相关: 'intent_accuracy',
}

/** API dimension_scores → L5 键映射（兼容旧 eval 字段 + 中文） */
export const L5_DIM_ALIASES = {
  intent_accuracy: ['intent_accuracy', 'knowledge_relevance', '知识相关'],
  boundary_recall: ['boundary_recall', 'safety_compliance', '安全合规', 'compliance', 'security'],
  fix_success_rate: ['fix_success_rate', 'reliability', '成功率'],
  schedule_utilization: ['schedule_utilization', 'efficiency', 'efficiency_ratio', '效率比'],
  batch_compliance: ['batch_compliance', 'compliance', 'stability', '稳定性'],
  tool_hit_rate: ['tool_hit_rate', 'step_efficiency', '步骤效率'],
}

export function normalizeDimScores(dimScores) {
  if (!dimScores || typeof dimScores !== 'object') return {}
  const out = { ...dimScores }
  for (const [cn, key] of Object.entries(EVAL_CN_MAP)) {
    if (dimScores[cn] != null && out[key] == null) out[key] = dimScores[cn]
  }
  return out
}

export function pickL5Score(dimScores, key) {
  if (!dimScores || typeof dimScores !== 'object') return null
  const aliases = L5_DIM_ALIASES[key] || [key]
  for (const alias of aliases) {
    const v = dimScores[alias]
    if (v != null && !Number.isNaN(Number(v))) {
      return Math.max(0, Math.min(100, Math.round(Number(v))))
    }
  }
  return null
}

export function buildL5MetricValues(dimScores, fallbacks = {}) {
  const normalized = normalizeDimScores(dimScores)
  return L5_METRICS.map(m => ({
    ...m,
    value: pickL5Score(normalized, m.key) ?? fallbacks[m.key] ?? null,
  }))
}

/** 六维均值（有值项） */
export function l5MetricsAverage(metricValues) {
  const nums = metricValues.map(m => m.value).filter(v => v != null && !Number.isNaN(v))
  if (!nums.length) return null
  return Math.round(nums.reduce((a, b) => a + b, 0) / nums.length)
}

/** L5 策略自进化建议（基于弱项；Trace 背书维度不过度告警） */
export function buildEvolutionHints(metricValues) {
  const weak = metricValues.filter(m => m.value != null && m.value < 70)
  if (!weak.length) {
    return ['各 L5 指标处于健康区间，维持当前规则/权重/阈值配置。']
  }
  return weak.map(m => {
    const hints = {
      intent_accuracy: '建议加强 L1 知识检索权重与意图分类样本回流 Wiki。',
      boundary_recall: '建议扩充 Gitee Wiki 边界对抗集并提高 L1 边界感知阈值。',
      fix_success_rate: '建议复盘 L3 修复簇失败 trace，优化 repair flow 与 L2 确认策略。',
      schedule_utilization: '建议调整 L3 调度簇配额策略与批量预调度参数。',
      batch_compliance: '建议检查批量队列是否跳过 L1 analyze（强制独立 trace）。',
      tool_hit_rate: '建议对照 cluster_map 优化 L3 工具选型与 registry 元数据。',
    }
    return `${m.label}（${m.value}%）偏低：${hints[m.key] || '请对照 Trace 卷宗复盘。'}`
  })
}

export const L5_LAYER_CROSS = [
  { layer: 'L1', agent: 'core_dispatch', data: 'plan · 三感知 · 静态快照', feeds: 'L2 预检 · L5 意图/边界指标' },
  { layer: 'L2', agent: 'safety_sandbox', data: 'verdict · 护栏命中', feeds: 'L3 门禁 · L5 合规对照' },
  { layer: 'L3', agent: 'core_dispatch', data: 'tools_used · 执行结果', feeds: 'L4 审计 · L5 修复/调度/工具指标' },
  { layer: 'L4', agent: 'audit_iteration', data: 'trace 卷宗 · 链路绘图', feeds: 'Wiki 回流 · L5 归因' },
  { layer: 'L5', agent: 'audit_iteration', data: '全维量化 · 策略反写', feeds: '规则/权重/阈值 · L1 边界集' },
]
