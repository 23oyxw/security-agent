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

    <!-- 智能根因分析 + OS 深度感知 -->
    <el-row :gutter="16" style="margin-bottom:16px">
      <el-col :span="12">
        <el-card class="rca-card">
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span>🔍 智能根因分析</span>
              <el-button type="primary" size="small" :loading="rcaLoading" @click="runRootCause">
                一键分析
              </el-button>
            </div>
          </template>
          <div v-if="rcaReport">
            <el-alert
              :title="rcaReport.summary"
              :type="rcaReport.has_issues ? (rcaReport.critical_count > 0 ? 'error' : 'warning') : 'success'"
              :closable="false"
              show-icon
              style="margin-bottom:12px"
            />
            <div v-for="f in rcaReport.findings" :key="f.title" class="rca-finding">
              <el-tag :type="f.severity === 'critical' ? 'danger' : 'warning'" size="small" effect="dark">
                {{ f.severity === 'critical' ? '严重' : '警告' }}
              </el-tag>
              <el-tag size="small" type="info" style="margin-left:4px">{{ f.category }}</el-tag>
              <div class="rca-title">{{ f.title }}</div>
              <div class="rca-cause">根因: {{ f.root_cause }}</div>
              <div class="rca-actions">
                <span v-for="a in f.suggested_actions" :key="a" class="rca-action-tag">• {{ a }}</span>
              </div>
            </div>
          </div>
          <el-empty v-else-if="!rcaLoading" description="点击「一键分析」检测系统异常" :image-size="60" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card header="🌐 网络端口监控" class="os-card">
          <el-table :data="osPorts" size="small" stripe empty-text="加载中..." max-height="200">
            <el-table-column prop="address" label="监听地址" show-overflow-tooltip />
            <el-table-column prop="port" label="端口" width="80" />
            <el-table-column prop="process" label="进程" show-overflow-tooltip />
          </el-table>
          <div v-if="osZombies && osZombies.zombie_count > 0" style="margin-top:12px">
            <el-alert :title="`⚠️ 检测到 ${osZombies.zombie_count} 个僵尸进程`" type="warning" :closable="false" show-icon />
          </div>
          <div v-if="osErrors && osErrors.length > 0" style="margin-top:12px">
            <el-tag type="danger" size="small">最近错误日志 {{ osErrors.length }} 条</el-tag>
            <div v-for="(e, i) in osErrors.slice(0, 3)" :key="i" class="os-error-line">{{ e.slice(0, 120) }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 一键测试面板 -->
    <el-card style="margin-bottom:16px">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span>⚡ 一键测试 — 所有 Skill Flow 快速验证</span>
          <div>
            <el-button type="primary" size="small" :loading="testAllLoading" @click="runAllTests">
              全部运行
            </el-button>
            <el-button size="small" @click="$router.push('/skill-flows')">Skill 编排页 →</el-button>
          </div>
        </div>
      </template>
      <el-alert type="info" :closable="false" show-icon style="margin-bottom:12px"
        title="点击单项测试或「全部运行」，所有结果实时显示，方便排查假运行问题" />
      <el-table :data="testCases" size="small" stripe>
        <el-table-column prop="label" label="测试项" width="180" />
        <el-table-column prop="flow" label="Flow" width="150" />
        <el-table-column prop="description" label="说明" min-width="200" />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.status === 'ok'" type="success" size="small">✓ 通过</el-tag>
            <el-tag v-else-if="row.status === 'fail'" type="danger" size="small">✗ 失败</el-tag>
            <el-tag v-else-if="row.status === 'blocked'" type="warning" size="small">⊘ 拦截</el-tag>
            <el-tag v-else-if="row.status === 'running'" type="primary" size="small" effect="plain">运行中...</el-tag>
            <span v-else style="color:#999;font-size:12px">—</span>
          </template>
        </el-table-column>
        <el-table-column label="耗时" width="80">
          <template #default="{ row }">
            <span v-if="row.elapsed_ms != null" style="font-size:12px">{{ row.elapsed_ms }}ms</span>
          </template>
        </el-table-column>
        <el-table-column label="详情" min-width="200">
          <template #default="{ row }">
            <span v-if="row.detail" style="font-size:12px;color:#606266">{{ row.detail }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" :loading="row.status === 'running'" @click="runSingleTest(row)">
              测试
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 进程管理 + CPU 压测 -->
    <el-row :gutter="16" style="margin-bottom:16px">
      <el-col :span="12">
        <el-card class="ops-card">
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span>🧹 进程管理</span>
              <div>
                <el-button size="small" :loading="procLoading" @click="loadProcessSummary">刷新</el-button>
                <el-button type="warning" size="small" :loading="procCleanLoading" @click="cleanZombies">清理僵尸</el-button>
                <el-button type="danger" size="small" :loading="optimizeLoading" @click="systemOptimize">一键优化</el-button>
              </div>
            </div>
          </template>
          <div v-if="procSummary" style="margin-bottom:12px">
            <el-descriptions :column="2" size="small" border>
              <el-descriptions-item label="总进程数">
                <el-tag type="info" size="large">{{ procSummary.total_processes }}</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="僵尸进程">
                <el-tag :type="procSummary.zombies > 0 ? 'danger' : 'success'" size="large">{{ procSummary.zombies }}</el-tag>
              </el-descriptions-item>
            </el-descriptions>
            <div style="margin-top:8px">
              <div v-for="(count, user) in procSummary.by_user" :key="user" style="display:inline-block;margin:4px">
                <el-tag size="small">{{ user }}: {{ count }}个</el-tag>
              </div>
            </div>
          </div>
          <el-empty v-if="!procSummary && !procLoading" description="点击刷新查看进程状态" :image-size="40" />
          <el-alert v-if="procCleanResult" :title="procCleanResult" :type="procCleanResult.includes('成功') || procCleanResult.includes('清理') ? 'success' : 'warning'" :closable="true" @close="procCleanResult=''" style="margin-top:8px" />
          <el-alert v-if="optimizeResult" :title="optimizeResult" type="success" :closable="true" @close="optimizeResult=''" style="margin-top:8px" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card class="ops-card">
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span>🔥 CPU 多核压测</span>
              <div>
                <el-button size="small" :loading="cpuInfoLoading" @click="loadCpuInfo">刷新信息</el-button>
                <el-button type="danger" size="small" :loading="stressLoading" @click="runStress(10)">压测10秒</el-button>
                <el-button type="danger" size="small" :loading="stressLoading" @click="runStress(30)">压测30秒</el-button>
              </div>
            </div>
          </template>
          <div v-if="cpuInfo">
            <el-descriptions :column="2" size="small" border>
              <el-descriptions-item label="CPU 型号" :span="2">{{ cpuInfo.model }}</el-descriptions-item>
              <el-descriptions-item label="核心数">
                <el-tag type="primary" size="large">{{ cpuInfo.cores }} 核</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="频率">{{ cpuInfo.frequency }}</el-descriptions-item>
              <el-descriptions-item label="平均负载">
                {{ (cpuInfo.load_avg || []).map(v => v.toFixed(2)).join(' / ') }}
              </el-descriptions-item>
              <el-descriptions-item label="总 CPU 使用">
                <el-progress :percentage="cpuInfo.avg_cpu_percent || 0" :color="progressColor(cpuInfo.avg_cpu_percent)" :stroke-width="14" :text-inside="true" />
              </el-descriptions-item>
            </el-descriptions>
            <div style="margin-top:12px">
              <div style="font-size:12px;color:#999;margin-bottom:6px">各核心使用率：</div>
              <div style="display:flex;flex-wrap:wrap;gap:6px">
                <div v-for="(pct, i) in (cpuInfo.per_core_percent || [])" :key="i" style="width:60px;text-align:center">
                  <el-progress type="circle" :percentage="pct" :width="48" :stroke-width="4" :color="progressColor(pct)" :show-text="false" />
                  <div style="font-size:10px;color:#999">C{{ i }} {{ pct }}%</div>
                </div>
              </div>
            </div>
          </div>
          <el-empty v-if="!cpuInfo && !cpuInfoLoading" description="点击刷新查看 CPU 信息" :image-size="40" />
          <el-alert v-if="stressResult" :title="stressResult" type="info" :closable="true" @close="stressResult=''" style="margin-top:8px" />
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
import { ElMessage } from 'element-plus'
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

// OS 深度感知 + 根因分析
const rcaLoading = ref(false)
const rcaReport = ref(null)
const osPorts = ref([])
const osZombies = ref(null)
const osErrors = ref([])

// 一键测试面板
const testAllLoading = ref(false)
const testCases = reactive([
  { key: 'scan', label: '安全扫描', flow: 'scan_report', description: '进程/路径/端口扫描 + 生成报告', status: '', elapsed_ms: null, detail: '' },
  { key: 'exec_safe', label: '安全命令(ls)', flow: 'secure_exec', description: '三层防御评估 + 安全执行 ls /tmp', status: '', elapsed_ms: null, detail: '', context: { command: 'ls -la /tmp', user_message: '查看临时目录', user_confirmed: true } },
  { key: 'exec_block', label: '拦截命令(rm)', flow: 'secure_exec', description: '高危命令 rm -rf / 应被拦截', status: '', elapsed_ms: null, detail: '', context: { command: 'rm -rf /', user_message: '删除根目录', user_confirmed: false } },
  { key: 'cleanup_scan', label: '清理扫描', flow: 'system_cleanup_scan', description: '扫描可清理项，不执行', status: '', elapsed_ms: null, detail: '' },
  { key: 'cleanup_run', label: '清理执行(安全)', flow: 'system_cleanup_run', description: '仅清理 apt/journal/log', status: '', elapsed_ms: null, detail: '', context: { categories: ['apt', 'journal', 'log'], confirm_all: false } },
  { key: 'alert', label: '告警响应', flow: 'alert_response', description: '模拟告警事件路由', status: '', elapsed_ms: null, detail: '', context: { alert_event: { message: 'CPU 持续高于 90%', level: '高', source: 'test' } } },
])

async function runSingleTest(tc) {
  tc.status = 'running'
  tc.detail = ''
  tc.elapsed_ms = null
  const t0 = Date.now()
  try {
    const ctx = tc.context || {}
    const res = await api.post(`/skills/flows/${tc.flow}/run`, { context: ctx })
    tc.elapsed_ms = Date.now() - t0
    if (res.ok) {
      tc.status = 'ok'
      // 拼接关键详情
      const stepNames = (res.steps || []).map(s => {
        const label = s.step || `step_${s.index}`
        return s.ok === false ? `✗${label}` : `✓${label}`
      })
      tc.detail = stepNames.join(' → ')
      if (res.report_html_path) tc.detail += ` | ${res.report_html_path.split('/').pop()}`
    } else {
      // 检查是否被拦截（这是预期行为）
      const blocked = (res.steps || []).some(s => s.blocked)
      if (blocked) {
        tc.status = 'blocked'
        const blockStep = res.steps.find(s => s.blocked)
        tc.detail = '预期拦截: ' + (blockStep?.message || blockStep?.error || '安全策略拦截')
      } else {
        tc.status = 'fail'
        const errStep = res.steps?.find(s => s.ok === false)
        tc.detail = errStep?.error || errStep?.message || '流程失败'
      }
    }
  } catch (e) {
    tc.elapsed_ms = Date.now() - t0
    tc.status = 'fail'
    tc.detail = e.response?.data?.detail || e.message || '请求失败'
  }
}

async function runAllTests() {
  testAllLoading.value = true
  for (const tc of testCases) {
    await runSingleTest(tc)
  }
  testAllLoading.value = false
  const ok = testCases.filter(t => t.status === 'ok' || t.status === 'blocked').length
  const fail = testCases.filter(t => t.status === 'fail').length
  ElMessage[fail > 0 ? 'warning' : 'success'](`测试完成: ${ok} 通过/拦截, ${fail} 失败`)
}

// 进程管理 + CPU 压测
const procLoading = ref(false)
const procCleanLoading = ref(false)
const optimizeLoading = ref(false)
const cpuInfoLoading = ref(false)
const stressLoading = ref(false)
const procSummary = ref(null)
const procCleanResult = ref('')
const optimizeResult = ref('')
const cpuInfo = ref(null)
const stressResult = ref('')

async function loadProcessSummary() {
  procLoading.value = true
  try {
    procSummary.value = await api.get('/ops/processes/summary')
  } catch (e) {
    procCleanResult.value = '加载失败: ' + (e.message || '未知')
  } finally {
    procLoading.value = false
  }
}

async function cleanZombies() {
  procCleanLoading.value = true
  try {
    const res = await api.post('/ops/processes/cleanup', { category: 'zombies' })
    procCleanResult.value = res.cleaned > 0
      ? `成功清理 ${res.cleaned} 个僵尸进程`
      : '无僵尸进程需要清理'
    loadProcessSummary()
  } catch (e) {
    procCleanResult.value = '清理失败: ' + (e.message || '未知')
  } finally {
    procCleanLoading.value = false
  }
}

async function systemOptimize() {
  optimizeLoading.value = true
  try {
    const res = await api.post('/ops/system/optimize')
    const actions = (res.actions || []).map(a => `${a.action}: ${a.count || a.ok || a.found || '完成'}`)
    optimizeResult.value = '优化完成 — ' + actions.join(' | ')
    loadProcessSummary()
  } catch (e) {
    optimizeResult.value = '优化失败: ' + (e.message || '未知')
  } finally {
    optimizeLoading.value = false
  }
}

async function loadCpuInfo() {
  cpuInfoLoading.value = true
  try {
    cpuInfo.value = await api.get('/ops/cpu/info')
  } catch (e) {
    stressResult.value = 'CPU 信息获取失败: ' + (e.message || '未知')
  } finally {
    cpuInfoLoading.value = false
  }
}

async function runStress(duration) {
  stressLoading.value = true
  stressResult.value = `正在执行 ${duration} 秒全核压测...`
  try {
    const res = await api.post('/ops/cpu/stress', null, { params: { duration, cores: 0 } })
    stressResult.value = `压测完成: ${res.cores} 核心 × ${res.duration}秒 — ${res.output?.slice(0, 200) || 'OK'}`
    loadCpuInfo()
  } catch (e) {
    stressResult.value = '压测失败: ' + (e.message || '未知')
  } finally {
    stressLoading.value = false
  }
}

async function runRootCause() {
  rcaLoading.value = true
  try {
    const res = await api.get('/perception/root-cause')
    rcaReport.value = res
  } catch (e) {
    rcaReport.value = { has_issues: false, findings: [], summary: '分析失败: ' + (e.message || '未知错误') }
  } finally {
    rcaLoading.value = false
  }
}

async function loadOsData() {
  try {
    const [ports, zombies, journal] = await Promise.all([
      api.get('/perception/os/ports').catch(() => ({ ports: [] })),
      api.get('/perception/os/zombies').catch(() => ({ zombie_count: 0 })),
      api.get('/perception/os/journal', { params: { priority: 'err', lines: 10, since: '30min ago' } }).catch(() => ({ entries: [] })),
    ])
    osPorts.value = ports.ports || []
    osZombies.value = zombies
    osErrors.value = journal.entries || []
  } catch {}
}

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

    // 加载 OS 深度感知 + 进程/CPU 数据
    loadOsData()
    loadProcessSummary()
    loadCpuInfo()
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

/* 根因分析卡片样式 */
.rca-card { min-height: 300px; }
.rca-finding {
  padding: 10px;
  margin-bottom: 10px;
  border-radius: 6px;
  background: #fafafa;
  border-left: 3px solid #E6A23C;
}
.rca-finding:last-child { margin-bottom: 0; }
.rca-title { font-weight: 600; margin: 6px 0 4px; font-size: 14px; }
.rca-cause { color: #666; font-size: 13px; margin-bottom: 6px; }
.rca-actions { display: flex; flex-direction: column; gap: 2px; }
.rca-action-tag { font-size: 12px; color: #409EFF; }

/* OS 感知面板样式 */
.os-card { min-height: 300px; }
.os-error-line {
  font-size: 12px;
  color: #999;
  padding: 2px 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>