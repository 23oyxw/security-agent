<template>
  <div>
    <ArchitectureLayers highlight="trace" :default-expanded="true" />
    <el-card header="推理溯源 · Trace（执行记录，非 L3 本身）">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span>推理溯源 · Trace</span>
          <div style="display:flex;gap:8px">
            <el-select v-model="pageSize" size="small" style="width:80px" @change="fetchTraces">
              <el-option :value="10" label="10条" />
              <el-option :value="20" label="20条" />
              <el-option :value="50" label="50条" />
            </el-select>
            <el-button type="primary" size="small" :loading="loading" @click="fetchTraces">刷新</el-button>
            <el-popconfirm title="清除 30 天前的旧 Trace？" @confirm="cleanupOld">
              <template #reference>
                <el-button size="small" type="warning" plain>清理旧记录</el-button>
              </template>
            </el-popconfirm>
          </div>
        </div>
      </template>

      <el-row :gutter="16" style="margin-bottom:16px">
        <el-col :span="6" v-for="s in summaryCards" :key="s.label">
          <el-statistic :title="s.label" :value="s.value">
            <template #suffix><span style="font-size:12px;color:#999">{{ s.suffix }}</span></template>
          </el-statistic>
        </el-col>
      </el-row>

      <el-alert type="warning" :closable="false" show-icon style="margin-bottom:12px"
        title="Trace = 黑匣子：记录智能助手（L3）或 Skill 流程（L2）的执行阶段，不负责思考决策。时间为北京时间；点「详情」看阶段链。" />
      <div style="font-size:12px;color:#666;margin-bottom:8px">上次刷新: {{ lastRefreshed || '—' }}</div>

      <el-table :data="traces" v-loading="loading" stripe size="small" row-key="trace_id" empty-text="暂无溯源记录" @selection-change="onTraceSelect">
        <el-table-column prop="trace_id" label="Trace ID" width="200" show-overflow-tooltip />
        <el-table-column label="降级" width="72">
          <template #default="{ row }">
            <el-tag v-if="row.degradation_level && row.degradation_level !== 'S0'" size="small" type="warning">{{ row.degradation_level }}</el-tag>
            <span v-else style="color:#999">S0</span>
          </template>
        </el-table-column>
        <el-table-column label="时间 (北京时间)" width="200">
          <template #default="{ row }">
            <div>{{ displayTime(row) }}</div>
            <div style="font-size:11px;color:#999">{{ relativeTime(row.timestamp_raw || row.timestamp) }}</div>
          </template>
        </el-table-column>
        <el-table-column label="阶段数" width="80">
          <template #default="{ row }">
            <el-tag size="small">{{ row.stage_count ?? (row.nodes || []).length }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'success' || row.status === 'allow' ? 'success' : 'warning'" size="small">
              {{ row.status || '完成' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="target" label="目标" show-overflow-tooltip />
        <el-table-column type="selection" width="40" />
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="openDetail(row)">详情</el-button>
            <el-button size="small" link type="primary" @click="exportTrace(row.trace_id, 'text')">纪要</el-button>
            <el-button size="small" link type="success" @click="exportTrace(row.trace_id, 'html')">分析</el-button>
            <el-button size="small" link type="info" @click="exportTrace(row.trace_id, 'json')">JSON</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="selectedTraceIds.length" style="margin-top:12px;display:flex;gap:8px;align-items:center">
        <el-button type="danger" size="small" @click="batchDeleteTraces">删除选中 ({{ selectedTraceIds.length }})</el-button>
        <el-button size="small" @click="selectedTraceIds = []">取消选择</el-button>
      </div>
      <el-empty v-if="!traces.length && !loading" description="暂无溯源记录" />
    </el-card>

    <el-dialog v-model="detailOpen" :title="`Trace 详情 · ${detailRow?.trace_id || ''}`" width="720px" destroy-on-close>
      <div v-loading="detailLoading">
        <el-empty v-if="!detailLoading && !detailNodes.length" description="无阶段数据，可导出「纪要」或「分析图」" />
        <el-steps v-else :active="detailNodes.length" direction="vertical" :space="56" finish-status="success">
          <el-step
            v-for="(node, i) in detailNodes"
            :key="node.node_id || i"
            :title="node.name || node.stage || `阶段 ${i + 1}`"
            :description="traceNodeDesc(node)"
          />
        </el-steps>
        <el-descriptions v-if="detailSummary && Object.keys(detailSummary).length" :column="1" size="small" border style="margin-top:16px">
          <el-descriptions-item v-for="(v, k) in detailSummary" :key="k" :label="String(k)">{{ formatSummaryVal(v) }}</el-descriptions-item>
        </el-descriptions>
        <div v-if="detailRow?.trace_id" style="margin-top:16px;display:flex;gap:8px;flex-wrap:wrap">
          <el-button type="primary" size="small" @click="exportTrace(detailRow.trace_id, 'text')">导出执行纪要 (.txt)</el-button>
          <el-button type="success" size="small" @click="exportTrace(detailRow.trace_id, 'html')">导出可视化分析 (.html)</el-button>
          <el-button size="small" link type="info" @click="exportTrace(detailRow.trace_id, 'json')">JSON（调试）</el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { formatBeijingTime, formatRelativeBeijing } from '../utils/formatTime'
import { downloadBlob, fetchWithAuth } from '../utils/download'
import ArchitectureLayers from '../components/ArchitectureLayers.vue'

const route = useRoute()

const traces = ref([])
const loading = ref(false)
const pageSize = ref(20)
const lastRefreshed = ref('')

const detailOpen = ref(false)
const detailRow = ref(null)
const detailLoading = ref(false)
const detailNodes = ref([])
const detailSummary = ref({})

const summaryCards = computed(() => [
  { label: '总记录', value: traces.value.length, suffix: '条' },
  { label: '成功率', value: traces.value.length ? Math.round(traces.value.filter(t => t.status !== 'error').length / traces.value.length * 100) : 0, suffix: '%' },
  { label: '平均阶段', value: traces.value.length ? (traces.value.reduce((s, t) => s + (t.stage_count || 0), 0) / traces.value.length).toFixed(1) : 0, suffix: '个' },
  { label: '最近记录', value: traces.value.length ? formatTimeShort(traces.value[0]?.timestamp) : '--', suffix: '' },
])

function displayTime(row) {
  const raw = row.timestamp_raw || row.timestamp
  const assumeUtc = raw && !String(raw).includes('+08') && !String(raw).includes('T') && String(raw).includes(' ')
  return formatBeijingTime(raw, { assumeUtcNaive: assumeUtc })
}
function relativeTime(raw) {
  return formatRelativeBeijing(raw, { assumeUtcNaive: raw && String(raw).match(/^\d{4}-\d{2}-\d{2} \d{2}:/) })
}
function formatTimeShort(ts) {
  const s = formatBeijingTime(ts)
  return s === '—' ? s : s.slice(5, 16)
}
function formatObjBrief(obj, max = 200) {
  if (!obj || typeof obj !== 'object') return ''
  const bits = []
  for (const [k, v] of Object.entries(obj).slice(0, 6)) {
    if (v == null || v === '') continue
    bits.push(`${k}=${typeof v === 'object' ? '…' : String(v).slice(0, 40)}`)
  }
  const s = bits.join('；')
  return s.length > max ? s.slice(0, max - 3) + '…' : s
}
function formatSummaryVal(v) {
  if (v == null) return '—'
  if (typeof v === 'object') return formatObjBrief(v, 400) || '—'
  return String(v)
}
function traceNodeDesc(n) {
  const parts = []
  if (n.detail) parts.push(String(n.detail).slice(0, 160))
  if (n.details && typeof n.details === 'object') {
    const brief = formatObjBrief(n.details, 140)
    if (brief) parts.push(brief)
  }
  if (n.duration_ms) parts.push(`耗时: ${Number(n.duration_ms).toFixed(0)}ms`)
  if (n.verdict) parts.push(`判定: ${n.verdict}`)
  return parts.join(' | ') || '—'
}

function nodesFromBundle(bundle) {
  const st = bundle?.sqlite_trace?.stages
  if (Array.isArray(st) && st.length) {
    return st.map((s, i) => ({
      node_id: `stage-${i}`,
      name: s.name || s.stage || `阶段 ${i + 1}`,
      stage: s.name || s.stage,
      detail: typeof s.data === 'object' ? formatObjBrief(s.data, 200) : String(s.data || ''),
      status: 'success',
      duration_ms: s.duration_ms,
    }))
  }
  const events = bundle?.audit_events || []
  if (events.length) {
    return events.slice(0, 30).map((e, i) => ({
      node_id: `audit-${i}`,
      name: e.event_type || e.type || 'audit',
      detail: formatObjBrief(e.payload || e, 180) || String(e.event_type || ''),
      status: 'success',
    }))
  }
  return []
}

async function openDetail(row) {
  if (!row?.trace_id) return
  detailRow.value = row
  detailOpen.value = true
  detailLoading.value = true
  detailNodes.value = []
  detailSummary.value = {}
  try {
    const viz = await api.get(`/trace/${row.trace_id}`)
    let nodes = viz.nodes || []
    let summary = viz.summary || {}
    if (!nodes.length) {
      const bundle = await api.get(`/trace/${row.trace_id}/export`)
      nodes = nodesFromBundle(bundle)
      summary = {
        ...summary,
        status: bundle.sqlite_trace?.status || summary.status,
        user_message: (bundle.sqlite_trace?.user_message || '').slice(0, 200),
        audit_events: (bundle.audit_events || []).length,
      }
    }
    detailNodes.value = nodes
    detailSummary.value = summary
    const idx = traces.value.findIndex(t => t.trace_id === row.trace_id)
    if (idx >= 0) {
      traces.value[idx] = { ...traces.value[idx], stage_count: nodes.length, nodes, summary }
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '加载详情失败')
  } finally {
    detailLoading.value = false
  }
}

async function exportTrace(traceId, format = 'text') {
  if (!traceId) return
  try {
    const res = await fetchWithAuth(`/api/trace/${traceId}/export?format=${format}`)
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || res.statusText)
    }
    if (format === 'json') {
      const data = await res.json()
      downloadBlob(JSON.stringify(data, null, 2), `${traceId}-debug.json`, 'application/json')
      ElMessage.success('已导出 JSON（调试用）')
      return
    }
    const text = await res.text()
    const ext = format === 'html' ? 'html' : 'txt'
    const mime = format === 'html' ? 'text/html;charset=utf-8' : 'text/plain;charset=utf-8'
    downloadBlob(text, `${traceId}-report.${ext}`, mime)
    ElMessage.success(
      format === 'html' ? '已导出可视化 HTML' : format === 'text' ? '已导出执行纪要' : '已导出'
    )
  } catch (e) {
    ElMessage.error(e.message || '导出失败')
  }
}

async function fetchTraces() {
  loading.value = true
  try {
    const res = await api.get('/trace/', { params: { limit: pageSize.value } }).catch(() => ({ traces: [] }))
    const list = res.traces || res.items || res || []
    traces.value = (Array.isArray(list) ? list : []).map(t => ({
      ...t,
      timestamp: t.timestamp || formatBeijingTime(t.timestamp_raw),
      stage_count: (t.nodes || t.stages || []).length,
    }))
  } catch {
    traces.value = []
  } finally {
    loading.value = false
    lastRefreshed.value = new Date().toLocaleString('zh-CN')
  }
}

onMounted(async () => {
  await fetchTraces()
  const qid = route.query.id
  if (qid) {
    const row = traces.value.find(t => t.trace_id === qid) || { trace_id: qid }
    openDetail(row)
  }
})

// --- 批量操作 ---
const selectedTraceIds = ref([])
function onTraceSelect(rows) { selectedTraceIds.value = rows.map(r => r.trace_id) }

async function batchDeleteTraces() {
  try {
    await ElMessageBox.confirm(`确定删除选中的 ${selectedTraceIds.value.length} 条 Trace？`, '确认', { type: 'warning' })
    const res = await api.post('/trace/cleanup', { trace_ids: selectedTraceIds.value })
    ElMessage.success(`已删除 ${res.deleted_count} 条`)
    selectedTraceIds.value = []
    fetchTraces()
  } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败') }
}

async function cleanupOld() {
  try {
    const res = await api.post('/trace/cleanup', { days: 30 })
    ElMessage.success(`已清理 ${res.deleted_count} 条旧记录`)
    fetchTraces()
  } catch (e) { ElMessage.error('清理失败') }
}
</script>
