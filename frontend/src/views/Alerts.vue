<template>
  <el-card header="告警管理">
    <el-alert type="info" :closable="false" show-icon style="margin-bottom:12px"
      title="本页每 30 秒自动刷新；顶栏角标同步轮询。执行器/闸门成功不会自动出现在此列表，除非 monitor 写入 data/alerts。" />
    <div style="display: flex; justify-content: space-between; margin-bottom: 12px; flex-wrap:wrap; gap:8px">
      <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
        <el-button type="primary" @click="fetchAlerts" :loading="loading">刷新</el-button>
        <el-radio-group v-model="filter" @change="fetchAlerts" style="margin-left: 4px" size="small">
          <el-radio-button label="">全部</el-radio-button>
          <el-radio-button label="critical">严重</el-radio-button>
          <el-radio-button label="high">高</el-radio-button>
          <el-radio-button label="medium">中</el-radio-button>
          <el-radio-button label="low">低</el-radio-button>
        </el-radio-group>
      </div>
      <div style="display:flex;gap:8px;align-items:center">
        <el-button v-if="selectedRows.length" type="warning" size="small" @click="batchAck">确认选中 ({{ selectedRows.length }})</el-button>
        <el-button v-if="selectedRows.length" type="danger" size="small" @click="batchDelete">删除选中</el-button>
        <el-button type="success" size="small" plain @click="ackAll">全部确认</el-button>
        <el-button type="danger" size="small" plain @click="clearAll">清空全部</el-button>
        <el-tag type="info">共 {{ total }} 条 · {{ lastSyncLabel }}</el-tag>
      </div>
    </div>
    <el-table :data="alerts" v-loading="loading" stripe @selection-change="onSelectChange" ref="alertTable">
      <el-table-column type="selection" width="40" />
      <el-table-column label="发生时间" width="200">
        <template #default="{ row }">
          <span>{{ displayTime(row) }}</span>
          <el-tooltip v-if="timeTooltip(row)" :content="timeTooltip(row)" placement="top">
            <el-icon style="margin-left:4px;vertical-align:middle;color:#999"><InfoFilled /></el-icon>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column prop="source" label="来源" width="120" />
      <el-table-column prop="severity" label="级别" width="80">
        <template #default="{ row }"><el-tag :type="sevColor(row.severity)" size="small">{{ row.severity }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="message" label="描述" min-width="200" show-overflow-tooltip />
      <el-table-column prop="acknowledged" label="状态" width="100">
        <template #default="{ row }"><el-tag :type="row.acknowledged ? 'success' : 'warning'" size="small">{{ row.acknowledged ? '已确认' : '待处理' }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button type="warning" size="small" link @click="goRespond(row)">L2 处置</el-button>
          <el-button v-if="!row.acknowledged" type="primary" size="small" @click="acknowledge(row)">确认</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!alerts.length && !loading" description="暂无告警" />
  </el-card>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAlertsStore } from '../stores/alerts'
import { ElMessage, ElMessageBox } from 'element-plus'
import { InfoFilled } from '@element-plus/icons-vue'
import { formatBeijingTime } from '../utils/formatTime'
import api from '../api'

const POLL_MS = 30000
const router = useRouter()
const alertsStore = useAlertsStore()
const filter = ref('')
let pollTimer = null

const alerts = computed(() => alertsStore.items)
const loading = computed(() => alertsStore.loading)
const total = computed(() => alertsStore.total)
const lastSyncLabel = computed(() => {
  if (!alertsStore.lastFetchedAt) return '未同步'
  const d = new Date(alertsStore.lastFetchedAt)
  return `更新于 ${d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`
})

function sevColor(s) { return { critical: 'danger', high: 'warning', medium: '', low: 'info' }[s] || '' }

function displayTime(row) {
  const raw = row.occurred_at_raw || row.timestamp_raw || row.timestamp
  if (!raw) return '—'
  const s = String(raw)
  if (s.includes('T') || s.includes('+') || s.endsWith('Z')) {
    return formatBeijingTime(raw)
  }
  return formatBeijingTime(raw, { assumeUtcNaive: true })
}

function timeTooltip(row) {
  const parts = []
  if (row.occurred_at_raw) parts.push(`发生: ${row.occurred_at_raw}`)
  if (row.published_at_raw) parts.push(`入库: ${row.published_at_raw}`)
  return parts.length ? parts.join(' · ') : ''
}

async function fetchAlerts() {
  const params = filter.value ? { severity: filter.value } : {}
  await alertsStore.fetchAlerts(params)
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

// --- 批量操作 ---
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
    await api.post('/alerts/acknowledge-batch', {})
    ElMessage.success('已全部确认')
    fetchAlerts()
  } catch (e) { ElMessage.error('操作失败') }
}

async function clearAll() {
  try {
    await ElMessageBox.confirm('确定清空全部告警？此操作不可撤销。', '确认', { type: 'warning', confirmButtonText: '确定清空' })
    await api.delete('/alerts/', { data: {} })
    ElMessage.success('已清空')
    fetchAlerts()
  } catch (e) { if (e !== 'cancel') ElMessage.error('清空失败') }
}

function onVisibility() {
  if (document.visibilityState === 'visible') fetchAlerts()
}

onMounted(() => {
  fetchAlerts()
  pollTimer = setInterval(fetchAlerts, POLL_MS)
  document.addEventListener('visibilitychange', onVisibility)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  document.removeEventListener('visibilitychange', onVisibility)
})
</script>
