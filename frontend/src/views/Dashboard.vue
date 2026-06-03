<template>
  <div class="dashboard">
    <!-- 顶部统计卡片 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6" v-for="s in statCards" :key="s.title">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-inner">
            <el-icon :size="40" :color="s.color"><component :is="s.icon" /></el-icon>
            <div>
              <div class="stat-value">{{ s.value }}</div>
              <div class="stat-title">{{ s.title }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 系统健康 + MCP 服务状态 -->
    <el-row :gutter="16" style="margin-bottom:16px">
      <el-col :span="8">
        <el-card header="CPU 使用率" class="chart-card">
          <div ref="cpuGauge" style="height:220px"></div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card header="系统资源总览" class="chart-card">
          <div ref="resourceBar" style="height:220px"></div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card header="MCP 服务状态" class="chart-card">
          <div class="mcp-summary">
            <div class="mcp-ring">
              <span class="mcp-count">{{ mcpStats.running }}</span>
              <span class="mcp-label">运行中</span>
            </div>
            <div class="mcp-tools">
              <div class="mcp-tool-row">
                <el-icon color="#67C23A"><CircleCheckFilled /></el-icon>
                <span>运行服务: {{ mcpStats.running }}/{{ mcpStats.total }}</span>
              </div>
              <div class="mcp-tool-row">
                <el-icon color="#409EFF"><Connection /></el-icon>
                <span>工具总数: {{ mcpStats.tools }}</span>
              </div>
              <div class="mcp-tool-row">
                <el-icon :color="mcpStats.errors ? '#F56C6C' : '#67C23A'"><WarningFilled /></el-icon>
                <span>异常: {{ mcpStats.errors }}</span>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 告警趋势 + 模块健康 -->
    <el-row :gutter="16" style="margin-bottom:16px">
      <el-col :span="16">
        <el-card header="系统健康详情">
          <el-descriptions :column="3" border size="small">
            <el-descriptions-item label="CPU 使用率">
              <el-progress :percentage="metrics.cpu_percent" :color="progressColor(metrics.cpu_percent)" :stroke-width="16" :text-inside="true" />
            </el-descriptions-item>
            <el-descriptions-item label="内存使用率">
              <el-progress :percentage="metrics.memory_percent" :color="progressColor(metrics.memory_percent)" :stroke-width="16" :text-inside="true" />
            </el-descriptions-item>
            <el-descriptions-item label="磁盘使用率">
              <el-progress :percentage="metrics.disk_percent" :color="progressColor(metrics.disk_percent)" :stroke-width="16" :text-inside="true" />
            </el-descriptions-item>
            <el-descriptions-item label="系统负载">
              {{ (metrics.load_avg || []).map(v => v.toFixed(2)).join(' / ') || '--' }}
            </el-descriptions-item>
            <el-descriptions-item label="进程数">{{ metrics.process_count || '--' }}</el-descriptions-item>
            <el-descriptions-item label="运行时间">{{ formatUptime(metrics.uptime_seconds) }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card header="核心模块">
          <div v-for="(status, name) in modules" :key="name" class="module-row">
            <el-tag :type="status === 'active' ? 'success' : 'danger'" size="small" effect="dark">{{ status }}</el-tag>
            <span class="module-name">{{ moduleLabels[name] || name }}</span>
          </div>
          <el-empty v-if="!Object.keys(modules).length" description="加载中..." :image-size="40" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 最近告警 -->
    <el-card header="最近告警">
      <div style="display:flex;justify-content:space-between;margin-bottom:12px">
        <el-tag type="info">共 {{ alerts.length }} 条</el-tag>
        <el-button text type="primary" @click="$router.push('/alerts')">查看全部 →</el-button>
      </div>
      <el-table :data="alerts" size="small" stripe empty-text="暂无告警">
        <el-table-column prop="timestamp" label="时间" width="180">
          <template #default="{ row }">{{ formatTime(row.timestamp) }}</template>
        </el-table-column>
        <el-table-column prop="source" label="来源" width="120" />
        <el-table-column prop="level" label="级别" width="80">
          <template #default="{ row }">
            <el-tag :type="sevColor(row.level || row.severity)" size="small">{{ row.level || row.severity }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题" width="160" />
        <el-table-column prop="message" label="描述" show-overflow-tooltip />
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="(row.read || row.acknowledged) ? 'success' : 'warning'" size="small">
              {{ (row.read || row.acknowledged) ? '已读' : '未读' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import api from '../api'
import { useAlertsStore } from '../stores/alerts'
import { useMetricsStore } from '../stores/metrics'
import { useMcpStore } from '../stores/mcp'

const alertsStore = useAlertsStore()
const metricsStore = useMetricsStore()
const mcpStore = useMcpStore()

const cpuGauge = ref(null), resourceBar = ref(null)
const alerts = ref([])
const metrics = reactive({ cpu_percent: 0, memory_percent: 0, disk_percent: 0, load_avg: [], process_count: 0, uptime_seconds: 0, network_io: {} })
const modules = ref({})
const mcpServers = ref([])
const statCards = reactive([
  { title: 'CPU 使用率', value: '--', icon: 'Cpu', color: '#409EFF' },
  { title: '内存使用率', value: '--', icon: 'Coin', color: '#67C23A' },
  { title: '磁盘使用率', value: '--', icon: 'FolderOpened', color: '#E6A23C' },
  { title: 'MCP 工具数', value: '--', icon: 'Connection', color: '#909399' },
])

const moduleLabels = {
  agent: 'Agent 引擎', safety_gate: '安全门禁', audit: '审计日志',
  monitor: '监控服务', knowledge: '知识库', mcp: 'MCP 服务',
}

const mcpStats = reactive({ running: 0, total: 0, tools: 0, errors: 0 })

function sevColor(s) {
  const lvl = String(s || '').toLowerCase()
  return { critical: 'danger', high: 'warning', medium: '', low: 'info', error: 'danger' }[lvl] || 'info'
}

function progressColor(pct) { return pct > 90 ? '#F56C6C' : pct > 70 ? '#E6A23C' : '#67C23A' }

function formatUptime(sec) {
  if (!sec) return '--'
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60)
  return h > 24 ? `${Math.floor(h / 24)}天${h % 24}时` : `${h}时${m}分`
}

function formatTime(ts) {
  if (!ts) return '--'
  if (typeof ts === 'number') return new Date(ts * 1000).toLocaleString('zh-CN')
  return String(ts).replace('T', ' ').slice(0, 19)
}

function initCharts() {
  nextTick(() => {
    if (cpuGauge.value) {
      const chart = echarts.init(cpuGauge.value)
      chart.setOption({
        series: [{
          type: 'gauge', max: 100,
          axisLine: { lineStyle: { width: 12, color: [[0.7, '#67C23A'], [0.9, '#E6A23C'], [1, '#F56C6C']] } },
          pointer: { width: 5 },
          detail: { formatter: '{value}%', fontSize: 20, offsetCenter: [0, '60%'] },
          data: [{ value: metrics.cpu_percent, name: 'CPU' }],
        }],
      })
    }
    if (resourceBar.value) {
      const chart = echarts.init(resourceBar.value)
      chart.setOption({
        tooltip: { trigger: 'axis' },
        grid: { top: 20, bottom: 30, left: 50, right: 20 },
        xAxis: { type: 'category', data: ['CPU', '内存', '磁盘'] },
        yAxis: { type: 'value', max: 100, axisLabel: { formatter: '{value}%' } },
        series: [{
          type: 'bar', barWidth: 40,
          data: [
            { value: metrics.cpu_percent, itemStyle: { color: progressColor(metrics.cpu_percent) } },
            { value: metrics.memory_percent, itemStyle: { color: progressColor(metrics.memory_percent) } },
            { value: metrics.disk_percent, itemStyle: { color: progressColor(metrics.disk_percent) } },
          ],
          label: { show: true, position: 'top', formatter: '{c}%' },
        }],
      })
    }
  })
}

onMounted(async () => {
  try {
    const [, , , healthRes] = await Promise.all([
      metricsStore.fetchMetrics(),
      alertsStore.fetchAlerts({ limit: 8 }),
      mcpStore.refresh(),
      api.get('/health').catch(() => ({})),
    ])
    const metricsRes = metricsStore.raw

    Object.assign(metrics, metricsRes)
    statCards[0].value = `${(metrics.cpu_percent || 0).toFixed(1)}%`
    statCards[1].value = `${(metrics.memory_percent || 0).toFixed(1)}%`
    statCards[2].value = `${(metrics.disk_percent || 0).toFixed(1)}%`

    alerts.value = alertsStore.items
    modules.value = healthRes.modules || {}

    mcpServers.value = mcpStore.servers
    mcpStats.total = mcpServers.value.length
    mcpStats.running = mcpServers.value.filter(s => s.status === 'running').length
    mcpStats.tools = mcpServers.value.reduce((sum, s) => sum + (s.tools_count || 0), 0)
    mcpStats.errors = mcpServers.value.filter(s => s.status === 'error').length
    statCards[3].value = String(mcpStats.tools)

    initCharts()
  } catch {}
})
</script>

<style scoped>
.stat-row { margin-bottom: 16px; }
.stat-card .stat-inner { display: flex; align-items: center; gap: 16px; }
.stat-value { font-size: 24px; font-weight: bold; }
.stat-title { color: #999; font-size: 13px; }
.chart-card { height: 100%; }
.mcp-summary { display: flex; align-items: center; justify-content: center; gap: 32px; height: 220px; }
.mcp-ring { display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100px; height: 100px; border-radius: 50%; background: linear-gradient(135deg, #409EFF22, #67C23A22); border: 3px solid #67C23A; }
.mcp-count { font-size: 32px; font-weight: bold; color: #67C23A; }
.mcp-label { font-size: 12px; color: #999; }
.mcp-tools { display: flex; flex-direction: column; gap: 12px; }
.mcp-tool-row { display: flex; align-items: center; gap: 8px; font-size: 14px; }
.module-row { display: flex; align-items: center; gap: 8px; padding: 6px 0; border-bottom: 1px solid #f0f0f0; }
.module-row:last-child { border-bottom: none; }
.module-name { font-size: 13px; }
</style>