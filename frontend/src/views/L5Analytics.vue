<template>
  <div class="l5-page page-theme-ops">
    <PageHeader
      :title="pageMeta.label"
      :subtitle="pageMeta.subtitle"
      :layer="pageMeta.layer"
      :layer-label="pageMeta.layerLabel"
      :agent="pageMeta.agent"
    >
      <template #tags>
        <el-tag type="info" effect="plain">3σ + IQR · DBSCAN · HTN 0-1</el-tag>
        <el-tag type="success" effect="plain">ECharts</el-tag>
        <el-tag v-if="scatter?.anomaly_count != null" type="danger" effect="plain">
          异常 {{ scatter.anomaly_count }} 点
        </el-tag>
        <el-tag v-if="traceSync?.trace_count" type="warning" effect="plain">
          与 L4 共享 {{ traceSync.trace_count }} 条 Trace
        </el-tag>
        <el-tag v-if="chartsUpdatedAt" size="small" effect="plain">图表 {{ chartsUpdatedAt }}</el-tag>
      </template>
      <template #actions>
        <el-button size="small" :loading="chartsRefreshing" @click="refreshCharts">
          <el-icon><Refresh /></el-icon>
          刷新图表
        </el-button>
      </template>
    </PageHeader>

    <!-- 功能导读 -->
    <section class="l5-guide">
      <div class="l5-guide-text">
        <h2 class="l5-guide-title">L5 链路量化 · 怎么用？</h2>
        <p class="l5-guide-desc">
          <strong>只读分析层</strong>：汇总 L1 计划、L2 安全、L3 执行、L4 Trace 的数据，用统计模型找异常，并给出可反写 L1 的调优建议。
          完整卷宗请去 <el-button link type="primary" size="small" @click="goTrace()">L4 Trace</el-button>。
        </p>
        <ol class="l5-guide-steps">
          <li><span class="step-n">1</span>看<strong>六维评分</strong> — 意图、边界、修复、调度、批量、工具是否达标</li>
          <li><span class="step-n">2</span>看<strong>散点/热力</strong> — 单点离群（3σ/IQR）与时段集群故障</li>
          <li><span class="step-n">3</span><strong>点击红点</strong> — 自动链路溯源，定位最慢/报错 Span</li>
          <li><span class="step-n">4</span><strong>策略反写</strong> — 弱项生成 L1 规则/权重建议</li>
        </ol>
      </div>
      <aside v-if="evalSummary" class="l5-score-card">
        <div class="score-main">
          <span class="score-label">综合得分</span>
          <span class="score-val">{{ evalSummary.composite ?? '—' }}</span>
          <el-tag v-if="evalSummary.grade" size="small" :type="gradeTagType">{{ evalSummary.grade }} 级</el-tag>
        </div>
        <div class="score-meta">
          <span>样本 {{ evalSummary.sample ?? 0 }} 次</span>
          <span v-if="evalSummary.trace?.total_traces">Trace {{ evalSummary.trace.total_traces }} 条</span>
          <span v-if="evalSummary.composite_geometric != null">短板指数 {{ evalSummary.composite_geometric }}</span>
          <span class="score-formula-hint">{{ compositeMethodPrimary || '综合分 = 六维加权平均（安全合规 25%）' }}</span>
          <span class="score-formula-hint">{{ compositeMethodBottleneck }}</span>
        </div>
        <p v-if="!hasMetricData" class="score-hint">暂无评分：请先在「智能体对话」完成 1 次 plan/execute 任务</p>
      </aside>
    </section>

    <section v-if="mathCatalog.length" class="l5-metrics-row l5-metrics-row--single">
      <article class="l5-card l5-card--wide">
        <header class="card-head">
          <h2>数学模型 · 用途说明</h2>
          <span class="card-sub">纯 Python 统计 + ECharts 可视化（答辩可演示公式）</span>
        </header>
        <div class="model-grid">
          <div v-for="m in mathCatalog" :key="m.id" class="model-cell">
            <span class="model-layer">{{ m.layer }}</span>
            <span class="model-name">{{ m.name }}</span>
            <span class="model-formula">{{ m.formula }}</span>
            <span class="model-oss">{{ m.oss }}</span>
          </div>
        </div>
      </article>
    </section>

    <!-- 六维量化 -->
    <section class="l5-metrics-row l5-metrics-row--single">
      <article class="l5-card l5-card--wide">
        <header class="card-head">
          <h2>L5 六维量化指标</h2>
          <span class="card-sub">加权综合分 + 贝叶斯收缩/Wilson 校正 · /api/eval/score</span>
        </header>
        <div v-if="hasMetricData" class="radar-trend-row">
          <div ref="radarRef" class="chart-box chart-box--radar" />
          <div ref="trendRef" class="chart-box chart-box--trend" />
        </div>
        <table v-if="l5DimDetail.length" class="dim-method-table">
          <thead>
            <tr>
              <th>维度</th><th>层</th><th>权重</th><th>计算公式</th>
              <th>观测值</th><th>收缩后</th><th>置信度</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="d in l5DimDetail" :key="d.key" :class="{ 'is-weak': d.score < 75 }">
              <td>{{ d.label }}</td>
              <td>{{ d.source_layer }}</td>
              <td>{{ Math.round(d.weight * 100) }}%</td>
              <td class="dim-formula">{{ d.formula }}</td>
              <td>{{ d.raw }}%</td>
              <td><strong>{{ d.score }}%</strong></td>
              <td>{{ d.confidence }}%</td>
            </tr>
          </tbody>
        </table>
        <div class="metric-grid">
          <div
            v-for="m in metricValues"
            :key="m.key"
            class="metric-cell"
            :class="{ 'is-weak': m.value != null && m.value < 75 }"
            :style="{ '--mc': m.color }"
          >
            <span class="metric-label">{{ m.label }}</span>
            <span class="metric-val">{{ m.value != null ? m.value + '%' : '—' }}</span>
            <span class="metric-desc">{{ m.desc }}</span>
            <span class="metric-src">来源 {{ m.sourceLayer }}</span>
          </div>
        </div>
        <ul v-if="evolutionHints.length" class="evolve-hints">
          <li v-for="(h, i) in evolutionHints" :key="i">{{ h }}</li>
        </ul>
        <div v-if="clusterSummary.length" class="cluster-row">
          <span class="cluster-label">DBSCAN 聚类</span>
          <el-tag v-for="c in clusterSummary" :key="c.key" size="small" effect="plain" type="info">
            {{ c.label }} · {{ c.count }}
          </el-tag>
        </div>
        <div class="policy-row">
          <el-button size="small" @click="loadPolicyHints">L5→L1 策略建议</el-button>
          <el-button size="small" type="primary" plain @click="applyPolicy">反写 L1 调优</el-button>
        </div>
        <ul v-if="policyHints?.hints?.length" class="evolve-hints">
          <li v-for="(h, i) in policyHints.hints" :key="'p'+i">{{ h.message || h.action }}</li>
        </ul>
      </article>
    </section>

    <!-- 各层数据对照（全宽 + 实时 Trace/L5 数据） -->
    <section class="l5-grid l5-grid--full">
      <article class="l5-card l5-card--full">
        <header class="card-head">
          <h2>各层数据对照</h2>
          <span class="card-sub">{{ layerCross?.definition || 'L1–L5 产出 → 馈入 L5 六维；边界对抗集存 Wiki boundary-adversarial.md' }}</span>
        </header>
        <div v-if="layerCross?.trace_sample" class="dist-summary">
          <el-tag effect="plain">Trace 样本 {{ layerCross.trace_sample }}</el-tag>
          <el-tag effect="plain">卷宗解析 {{ layerCross.detail_loaded }} 条</el-tag>
        </div>
        <div v-if="layerFlowTags.length" class="layer-flow">
          <template v-for="(tag, i) in layerFlowTags" :key="tag.layer">
            <div class="layer-flow-node">
              <el-tag :type="tag.type" effect="dark" size="large">{{ tag.layer }}</el-tag>
              <span class="layer-flow-stat">{{ tag.stages }} 阶段</span>
              <span v-if="tag.errors" class="layer-flow-err">{{ tag.errors }} 异常</span>
            </div>
            <span v-if="i < layerFlowTags.length - 1" class="layer-flow-arrow">→</span>
          </template>
        </div>
        <el-table
          :data="layerCrossRows"
          size="small"
          stripe
          class="data-table layer-cross-table"
          empty-text="加载各层对照…"
        >
          <el-table-column prop="layer" label="层" width="56" fixed />
          <el-table-column prop="agent" label="Agent" width="130" show-overflow-tooltip />
          <el-table-column prop="data" label="本层产出（共享数据）" min-width="160" show-overflow-tooltip />
          <el-table-column prop="feeds" label="馈入 L5 指标" min-width="150" show-overflow-tooltip />
          <el-table-column prop="api" label="API" width="168" show-overflow-tooltip />
          <el-table-column prop="trace_count" label="涉及 Trace" width="88" align="center" />
          <el-table-column prop="trace_stages" label="阶段数" width="72" align="center" sortable />
          <el-table-column prop="total_ms" label="累计耗时(ms)" width="108" sortable />
          <el-table-column prop="error_stages" label="异常阶段" width="80" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.error_stages > 0" type="danger" size="small" effect="plain">{{ row.error_stages }}</el-tag>
              <span v-else>0</span>
            </template>
          </el-table-column>
          <el-table-column prop="l5_metric_text" label="关联 L5 得分" min-width="180" show-overflow-tooltip />
        </el-table>
      </article>
    </section>

    <section class="l5-grid l5-grid--full">
      <article class="l5-card l5-card--full">
        <header class="card-head">
          <h2>统计分布 · 耗时与风险</h2>
          <span class="card-sub">{{ distributions?.definition || '直方图分箱 + Tukey 箱线 + 分意图均值' }}</span>
        </header>
        <div v-if="distributions?.trace_count" class="dist-summary">
          <el-tag effect="plain">样本 {{ distributions.trace_count }} 条</el-tag>
          <el-tag v-if="distributions.summary" effect="plain">均值 {{ distributions.summary.mean_latency_ms }} ms</el-tag>
          <el-tag v-if="distributions.summary" effect="plain">P95 {{ distributions.summary.p95_latency_ms }} ms</el-tag>
          <el-tag v-if="distributions.summary" effect="plain">均值风险 {{ distributions.summary.mean_risk }}</el-tag>
        </div>
        <div v-if="distributions?.trace_count" class="dist-charts">
          <div ref="latHistRef" class="chart-box chart-box--dist" />
          <div ref="latBoxRef" class="chart-box chart-box--dist" />
          <div ref="riskHistRef" class="chart-box chart-box--dist" />
        </div>
        <el-table
          v-if="distributions?.intent_breakdown?.length"
          :data="distributions.intent_breakdown"
          size="small"
          stripe
          class="data-table"
          max-height="220"
        >
          <el-table-column prop="intent" label="意图" min-width="100" />
          <el-table-column prop="count" label="样本数" width="72" />
          <el-table-column prop="avg_latency_ms" label="均耗时(ms)" width="100" />
          <el-table-column prop="avg_risk" label="均风险" width="80" />
        </el-table>
        <el-empty v-else description="暂无分布数据" :image-size="48" />
      </article>
    </section>

    <section class="l5-grid l5-grid--full">
      <article class="l5-card l5-card--full">
        <header class="card-head">
          <h2>散点图 · 单点/偶发异常</h2>
          <span class="card-sub">{{ scatter?.definition || '加载中…' }}</span>
        </header>
        <div v-if="scatterHasData" ref="scatterRef" class="chart-box chart-box--xl" />
        <el-empty v-else description="暂无 Trace 散点数据" :image-size="56">
          <template #description>
            <p>请先在「智能体对话」执行一次任务（plan → L2 → execute），产生 Trace 后再刷新本页。</p>
          </template>
        </el-empty>
        <div v-if="scatter?.axis_help" class="chart-legend-box">
          <p><strong>横轴</strong> {{ scatter.axis_help.x }}</p>
          <p><strong>纵轴</strong> {{ scatter.axis_help.y }}</p>
          <p class="legend-muted">{{ scatter.axis_help.size }}</p>
        </div>
        <p v-if="selectedTrace" class="trace-hint">
          选中 <code>{{ selectedTrace.trace_id }}</code> · 路径 {{ selectedTrace.path_id }}
          <el-button link type="primary" size="small" @click="loadRootCause(selectedTrace.trace_id)">溯源</el-button>
        </p>
        <el-table
          v-if="scatterTableRows.length"
          :data="scatterTableRows"
          size="small"
          stripe
          class="data-table"
          max-height="280"
          highlight-current-row
          @row-click="onScatterRowClick"
        >
          <el-table-column prop="path_label" label="意图" width="100" />
          <el-table-column prop="latency_ms" label="耗时(ms)" width="96" sortable />
          <el-table-column prop="risk_score" label="风险分" width="80" sortable />
          <el-table-column prop="error_rate" label="阶段异常%" width="96" sortable />
          <el-table-column prop="stages" label="阶段" width="64" />
          <el-table-column prop="is_anomaly" label="离群" width="64">
            <template #default="{ row }">
              <el-tag v-if="row.is_anomaly" type="danger" size="small" effect="plain">是</el-tag>
              <span v-else>—</span>
            </template>
          </el-table-column>
          <el-table-column prop="trace_id" label="Trace ID" min-width="140" show-overflow-tooltip />
        </el-table>
      </article>

      <article class="l5-card l5-card--full">
        <header class="card-head">
          <h2>热力图 · 时段/集群异常</h2>
          <span class="card-sub">{{ heatmap?.definition || '加载中…' }}</span>
        </header>
        <div v-if="heatmapHasData" class="heatmap-wrap heatmap-wrap--wide">
          <div ref="heatmapRef" class="chart-box chart-box--heatmap-xl" />
          <aside v-if="heatmap?.legend" class="heatmap-legend">
            <h3>读图说明</h3>
            <p><strong>横轴</strong> {{ heatmap.legend.x }}</p>
            <p><strong>纵轴</strong> {{ heatmap.legend.y }}</p>
            <p><strong>颜色</strong> {{ heatmap.legend.color }}</p>
            <p class="legend-muted">{{ heatmap.legend.empty }}</p>
            <div v-if="heatmapHotspots.length" class="hotspot-table">
              <h4>热点 Top {{ heatmapHotspots.length }}</h4>
              <table>
                <thead><tr><th>时段</th><th>意图</th><th>热度</th></tr></thead>
                <tbody>
                  <tr v-for="(h, i) in heatmapHotspots" :key="i">
                    <td>{{ h.time }}</td>
                    <td>{{ h.intent }}</td>
                    <td>{{ h.value }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p v-else class="legend-muted">当前各时段任务较均匀，暂无突出热点。</p>
          </aside>
        </div>
        <el-empty v-else description="暂无时段热力数据" :image-size="56" />
      </article>
    </section>

    <section class="l5-grid l5-grid--full">
      <article class="l5-card l5-card--full l5-card--root-cause">
        <header class="card-head">
          <h2>链路溯源闭环</h2>
          <span class="card-sub">Trace/Span 全量拆解 · 横向瀑布图展示完整阶段</span>
        </header>
        <div v-if="rootCause" class="root-cause">
          <div class="rc-summary">
            <strong>{{ rootCause.root_cause }}</strong>
            <span v-if="rootCause.trace_id" class="rc-id">{{ rootCause.trace_id }}</span>
            <el-tag v-if="rootCause.spans?.length" size="small" effect="plain">{{ rootCause.spans.length }} 个阶段</el-tag>
          </div>
          <ol class="rc-steps">
            <li v-for="(s, i) in rootCause.steps" :key="i">{{ s }}</li>
          </ol>
          <div class="rc-body">
            <div class="rc-spans rc-spans--scroll">
              <div
                v-for="sp in rootCause.spans"
                :key="sp.name + sp.layer"
                class="rc-span"
                :class="{ err: sp.error || sp.is_error, slow: sp.is_slowest }"
              >
                <div class="rc-span-main">
                  <el-tag size="small" effect="plain" class="rc-layer">{{ sp.layer || '—' }}</el-tag>
                  <span class="rc-title">{{ sp.title || sp.name }}</span>
                  <el-tag v-if="sp.is_slowest" size="small" type="warning" effect="plain">最慢</el-tag>
                  <el-tag v-if="sp.is_error || sp.error" size="small" type="danger" effect="plain">异常</el-tag>
                </div>
                <div class="rc-span-meta">
                  <span v-if="sp.tool" class="rc-tool">{{ sp.tool }}</span>
                  <span class="rc-dur">{{ sp.duration_ms }} ms</span>
                </div>
              </div>
            </div>
            <div ref="waterfallRef" class="chart-box chart-box--waterfall" :style="waterfallStyle" />
          </div>
          <p class="chain-note">
            调用链按 L1 规划 → L2 安全 → L3 执行/工具 → L4 审计 拆解；柱图横轴为阶段中文名，红色=报错、橙色=最慢节点。
          </p>
          <el-button v-if="rootCause.trace_id" size="small" @click="goTrace(rootCause.trace_id)">打开 L4 卷宗</el-button>
        </div>
        <el-empty v-else description="点击散点图或下方表格行进行溯源" :image-size="64" />
      </article>
    </section>

    <section class="l5-grid l5-grid--split">
      <article class="l5-card">
        <header class="card-head">
          <h2>集成测试 · 模块链路</h2>
          <span class="card-sub">{{ catalog?.method || '分层集成 + 链路矩阵' }}</span>
        </header>
        <el-tabs v-model="integrationTab" class="integration-tabs">
          <el-tab-pane label="内部链路" name="internal">
            <p class="tab-desc">Agent 层间消息/参数/指令流转 — 黑盒内模块对接</p>
          </el-tab-pane>
          <el-tab-pane label="外部模拟" name="external">
            <p class="tab-desc">浏览器触发异常流量/高危指令模拟 — 检验五层对外防御（演示 mock）</p>
            <el-alert type="warning" :closable="false" show-icon title="外部攻击模拟需云 VM 网络权限；当前为答辩演示模式" />
          </el-tab-pane>
        </el-tabs>
        <div class="test-toolbar">
          <el-checkbox v-model="selectAll" :indeterminate="indeterminate" @change="toggleAll">全选</el-checkbox>
          <el-button type="primary" size="small" :loading="testRunning" @click="runTests">运行选中</el-button>
          <el-button size="small" :loading="testRunning" @click="runTestsAll">跑全链路</el-button>
        </div>
        <el-checkbox-group v-model="selectedTests" class="test-list">
          <label v-for="t in activeTests" :key="t.id" class="test-row">
            <el-checkbox :value="t.id">
              <span class="test-name">{{ t.name }}</span>
              <el-tag size="small" effect="plain">{{ t.layer }}</el-tag>
            </el-checkbox>
          </label>
        </el-checkbox-group>
        <div v-if="testResult" class="test-result">
          <div class="test-stats">
            通过 {{ testResult.passed }}/{{ testResult.total }} · {{ testResult.pass_rate }}%
          </div>
          <div v-for="r in testResult.results" :key="r.id" class="test-item" :class="r.status">
            <span>{{ r.name }}</span>
            <span>{{ r.status }} · {{ r.elapsed_ms }}ms</span>
          </div>
        </div>
      </article>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAgentStore } from '../stores/agent'
import { useEvalStore } from '../stores/eval'
import { ElMessage } from 'element-plus'
import {
  fetchL5Scatter,
  fetchL5Heatmap,
  fetchL5Distributions,
  fetchL5LayerCross,
  fetchL5RootCause,
  fetchL5IntegrationCatalog,
  runL5Integration,
  fetchL5ExternalCatalog,
  runL5External,
  fetchL5PolicyFeedback,
  applyL5PolicyFeedback,
  fetchL5Clusters,
  fetchL5MathCatalog,
  fetchL5Sync,
} from '../api/l5'
import api from '../api'
import { resolveTraceId, traceQuery } from '../utils/pipeline-context'
import { initChart, scheduleChartResize } from '../composables/useEcharts'
import {
  chartTooltip,
  buildRadarChartOption,
  buildWaterfallBarOption,
  buildL5ScatterOption,
  buildL5HeatmapOption,
  buildHistogramOption,
  buildBoxPlotOption,
  buildEvalTrendOption,
} from '../utils/chartTheme'
import {
  L5_FORMULA,
  buildL5MetricValues,
  buildEvolutionHints,
  l5MetricsAverage,
} from '../constants/l5-metrics'
import PageHeader from '../components/common/PageHeader.vue'
import { usePageMeta } from '../composables/usePageMeta'

const { pageMeta } = usePageMeta('l5')

const integrationTab = ref('internal')
const externalCatalog = ref(null)
const policyHints = ref(null)
const mathCatalog = ref([])
const evalSummary = ref(null)
const chartsUpdatedAt = ref('')
const chartsRefreshing = ref(false)
let chartsPollTimer = null
const CHARTS_POLL_SEC = 10
const traceSync = ref(null)

const activeTests = computed(() => {
  if (integrationTab.value === 'external') {
    return (externalCatalog.value?.scenarios || []).map(s => ({ id: s.id, name: s.name, layer: s.layer }))
  }
  return catalog.value?.tests || []
})

const router = useRouter()
const agentStore = useAgentStore()
const evalStore = useEvalStore()

const scatter = ref(null)
const heatmap = ref(null)
const distributions = ref(null)
const layerCross = ref(null)
const rootCause = ref(null)
const catalog = ref(null)
const testResult = ref(null)
const testRunning = ref(false)
const selectedTests = ref([])
const selectedTrace = ref(null)

const route = useRoute()
const metricValues = ref(buildL5MetricValues({}))
const evolutionHints = ref([])
const clusterSummary = ref([])

const l5DimDetail = ref([])
const compositeMethodPrimary = ref('')
const compositeMethodBottleneck = ref('')
const trendPoints = ref([])

const scatterTableRows = computed(() => scatter.value?.points || [])
const layerCrossRows = computed(() => layerCross.value?.rows || [])
const layerFlowTags = computed(() => {
  const order = ['L1', 'L2', 'GATE', 'L3', 'L4', 'L5']
  const stats = layerCross.value?.layer_stats || {}
  const types = { L1: 'primary', L2: 'warning', GATE: 'info', L3: 'success', L4: '', L5: 'danger' }
  return order
    .filter(layer => stats[layer]?.stage_count > 0 || ['L1', 'L2', 'L3', 'L4', 'L5'].includes(layer))
    .filter(layer => layer !== 'GATE' || stats.GATE?.stage_count > 0)
    .map(layer => ({
      layer,
      stages: stats[layer]?.stage_count ?? layerCrossRows.value.find(r => r.layer === layer)?.trace_stages ?? 0,
      errors: stats[layer]?.error_count ?? 0,
      type: types[layer] || 'info',
    }))
})
const waterfallStyle = computed(() => {
  const n = rootCause.value?.spans?.length || 0
  const h = n > 5 ? Math.max(320, n * 40 + 80) : 280
  return { height: `${h}px` }
})
const scatterHasData = computed(() => (scatter.value?.points?.length || 0) > 0)
const heatmapHasData = computed(() => {
  const m = heatmap.value?.matrix
  return Array.isArray(m) && m.length > 0 && (m[0]?.length || 0) > 0
})
const heatmapHotspots = computed(() => heatmap.value?.hotspots || [])
const hasMetricData = computed(() => metricValues.value.some(m => m.value != null))
const metricsAvg = computed(() => l5MetricsAverage(metricValues.value))
const gradeTagType = computed(() => {
  const g = evalSummary.value?.grade
  if (g === 'A' || g === 'B') return 'success'
  if (g === 'C') return 'warning'
  return 'danger'
})

const waterfallRef = ref(null)
const scatterRef = ref(null)
const heatmapRef = ref(null)
const radarRef = ref(null)
const trendRef = ref(null)
const latHistRef = ref(null)
const latBoxRef = ref(null)
const riskHistRef = ref(null)
let waterfallChart = null
let scatterChart = null
let heatmapChart = null
let radarChart = null
let trendChart = null
let latHistChart = null
let latBoxChart = null
let riskHistChart = null

const selectAll = computed({
  get() {
    const all = activeTests.value.map(t => t.id) || []
    return all.length > 0 && selectedTests.value.length === all.length
  },
  set(v) {
    selectedTests.value = v ? activeTests.value.map(t => t.id) : []
  },
})

const indeterminate = computed(() => {
  const n = activeTests.value.length || 0
  return selectedTests.value.length > 0 && selectedTests.value.length < n
})

function toggleAll(v) {
  selectAll.value = v
}

function activeRouteTraceId() {
  return resolveTraceId(route, agentStore)
}

function goTrace(traceId) {
  router.push({ path: '/trace', query: traceQuery(traceId, agentStore) })
}

async function renderRadar() {
  if (!radarRef.value || !hasMetricData.value) return
  if (!radarChart) radarChart = await initChart(radarRef.value)
  if (!radarChart) return
  const indicators = metricValues.value.map(m => ({ name: m.label, max: 100 }))
  const data = metricValues.value.map(m => m.value ?? 0)
  radarChart.setOption(buildRadarChartOption({
    indicators,
    values: data,
    name: '六维得分',
    color: '#0ea5e9',
  }), true)
  scheduleChartResize(radarChart)
}

async function renderTrend() {
  if (!trendRef.value || !trendPoints.value.length) return
  if (!trendChart) trendChart = await initChart(trendRef.value)
  if (!trendChart) return
  trendChart.setOption(buildEvalTrendOption(trendPoints.value), true)
  scheduleChartResize(trendChart)
}

async function renderDistributions() {
  const d = distributions.value
  if (!d?.trace_count) return
  await nextTick()
  if (latHistRef.value) {
    if (!latHistChart) latHistChart = await initChart(latHistRef.value)
    latHistChart?.setOption(buildHistogramOption({
      title: '耗时分布直方图',
      binLabels: d.latency_histogram?.bin_labels || [],
      counts: d.latency_histogram?.counts || [],
      color: '#3b82f6',
    }), true)
    scheduleChartResize(latHistChart)
  }
  if (latBoxRef.value) {
    if (!latBoxChart) latBoxChart = await initChart(latBoxRef.value)
    latBoxChart?.setOption(buildBoxPlotOption({ name: '耗时箱线', box: d.latency_box || {} }), true)
    scheduleChartResize(latBoxChart)
  }
  if (riskHistRef.value) {
    if (!riskHistChart) riskHistChart = await initChart(riskHistRef.value)
    riskHistChart?.setOption(buildHistogramOption({
      title: '风险分布直方图',
      binLabels: d.risk_histogram?.bin_labels || [],
      counts: d.risk_histogram?.counts || [],
      color: '#f59e0b',
    }), true)
    scheduleChartResize(riskHistChart)
  }
}

function onScatterRowClick(row) {
  if (!row?.trace_id) return
  selectedTrace.value = { trace_id: row.trace_id, path_id: row.path_id }
  loadRootCause(row.trace_id)
}

async function loadEvalMetrics() {
  try {
    const ev = await evalStore.fetchScore({ force: true, maxAgeMs: 0 })
    evalSummary.value = {
      composite: ev?.latest?.composite,
      composite_geometric: ev?.latest?.composite_geometric,
      grade: ev?.latest?.grade,
      sample: ev?.latest?.sample_count,
      trace: ev?.trace_metrics,
      label: ev?.latest?.label,
    }
    l5DimDetail.value = ev?.l5_dimensions?.dimensions || []
    compositeMethodPrimary.value = ev?.l5_dimensions?.composite_method?.primary || ''
    compositeMethodBottleneck.value = ev?.l5_dimensions?.composite_method?.bottleneck || ''
    trendPoints.value = ev?.trend_points || []
    metricValues.value = buildL5MetricValues(ev?.dimension_scores || {})
    if (l5DimDetail.value.length) {
      metricValues.value = l5DimDetail.value.map(d => ({
        key: d.key,
        label: d.label,
        sourceLayer: d.source_layer,
        desc: d.formula,
        color: metricValues.value.find(m => m.key === d.key)?.color || 'var(--color-primary-500)',
        value: d.score,
      }))
    }
    evolutionHints.value = buildEvolutionHints(metricValues.value)
    await nextTick()
    await renderRadar()
    await renderTrend()
  } catch { /* mock/offline */ }
}

async function loadMathCatalog() {
  try {
    const res = await fetchL5MathCatalog()
    mathCatalog.value = res?.models || []
  } catch {
    mathCatalog.value = []
  }
}

async function loadRootCause(traceId) {
  rootCause.value = await fetchL5RootCause(traceId)
  await nextTick()
  renderWaterfall()
}

async function renderWaterfall() {
  if (!waterfallRef.value || !rootCause.value?.spans?.length) return
  if (!waterfallChart) waterfallChart = await initChart(waterfallRef.value)
  if (!waterfallChart) return
  const spans = rootCause.value.spans
  waterfallChart.setOption(buildWaterfallBarOption(spans), true)
  scheduleChartResize(waterfallChart)
}

function scatterRow(p, idxInBucket, bucketSize) {
  const risk = p.risk_score ?? p.error_rate ?? 0
  const yJitter = bucketSize > 1 ? (idxInBucket - (bucketSize - 1) / 2) * 2.2 : 0
  return [
    p.latency_ms,
    Math.min(99, Math.max(1, risk + yJitter)),
    p.stages || 4,
    p.trace_id,
    p.path_label || p.path_id,
    p.error_rate,
    p.latency_ms,
    risk,
  ]
}

function bucketScatterPoints(pts) {
  const buckets = new Map()
  for (const p of pts) {
    const risk = p.risk_score ?? p.error_rate ?? 0
    const key = `${Math.round(p.latency_ms / 80)}|${Math.round(risk / 8)}`
    const list = buckets.get(key) || []
    list.push(p)
    buckets.set(key, list)
  }
  const rows = []
  for (const group of buckets.values()) {
    group.forEach((p, i) => rows.push(scatterRow(p, i, group.length)))
  }
  return rows
}

async function renderScatter() {
  if (!scatterRef.value || !scatterHasData.value) return
  if (scatterChart) {
    scatterChart.dispose()
    scatterChart = null
  }
  scatterChart = await initChart(scatterRef.value)
  if (!scatterChart) return
  const pts = scatter.value.points || []
  const normal = bucketScatterPoints(pts.filter(p => !p.is_anomaly))
  const anomaly = bucketScatterPoints(pts.filter(p => p.is_anomaly))

  scatterChart.setOption(buildL5ScatterOption({
    normal,
    anomaly,
    latencyRange: scatter.value.latency_range,
  }), true)
  scheduleChartResize(scatterChart)
  scatterChart.off('click')
  scatterChart.on('click', params => {
    const d = params.data
    selectedTrace.value = { trace_id: d[3], path_id: d[4] }
    loadRootCause(d[3])
  })
}

async function renderHeatmap() {
  if (!heatmapRef.value || !heatmapHasData.value) return
  if (heatmapChart) {
    heatmapChart.dispose()
    heatmapChart = null
  }
  heatmapChart = await initChart(heatmapRef.value)
  if (!heatmapChart) return
  const { x_labels: xl, y_labels: yl, matrix } = heatmap.value

  heatmapChart.setOption(buildL5HeatmapOption({
    xLabels: xl,
    yLabels: yl,
    matrix,
  }), true)
  scheduleChartResize(heatmapChart)
}

async function loadClusters() {
  try {
    const c = await fetchL5Clusters()
    const items = []
    for (const [prefix, block] of [['边界', c.boundary], ['链路', c.traces]]) {
      if (!block?.clusters?.length) continue
      for (const g of block.clusters) {
        const cid = g.cluster_id != null ? g.cluster_id : g.label
        items.push({
          key: `${prefix}-${cid}`,
          label: `${prefix}·簇${cid}`,
          count: g.size ?? g.count ?? '—',
        })
      }
    }
    clusterSummary.value = items.slice(0, 8)
  } catch { clusterSummary.value = [] }
}

async function loadTraceSync() {
  try {
    traceSync.value = await fetchL5Sync()
  } catch {
    traceSync.value = null
  }
}

async function loadCharts() {
  const [sc, hm, dist, cross] = await Promise.all([
    fetchL5Scatter(),
    fetchL5Heatmap(),
    fetchL5Distributions(),
    fetchL5LayerCross(),
  ])
  await loadTraceSync()
  scatter.value = sc
  heatmap.value = hm
  distributions.value = dist
  layerCross.value = cross
  chartsUpdatedAt.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
  await nextTick()
  await renderScatter()
  await renderHeatmap()
  await renderDistributions()
  const qTrace = activeRouteTraceId()
  if (qTrace) {
    selectedTrace.value = { trace_id: qTrace, path_id: '' }
    await loadRootCause(qTrace)
  } else {
    const first = scatter.value.points?.find(p => p.is_anomaly) || scatter.value.points?.[0]
    if (first?.trace_id) {
      selectedTrace.value = { trace_id: first.trace_id, path_id: first.path_id }
      await loadRootCause(first.trace_id)
    }
  }
}

async function refreshCharts() {
  chartsRefreshing.value = true
  try {
    await Promise.all([
      loadCharts(),
      loadEvalMetrics(),
      loadClusters(),
    ])
  } finally {
    chartsRefreshing.value = false
  }
}

async function loadCatalog() {
  catalog.value = await fetchL5IntegrationCatalog()
  externalCatalog.value = await fetchL5ExternalCatalog()
  selectedTests.value = catalog.value.tests?.map(t => t.id) || []
}

async function loadPolicyHints() {
  policyHints.value = await fetchL5PolicyFeedback()
}

async function applyPolicy() {
  const res = await applyL5PolicyFeedback()
  ElMessage.success(`已反写 L1 调优 · ${res.hints_count} 条`)
}

async function runTests() {
  testRunning.value = true
  try {
    if (integrationTab.value === 'external') {
      testResult.value = await runL5External(selectedTests.value.length ? selectedTests.value : null)
    } else {
      testResult.value = await runL5Integration(selectedTests.value.length ? selectedTests.value : null)
    }
    ElMessage.success(`测试完成：${testResult.value.passed}/${testResult.value.total} 通过`)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message)
  } finally {
    testRunning.value = false
  }
}

function runTestsAll() {
  selectedTests.value = activeTests.value.map(t => t.id) || []
  runTests()
}

function onResize() {
  scatterChart?.resize()
  heatmapChart?.resize()
  waterfallChart?.resize()
  radarChart?.resize()
  trendChart?.resize()
  latHistChart?.resize()
  latBoxChart?.resize()
  riskHistChart?.resize()
}

onMounted(async () => {
  window.addEventListener('resize', onResize)
  try {
    await Promise.all([loadCharts(), loadCatalog(), loadEvalMetrics(), loadClusters(), loadMathCatalog()])
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message || 'L5 数据加载失败')
  }
  chartsPollTimer = setInterval(() => {
    refreshCharts().catch(() => {})
  }, CHARTS_POLL_SEC * 1000)
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  if (chartsPollTimer) clearInterval(chartsPollTimer)
  scatterChart?.dispose()
  heatmapChart?.dispose()
  waterfallChart?.dispose()
  radarChart?.dispose()
  trendChart?.dispose()
  latHistChart?.dispose()
  latBoxChart?.dispose()
  riskHistChart?.dispose()
})

watch(integrationTab, () => {
  selectedTests.value = activeTests.value.map(t => t.id) || []
})

watch(scatterHasData, async v => { if (v) { await nextTick(); await renderScatter() } })
watch(heatmapHasData, async v => { if (v) { await nextTick(); await renderHeatmap() } })

watch(() => [route.query.trace, route.query.id], () => {
  const tid = activeRouteTraceId()
  if (!tid) return
  selectedTrace.value = { trace_id: tid, path_id: '' }
  loadRootCause(tid)
})
</script>

<style scoped>
.l5-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding-bottom: var(--space-6);
}

.l5-guide {
  display: grid;
  grid-template-columns: 1fr minmax(200px, 260px);
  gap: var(--space-4);
  padding: var(--space-4);
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.08), rgba(248, 250, 252, 1));
  border: 1px solid rgba(14, 165, 233, 0.2);
}

.l5-guide-title {
  margin: 0 0 var(--space-2);
  font-size: var(--text-lg);
  font-weight: 700;
  color: var(--color-text-primary);
}

.l5-guide-desc {
  margin: 0 0 var(--space-3);
  font-size: var(--text-sm);
  line-height: 1.6;
  color: var(--color-text-secondary);
}

.l5-guide-steps {
  margin: 0;
  padding-left: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}

.l5-guide-steps li {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  line-height: 1.5;
}

.step-n {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--color-primary-500);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.l5-score-card {
  padding: var(--space-4);
  border-radius: var(--radius-md);
  background: #fff;
  border: 1px solid var(--color-border-default);
  box-shadow: var(--shadow-sm);
}

.score-main {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--space-2);
}

.score-label {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
  width: 100%;
}

.score-val {
  font-family: var(--font-mono);
  font-size: 2rem;
  font-weight: 800;
  color: var(--color-primary-600);
  line-height: 1;
}

.score-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: var(--space-2);
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.score-formula-hint {
  color: var(--color-neutral-400);
  line-height: 1.4;
}

.score-hint {
  margin: var(--space-2) 0 0;
  font-size: var(--text-xs);
  color: var(--color-warning-muted);
}

.layer-cross-table {
  margin-top: var(--space-3);
}

.layer-flow {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: var(--space-3);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border-subtle);
}

.layer-flow-node {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  min-width: 72px;
}

.layer-flow-stat {
  font-size: 10px;
  color: var(--color-text-muted);
}

.layer-flow-err {
  font-size: 10px;
  color: #ef4444;
}

.layer-flow-arrow {
  font-size: 18px;
  color: var(--color-text-muted);
  padding: 0 4px;
}

.l5-metrics-row--single {
  grid-template-columns: 1fr;
}

.model-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: var(--space-2);
  margin-top: var(--space-3);
}

.model-cell {
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border-subtle);
}

.model-layer {
  display: inline-block;
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--color-primary-50);
  color: var(--color-primary-700);
  margin-bottom: 4px;
}

.model-name {
  display: block;
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--color-text-primary);
}

.model-formula {
  display: block;
  margin-top: 4px;
  font-size: 11px;
  color: var(--color-text-secondary);
  line-height: 1.4;
}

.model-oss {
  display: block;
  margin-top: 4px;
  font-size: 10px;
  color: var(--color-text-muted);
}

@media (max-width: 960px) {
  .radar-trend-row,
  .dist-charts,
  .rc-body,
  .heatmap-wrap--wide {
    grid-template-columns: 1fr;
  }
  .chart-box--xl {
    height: 360px;
  }
}

.l5-hero {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-4);
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.12), rgba(15, 23, 42, 0.6));
  border: 1px solid rgba(14, 165, 233, 0.25);
}

.l5-title {
  margin: 0 0 var(--space-2);
  font-size: var(--text-xl);
  font-weight: 700;
}

.l5-core {
  margin: 0;
  max-width: 52rem;
  color: var(--color-text-secondary);
  line-height: 1.55;
  font-size: var(--text-sm);
}

.l5-hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  align-items: flex-start;
}

.l5-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-4);
}

.l5-grid--split {
  align-items: start;
}

.l5-card {
  padding: var(--space-4);
  border-radius: var(--radius-lg);
  background: var(--glass-surface, #fff);
  border: 1px solid var(--glass-border, var(--color-border-default));
  box-shadow: var(--glass-shadow, var(--shadow-sm));
}

.cluster-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-top: var(--space-3);
  padding-top: var(--space-2);
  border-top: 1px dashed var(--color-border-subtle);
}

.cluster-label {
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--color-text-muted);
}

.card-head h2 {
  margin: 0;
  font-size: var(--text-base);
  font-weight: 600;
}

.card-sub {
  display: block;
  margin-top: var(--space-1);
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}

.chart-box {
  height: 360px;
  margin-top: var(--space-3);
}

.chart-box--xl {
  height: 460px;
}

.chart-box--radar {
  height: 280px;
  margin-top: var(--space-2);
  margin-bottom: var(--space-2);
}

.chart-box--trend {
  height: 280px;
}

.chart-box--dist {
  height: 300px;
  margin-top: 0;
}

.chart-box--heatmap-xl {
  margin-top: 0;
  min-height: 380px;
  height: 380px;
}

.chart-box--waterfall {
  min-height: 280px;
  flex: 1;
  margin-top: 0;
}

.radar-trend-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
}

.dim-method-table {
  width: 100%;
  margin-top: var(--space-3);
  font-size: 11px;
  border-collapse: collapse;
}

.dim-method-table th,
.dim-method-table td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--color-border-subtle);
  text-align: left;
  vertical-align: top;
}

.dim-method-table th {
  font-weight: 600;
  color: var(--color-text-primary);
  background: var(--color-surface-raised);
}

.dim-method-table tr.is-weak {
  background: rgba(245, 158, 11, 0.08);
}

.dim-formula {
  max-width: 220px;
  line-height: 1.4;
  color: var(--color-text-secondary);
}

.l5-grid--full {
  grid-template-columns: 1fr;
}

.l5-card--full {
  width: 100%;
}

.dist-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: var(--space-2);
}

.dist-charts {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-3);
  margin-top: var(--space-3);
}

.data-table {
  width: 100%;
  margin-top: var(--space-3);
}

.heatmap-wrap--wide {
  grid-template-columns: 1fr minmax(200px, 260px);
}

.l5-card--root-cause .root-cause {
  margin-top: var(--space-2);
}

.rc-body {
  display: grid;
  grid-template-columns: minmax(280px, 360px) 1fr;
  gap: var(--space-4);
  align-items: stretch;
}

.rc-spans--scroll {
  max-height: 480px;
  overflow-y: auto;
  padding-right: 4px;
}

.trace-hint {
  margin: var(--space-2) 0 0;
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
}

.root-cause {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  margin-top: var(--space-2);
}

.rc-summary {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  align-items: center;
}

.rc-id {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
  font-family: var(--font-mono);
}

.rc-steps {
  margin: 0;
  padding-left: 1.25rem;
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}

.rc-spans {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.rc-span {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: var(--space-2);
  border-radius: var(--radius-sm);
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border-subtle);
  font-size: var(--text-sm);
  color: var(--color-text-primary);
}

.rc-span-main {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.rc-layer {
  font-family: var(--font-mono);
  font-weight: 700;
}

.rc-title {
  font-weight: 600;
}

.rc-span-meta {
  display: flex;
  justify-content: space-between;
  gap: var(--space-2);
  font-size: 11px;
  color: var(--color-text-muted);
  padding-left: 2px;
}

.rc-tool {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rc-dur {
  font-family: var(--font-mono);
  flex-shrink: 0;
}

.rc-span.err {
  border-left: 3px solid #ef4444;
  background: rgba(239, 68, 68, 0.06);
}

.rc-span.slow {
  border-left: 3px solid #f59e0b;
}

.test-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  align-items: center;
  margin: var(--space-3) 0;
}

.test-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.test-row {
  display: block;
  padding: var(--space-2);
  border-radius: var(--radius-sm);
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border-subtle);
}

.test-name {
  margin-right: var(--space-2);
}

.test-result {
  margin-top: var(--space-3);
  font-size: var(--text-sm);
}

.test-stats {
  margin-bottom: var(--space-2);
  font-weight: 600;
}

.test-item {
  display: flex;
  justify-content: space-between;
  padding: var(--space-1) 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.test-item.pass { color: #22c55e; }
.test-item.fail { color: #ef4444; }

.l5-metrics-row {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: var(--space-4);
}

.l5-card--wide { grid-column: span 1; }

.metric-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-2);
  margin-top: var(--space-3);
}

.metric-cell {
  padding: var(--space-3);
  border-radius: var(--radius-md);
  border-left: 3px solid var(--mc);
  background: var(--color-surface-raised, #f8fafc);
  border: 1px solid var(--color-border-subtle);
  border-left-width: 3px;
  border-left-color: var(--mc);
}

.metric-cell.is-weak {
  background: var(--color-warning-bg);
}

.metric-label { display: block; font-size: var(--text-sm); font-weight: 600; color: var(--color-text-primary); }
.metric-val { display: block; font-family: var(--font-mono); font-size: var(--text-metric); font-weight: 700; margin: 4px 0; color: var(--color-text-primary); }
.metric-desc { display: block; font-size: 11px; color: var(--color-text-secondary); line-height: 1.35; margin-bottom: 4px; }
.metric-src { font-size: 10px; color: var(--color-text-muted); }

.evolve-hints {
  margin: var(--space-3) 0 0;
  padding-left: 1.25rem;
  font-size: 12px;
  color: var(--color-text-secondary);
}

.cross-table {
  width: 100%;
  margin-top: var(--space-2);
  font-size: 11px;
  border-collapse: collapse;
}

.cross-table th,
.cross-table td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--color-border-subtle);
  text-align: left;
  color: var(--color-text-secondary);
}

.cross-table th {
  color: var(--color-text-primary);
  font-weight: 600;
}

@media (max-width: 960px) {
  .l5-guide { grid-template-columns: 1fr; }
  .l5-metrics-row { grid-template-columns: 1fr; }
  .metric-grid { grid-template-columns: repeat(2, 1fr); }
}

.chart-box--sm { height: 180px; margin-top: var(--space-2); }

.chart-legend-box {
  margin-top: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border-subtle);
  font-size: 11px;
  line-height: 1.5;
  color: var(--color-text-secondary);
}

.chart-legend-box p {
  margin: 0 0 4px;
}

.legend-muted {
  color: var(--color-text-muted);
  font-size: 10px;
}

.heatmap-wrap {
  display: grid;
  grid-template-columns: 1fr minmax(160px, 220px);
  gap: var(--space-3);
  margin-top: var(--space-3);
  align-items: start;
}

.chart-box--heatmap {
  margin-top: 0;
  min-height: 280px;
}

.heatmap-legend {
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border-subtle);
  font-size: 11px;
  line-height: 1.5;
  color: var(--color-text-secondary);
}

.heatmap-legend h3,
.heatmap-legend h4 {
  margin: 0 0 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.heatmap-legend h4 {
  margin-top: var(--space-2);
}

.heatmap-legend p {
  margin: 0 0 4px;
}

.hotspot-table table {
  width: 100%;
  border-collapse: collapse;
  font-size: 10px;
}

.hotspot-table th,
.hotspot-table td {
  padding: 4px 6px;
  border-bottom: 1px solid var(--color-border-subtle);
  text-align: left;
}

.hotspot-table th {
  font-weight: 600;
  color: var(--color-text-primary);
}

.chain-note {
  margin: var(--space-2) 0 0;
  font-size: 11px;
  color: var(--color-text-muted);
}

@media (max-width: 960px) {
  .l5-grid {
    grid-template-columns: 1fr;
  }
  .heatmap-wrap {
    grid-template-columns: 1fr;
  }
}
</style>
