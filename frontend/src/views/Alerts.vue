<template>
  <div class="alerts-view">
    <PageHeader
      :title="pageMeta.label"
      :subtitle="pageMeta.subtitle"
      :layer="pageMeta.layer"
    >
      <template #actions>
        <span class="auto-refresh-badge" :class="polling ? 'active' : ''">
          <span class="pulse-dot"></span>
          {{ polling ? '30s 自动刷新' : '已暂停' }}
        </span>
        <el-button size="small" plain @click="toggleAggregated">{{ aggregatedMode ? '原始列表' : '聚合降噪' }}</el-button>
        <PipelineBtn action="refresh" size="small" :loading="loading" @click="fetchAlerts" />
        <el-button size="small" plain @click="togglePoll">
          {{ polling ? '暂停' : '恢复' }}
        </el-button>
      </template>
    </PageHeader>

    <!-- 告警统计卡片 -->
    <div class="stat-grid">
      <div v-for="s in alertStats" :key="s.label" class="stat-card" :style="{ '--accent': s.color }">
        <div class="stat-value" :style="{ color: s.color }">{{ s.value }}</div>
        <div class="stat-label">{{ s.label }}</div>
      </div>
    </div>

    <!-- 告警趋势图 -->
    <div class="section-card">
      <div class="section-card-header">
        <h3>告警趋势</h3>
        <div class="section-card-actions">
          <el-radio-group v-model="trendRange" size="small">
            <el-radio-button value="1h">1小时</el-radio-button>
            <el-radio-button value="6h">6小时</el-radio-button>
            <el-radio-button value="24h">24小时</el-radio-button>
          </el-radio-group>
        </div>
      </div>
      <div class="chart-area">
        <div ref="trendChart" class="trend-chart"></div>
        <div v-if="!alerts.length" class="chart-empty">
          <el-icon :size="32" color="var(--color-neutral-300)"><DataLine /></el-icon>
          <p>暂无告警数据</p>
        </div>
      </div>
    </div>

    <!-- 告警列表 -->
    <div class="section-card">
      <div class="section-card-header">
        <h3>告警列表</h3>
        <div class="section-card-actions">
          <el-radio-group v-model="filter" @change="fetchAlerts" size="small">
            <el-radio-button label="">全部</el-radio-button>
            <el-radio-button label="critical">严重</el-radio-button>
            <el-radio-button label="high">高</el-radio-button>
            <el-radio-button label="medium">中</el-radio-button>
            <el-radio-button label="low">低</el-radio-button>
          </el-radio-group>
          <el-button v-if="selectedRows.length" type="warning" size="small" @click="batchAck">确认 ({{ selectedRows.length }})</el-button>
          <el-button v-if="selectedRows.length" type="danger" size="small" @click="batchDelete">删除</el-button>
          <el-button type="success" size="small" plain @click="ackAll">全部确认</el-button>
          <el-button type="danger" size="small" plain @click="clearAll">清空</el-button>
        </div>
      </div>
      <div class="table-wrap">
        <el-table :data="displayAlerts" v-loading="loading" stripe size="small" @selection-change="onSelectChange" ref="alertTable" empty-text="暂无告警">
          <el-table-column type="selection" width="40" />
          <el-table-column label="级别" width="110">
            <template #default="{ row }">
              <span class="severity-badge" :class="row.severity || 'info'">
                <span class="severity-dot"></span>
                {{ severityLabel(row.severity) }}
              </span>
              <el-tag v-if="row.grade" size="small" type="warning" class="grade-tag">{{ row.grade }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column v-if="aggregatedMode" label="分类" width="100" prop="category" />
          <el-table-column label="时间" width="180">
            <template #default="{ row }">
              <div class="alert-time">{{ displayTime(row) }}</div>
              <div class="alert-time-relative">{{ relativeTime(row) }}</div>
            </template>
          </el-table-column>
          <el-table-column prop="source" label="来源" width="120" />
          <el-table-column prop="message" label="描述" min-width="200" show-overflow-tooltip />
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <span class="status-tag" :class="row.acknowledged ? 'read' : 'unread'">
                {{ row.acknowledged ? '已确认' : '待处理' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="160" fixed="right">
            <template #default="{ row }">
              <div class="action-btns">
                <el-button size="small" text type="primary" @click="goRespond(row)">L2 处置</el-button>
                <el-button v-if="!row.acknowledged" size="small" text type="warning" @click="acknowledge(row)">确认</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { initChart, getEcharts, scheduleChartResize } from '../composables/useEcharts'
import { chartTooltip, categoryAxis, valueAxis } from '../utils/chartTheme'
import { useAlertsStore } from '../stores/alerts'
import { ElMessage, ElMessageBox } from 'element-plus'
import { formatBeijingTime, formatRelativeBeijing } from '../utils/formatTime'
import api from '../api'
import PageHeader from '../components/common/PageHeader.vue'
import PipelineBtn from '../components/common/PipelineBtn.vue'
import { NAV_PAGES } from '../constants/navigation'

import { fetchAggregatedAlerts } from '../api/l5'

const pageMeta = NAV_PAGES.alerts
const aggregatedMode = ref(false)
const stormStats = ref(null)
const aggregatedItems = ref([])

const displayAlerts = computed(() => (aggregatedMode.value ? aggregatedItems.value : alerts.value))

const POLL_MS = 5000
const router = useRouter()
const alertsStore = useAlertsStore()
const filter = ref('')
const trendRange = ref('6h')
const trendChart = ref(null)
let pollTimer = null
let chartInstance = null
const resizeHandler = () => chartInstance?.resize()

const alerts = computed(() => alertsStore.items)
const loading = computed(() => alertsStore.loading)
const total = computed(() => alertsStore.total)
const polling = ref(true)

const alertStats = computed(() => {
  const items = alerts.value
  const critical = items.filter(a => a.severity === 'critical').length
  const high = items.filter(a => a.severity === 'high').length
  const unread = items.filter(a => !a.acknowledged).length
  return [
    { label: '严重告警', value: critical, color: '#ef4444' },
    { label: '高告警', value: high, color: '#f59e0b' },
    { label: '待处理', value: unread, color: '#3b82f6' },
    { label: '总计', value: items.length, color: '#64748b' },
  ]
})

function severityLabel(s) {
  const map = { critical: '严重', high: '高', medium: '中', low: '低', info: '信息' }
  return map[s] || s || '信息'
}

function displayTime(row) {
  const raw = row.occurred_at_raw || row.timestamp_raw || row.timestamp
  if (!raw) return '—'
  const assumeUtc = raw && !String(raw).includes('+08') && !String(raw).includes('T') && String(raw).includes(' ')
  return formatBeijingTime(raw, { assumeUtcNaive: assumeUtc })
}

function relativeTime(row) {
  const raw = row.occurred_at_raw || row.timestamp_raw || row.timestamp
  if (!raw) return ''
  const assumeUtc = raw && String(raw).match(/^\d{4}-\d{2}-\d{2} \d{2}:/)
  return formatRelativeBeijing(raw, { assumeUtcNaive: !!assumeUtc })
}

async function renderTrendChart() {
  if (!trendChart.value) return
  const echarts = await getEcharts()
  if (!chartInstance || chartInstance.isDisposed()) {
    if (chartInstance) try { chartInstance.dispose() } catch {}
    if (!trendChart.value) return
    chartInstance = await initChart(trendChart.value)
  }
  if (!alerts.value.length) { chartInstance.clear(); return }
  const now = Date.now()
  const range = trendRange.value === '1h' ? 3600000 : trendRange.value === '6h' ? 21600000 : 86400000
  const intervals = trendRange.value === '1h' ? 12 : trendRange.value === '6h' ? 12 : 24
  const step = range / intervals
  const data = Array(intervals).fill(0)
  const labels = []
  for (let i = 0; i < intervals; i++) {
    const t = new Date(now - range + i * step)
    labels.push(t.getHours().toString().padStart(2, '0') + ':' + t.getMinutes().toString().padStart(2, '0'))
  }
  alerts.value.forEach(a => {
    const raw = a.occurred_at_raw || a.timestamp_raw || a.timestamp
    if (!raw) return
    const ts = new Date(raw).getTime()
    if (isNaN(ts)) return
    const idx = Math.floor((ts - (now - range)) / step)
    if (idx >= 0 && idx < intervals) data[idx]++
  })
  chartInstance.setOption({
    tooltip: chartTooltip(),
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: categoryAxis(labels, { axisLabel: { fontSize: 10 } }),
    yAxis: valueAxis({ name: '告警数', nameTextStyle: { color: '#64748b' } }),
    series: [{
      type: 'line', data, smooth: true, areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(239, 68, 68, 0.35)' },
          { offset: 1, color: 'rgba(239, 68, 68, 0.04)' },
        ])
      },
      lineStyle: { color: '#ef4444', width: 2 },
      itemStyle: { color: '#ef4444' },
    }],
  })
  scheduleChartResize(chartInstance)
}

async function fetchAlerts() {
  if (aggregatedMode.value) {
    const agg = await fetchAggregatedAlerts()
    stormStats.value = agg
    aggregatedItems.value = (agg.display_alerts || []).map(a => ({
      ...a,
      acknowledged: false,
      source: a.source || 'aggregate',
    }))
    return
  }
  const params = filter.value ? { severity: filter.value } : {}
  await alertsStore.fetchAlerts(params)
  nextTick(renderTrendChart)
}

async function toggleAggregated() {
  aggregatedMode.value = !aggregatedMode.value
  await fetchAlerts()
  if (stormStats.value?.suppressed_count) {
    ElMessage.info(`降噪抑制 ${stormStats.value.suppressed_count} 条衍生告警`)
  }
  const pub = stormStats.value?.publish_suppress
  if (pub?.total_suppressed) {
    ElMessage.info(`发布侧累计降噪 ${pub.total_suppressed} 次`)
  }
}

function togglePoll() {
  polling.value = !polling.value
  if (polling.value) {
    pollTimer = setInterval(fetchAlerts, POLL_MS)
  } else {
    if (pollTimer) clearInterval(pollTimer)
    pollTimer = null
  }
}

function goRespond(row) {
  router.push({
    path: '/flows',
    query: {
      flow: 'alert_response',
      message: row.message || row.title || '',
      severity: row.severity || '',
    },
  })
}

async function acknowledge(row) {
  try {
    await alertsStore.acknowledge(row.id || row.alert_id)
    ElMessage.success('已确认')
  } catch (e) { ElMessage.error('操作失败') }
}

const selectedRows = ref([])
function onSelectChange(rows) { selectedRows.value = rows }

async function batchAck() {
  try {
    const ids = selectedRows.value.map(r => r.id)
    await api.post('/alerts/acknowledge-batch', { alert_ids: ids })
    ElMessage.success(`已确认 ${ids.length} 条`)
    fetchAlerts()
  } catch (e) { ElMessage.error('批量确认失败') }
}

async function batchDelete() {
  try {
    const ids = selectedRows.value.map(r => r.id)
    await ElMessageBox.confirm(`确定删除选中的 ${ids.length} 条告警？`, '确认', { type: 'warning' })
    await api.delete('/alerts/', { data: { alert_ids: ids } })
    ElMessage.success(`已删除 ${ids.length} 条`)
    fetchAlerts()
  } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败') }
}

async function ackAll() {
  try {
    await api.post('/alerts/acknowledge-batch', { alert_ids: null })
    ElMessage.success('已全部确认')
    await alertsStore.fetchAlerts()
    await alertsStore.fetchUnreadCount()
  } catch (e) {
    const msg = e.response?.data?.detail || e.message || '操作失败'
    ElMessage.error('确认失败: ' + msg)
  }
}

async function clearAll() {
  try {
    await ElMessageBox.confirm(
      '确定清空全部告警？此操作不可撤销。', '清空告警',
      { type: 'warning', confirmButtonText: '确定清空', cancelButtonText: '取消' }
    )
    await api.delete('/alerts/', { data: {} })
    ElMessage.success('已清空')
    fetchAlerts()
  } catch (e) { if (e !== 'cancel') ElMessage.error('清空失败: ' + (e.response?.data?.detail || e.message || '')) }
}

function onVisibility() {
  if (document.visibilityState === 'visible') fetchAlerts()
}

onMounted(() => {
  fetchAlerts()
  pollTimer = setInterval(fetchAlerts, POLL_MS)
  document.addEventListener('visibilitychange', onVisibility)
  window.addEventListener('resize', resizeHandler)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  document.removeEventListener('visibilitychange', onVisibility)
  window.removeEventListener('resize', resizeHandler)
  if (chartInstance) { chartInstance.dispose(); chartInstance = null }
})
</script>

<style scoped>
.alerts-view {
  max-width: var(--content-max-width);
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.page-title {
  font-size: var(--text-2xl);
  font-weight: 700;
  color: var(--color-neutral-900);
  margin: 0;
  letter-spacing: var(--tracking-tight);
}

.page-subtitle {
  font-size: var(--text-sm);
  color: var(--color-neutral-400);
  margin: var(--space-1) 0 0;
}

.page-actions {
  display: flex;
  gap: var(--space-2);
  align-items: center;
}

.auto-refresh-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-xs);
  color: var(--color-neutral-400);
  padding: 2px 8px;
  border-radius: var(--radius-full);
  background: var(--color-neutral-50);
}

.auto-refresh-badge.active {
  color: var(--color-success);
  background: var(--color-success-bg);
}

.pulse-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-neutral-300);
}

.auto-refresh-badge.active .pulse-dot {
  background: var(--color-success);
  animation: pulse-dot var(--duration-pulse) ease-in-out infinite;
  box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.4);
}

/* 双环脉冲增强 */
@keyframes pulse-dot-double {
  0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.4); }
  70% { box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }
  100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
}

.auto-refresh-badge.active .pulse-dot {
  animation: pulse-dot-double 1.8s ease-in-out infinite;
}

/* 统计卡片 */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-4);
}

.stat-card {
  background: transparent;
  border: 1px solid var(--color-neutral-200);
  border-radius: var(--radius-lg);
  padding: var(--space-4) var(--space-5);
  box-shadow: var(--shadow-sm);
  position: relative;
  overflow: hidden;
  animation: slide-up var(--duration-normal) var(--ease-out) both;
  transition: all var(--duration-normal) var(--ease-out);
}
.stat-card:nth-child(1) { animation-delay: 0ms; }
.stat-card:nth-child(2) { animation-delay: 60ms; }
.stat-card:nth-child(3) { animation-delay: 120ms; }
.stat-card:nth-child(4) { animation-delay: 180ms; }

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

/* 严重告警卡脉冲 */
.stat-card:first-child:hover {
  box-shadow: var(--shadow-md), var(--shadow-glow-danger);
}

.stat-card::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  width: 3px;
  height: 100%;
  background: var(--accent);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}

.stat-value {
  font-size: var(--text-2xl);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}

.stat-label {
  font-size: var(--text-xs);
  color: var(--color-neutral-400);
  margin-top: var(--space-1);
}

/* 图表 */
.section-card {
  background: transparent;
  border: 1px solid var(--color-neutral-200);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.section-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--color-neutral-100);
}

.section-card-header h3 {
  margin: 0;
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--color-neutral-700);
  letter-spacing: var(--tracking-tight);
}

.section-card-actions {
  display: flex;
  gap: var(--space-2);
  align-items: center;
  flex-wrap: wrap;
}

.chart-area {
  padding: var(--space-4);
  height: 260px;
}

.trend-chart {
  width: 100%;
  height: 100%;
}

.chart-empty {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  color: var(--color-neutral-300);
}

.chart-empty p {
  margin: 0;
  font-size: var(--text-sm);
}

/* 表格 */
.table-wrap {
  padding: 0 var(--space-5) var(--space-4);
}

.severity-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-xs);
  font-weight: 600;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  animation: scale-in var(--duration-fast) var(--ease-spring);
}

.severity-badge.critical { background: var(--color-danger-bg); color: var(--color-danger); }
.severity-badge.high { background: var(--color-warning-bg); color: var(--color-warning); }
.severity-badge.medium { background: #fef3c7; color: #d97706; }
.severity-badge.low { background: var(--color-info-bg); color: var(--color-info); }
.severity-badge.info { background: var(--color-neutral-50); color: var(--color-neutral-500); }

.severity-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
}

.severity-badge.critical .severity-dot { background: var(--color-danger); }
.severity-badge.high .severity-dot { background: var(--color-warning); }
.severity-badge.medium .severity-dot { background: #d97706; }
.severity-badge.low .severity-dot { background: var(--color-info); }
.severity-badge.info .severity-dot { background: var(--color-neutral-400); }

.alert-time {
  font-size: var(--text-sm);
  color: var(--color-neutral-700);
}

.alert-time-relative {
  font-size: var(--text-sm);
  color: var(--color-neutral-400);
}

.status-tag {
  font-size: var(--text-xs);
  font-weight: 600;
  padding: 2px 8px;
  border-radius: var(--radius-full);
}

.status-tag.unread { background: var(--color-warning-bg); color: var(--color-warning); }
.status-tag.read { background: var(--color-success-bg); color: var(--color-success); }

.action-btns {
  display: flex;
  gap: var(--space-1);
}

@media (max-width: 900px) {
  .stat-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
