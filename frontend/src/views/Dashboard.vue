<template>
  <div class="dashboard-root">
    <!-- 左侧操作抽屉 -->
    <aside class="ops-drawer" :class="{ collapsed: drawerClosed }">
      <div class="drawer-toggle" @click="drawerClosed = !drawerClosed">
        <el-icon :size="18"><component :is="drawerClosed ? 'Expand' : 'Fold'" /></el-icon>
      </div>
      <div v-if="!drawerClosed" class="drawer-body">
        <!-- 分组1: 快捷操作 -->
        <el-collapse v-model="activeDrawerGroups">
          <el-collapse-item title="⚡ 快捷操作" name="ops">
            <div class="drawer-section">
              <div class="drawer-section-title">CPU 压测</div>
              <div style="display:flex;gap:4px">
                <el-button size="small" type="danger" :loading="stressLoading" @click="runStress(10)">10s</el-button>
                <el-button size="small" type="danger" :loading="stressLoading" @click="runStress(30)">30s</el-button>
              </div>
              <div v-if="stressResult" class="drawer-result">{{ stressResult.split('\n')[0] }}</div>
            </div>
            <div class="drawer-section">
              <div class="drawer-section-title">进程管理</div>
              <div style="display:flex;gap:4px">
                <el-button size="small" :loading="procLoading" @click="refreshProc">刷新</el-button>
              </div>
              <div v-if="procSummary" class="drawer-result">
                {{ procSummary.total_processes }} 进程 · {{ procSummary.zombies || 0 }} 僵尸
              </div>
            </div>
          </el-collapse-item>

          <!-- 分组2: 筛选与配置 -->
          <el-collapse-item title="📊 数据筛选" name="filter">
            <div class="drawer-section">
              <div class="drawer-section-title">告警级别</div>
              <el-select v-model="alertFilter" size="small" style="width:100%">
                <el-option label="全部" value="" />
                <el-option label="严重" value="critical" />
                <el-option label="高" value="high" />
                <el-option label="中" value="medium" />
              </el-select>
            </div>
            <div class="drawer-section">
              <div class="drawer-section-title">刷新间隔</div>
              <el-select v-model="pollSec" size="small" style="width:100%">
                <el-option label="5 秒" :value="5" />
                <el-option label="10 秒" :value="10" />
                <el-option label="30 秒" :value="30" />
              </el-select>
            </div>
            <div class="drawer-section">
              <el-button size="small" icon="Refresh" @click="fetchAll" style="width:100%">立即刷新</el-button>
            </div>
          </el-collapse-item>

          <!-- 分组3: 辅助明细 -->
          <el-collapse-item title="📁 辅助明细" name="detail">
            <div class="drawer-section">
              <div class="drawer-section-title">监听端口 (Top 10)</div>
              <div v-for="p in osPorts.slice(0,10)" :key="p.port" class="port-line">
                <code>{{ p.port }}</code> {{ p.process?.slice(0,30) }}
              </div>
              <div v-if="!osPorts.length" style="font-size:11px;color:#999">加载中...</div>
            </div>
            <div class="drawer-section">
              <div class="drawer-section-title">可用模块</div>
              <div style="display:flex;flex-wrap:wrap;gap:4px">
                <el-tag v-for="(v,k) in modules" :key="k" size="small" :type="v==='active'?'success':'danger'" effect="plain">{{ k }}</el-tag>
              </div>
            </div>
            <div class="drawer-section">
              <el-button size="small" text type="primary" @click="$router.push('/trace')" style="width:100%">查看 Trace →</el-button>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>
    </aside>

    <!-- 主内容区 -->
    <main class="main-content">
      <!-- 顶部 6 指标卡 -->
      <div class="metric-cards">
        <div class="metric-card" v-for="s in statCards" :key="s.key">
          <div class="metric-card-value" :style="{color:s.color}">{{ s.value }}</div>
          <div class="metric-card-label">{{ s.label }}</div>
          <div class="metric-card-sub">{{ s.sub }}</div>
        </div>
      </div>

      <!-- 核心图表行 -->
      <el-row :gutter="12" style="margin-bottom:12px">
        <el-col :span="12">
          <el-card header="系统资源" shadow="never" class="panel-card">
            <div ref="resourceBar" style="height:180px"></div>
            <div style="text-align:center;font-size:11px;color:var(--color-neutral-400);margin-top:4px">
              {{ loadStr }} — {{ loadTip }}
            </div>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card header="Agent 评估" shadow="never" class="panel-card">
            <div v-if="evalScore" class="eval-panel">
              <div class="eval-grade" :class="'grade-' + evalScore.grade">{{ evalScore.grade }}</div>
              <div class="eval-composite">{{ evalScore.composite }} 分</div>
              <div class="eval-label" style="margin-bottom:6px">综合评估 · {{ evalScore.total_evaluations || '—' }} 次</div>
              <div style="display:flex;gap:6px;flex-wrap:wrap;justify-content:center">
                <span v-for="(v,k) in evalDims" :key="k" class="eval-dim">
                  <span class="eval-dim-name">{{ k === 'success_rate' ? '成功率' : k === 'safety_compliance' ? '安全合规' : k === 'efficiency_ratio' ? '效率比' : k === 'step_efficiency' ? '步骤效率' : '稳定性' }}</span>
                  <el-progress :percentage="v" :stroke-width="4" :show-text="false" :color="v>70?'#67C23A':v>40?'#E6A23C':'#F56C6C'" style="width:50px" />
                  <span style="font-size:9px">{{ v }}</span>
                </span>
              </div>
              <div style="display:flex;justify-content:center;gap:16px;margin-top:8px;font-size:11px;color:var(--color-neutral-500)">
                <span>Token: {{ evalScore.tokens || '—' }}</span>
                <span>效率比: {{ evalScore.efficiency_ratio || '—' }}</span>
                <span>Trace: {{ traceMetrics.avg_stages || '—' }}阶 · {{ traceMetrics.avg_duration_ms ? (traceMetrics.avg_duration_ms/1000).toFixed(1)+'s' : '—' }}</span>
              </div>
              <div v-if="trendPoints?.length" style="margin-top:8px;display:flex;align-items:flex-end;gap:2px;justify-content:center;height:32px">
                <div v-for="(p,i) in trendPoints" :key="i"
                     :title="'#'+p.n+' '+p.score+'分 '+p.tokens+'tokens'"
                     :style="{height: Math.max(4, p.score/100*28)+'px', width: '12px', background: p.grade==='A'?'#10b981':p.grade==='B'?'#3b82f6':p.grade==='C'?'#f59e0b':'#ef4444', borderRadius: '2px', opacity: 0.8, transition: 'height .3s' }"></div>
              </div>
              <div style="font-size:9px;color:var(--color-neutral-400)">mini 趋势 (最近 10 次, 每柱=单次评分)</div>
            </div>
            <el-empty v-else description="Agent 对话后自动评估" :image-size="40" style="padding:20px 0" />
          </el-card>
        </el-col>
      </el-row>

      <!-- 压测结果 -->
      <el-alert v-if="stressResult" type="info" :closable="false" style="margin-bottom:12px;white-space:pre-line;font-size:12px">
        {{ stressResult }}
      </el-alert>

      <!-- 一键测试面板 (折叠) -->
      <el-collapse style="margin-bottom:12px">
        <el-collapse-item title="⚡ Skill Flow 一键测试" name="test">
          <div style="display:flex;flex-wrap:wrap;gap:8px">
            <div v-for="tc in testCases" :key="tc.key" style="display:flex;align-items:center;gap:6px;padding:4px 10px;background:#fafafa;border-radius:6px;font-size:12px">
              <span style="font-weight:600;min-width:80px">{{ tc.label }}</span>
              <span style="color:#999;max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ tc.description }}</span>
              <el-tag v-if="tc.status==='ok'" type="success" size="small">✓</el-tag>
              <el-tag v-else-if="tc.status==='blocked'" type="warning" size="small">⊘</el-tag>
              <el-tag v-else-if="tc.status==='fail'" type="danger" size="small">✗</el-tag>
              <span v-else style="color:#ccc">—</span>
              <el-button size="small" text type="primary" :loading="tc.status==='running'" @click="runSingleTest(tc)">测试</el-button>
            </div>
          </div>
          <div style="text-align:center;margin-top:8px">
            <el-button type="primary" size="small" :loading="testAllLoading" @click="runAllTests">全部运行</el-button>
          </div>
        </el-collapse-item>
      </el-collapse>

      <!-- 最近告警 -->
      <el-card header="最近告警" shadow="never" class="panel-card">
        <el-table :data="alerts.slice(0,5)" size="small" stripe empty-text="暂无告警">
          <el-table-column prop="timestamp" label="时间" width="150" />
          <el-table-column prop="level" label="级别" width="60">
            <template #default="{row}"><el-tag :type="sevColor(row.level)" size="small">{{ row.level }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="message" label="内容" show-overflow-tooltip />
        </el-table>
        <div style="text-align:right;margin-top:8px">
          <el-button text type="primary" @click="$router.push('/alerts')">告警管理 →</el-button>
        </div>
      </el-card>
    </main>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import api from '../api'
import { useAlertsStore } from '../stores/alerts'

const alertsStore = useAlertsStore()
const resourceBar = ref(null)
const drawerClosed = ref(false)
const activeDrawerGroups = ref(['ops'])
const alertFilter = ref('')
const pollSec = ref(10)
const alerts = ref([])
const modules = ref({})
const osPorts = ref([])
const procSummary = ref(null)
const procLoading = ref(false)
const stressLoading = ref(false)
const stressResult = ref('')
const testAllLoading = ref(false)
const evalScore = ref(null)
const evalDims = ref({})
const traceMetrics = ref({ avg_stages: 0, avg_duration_ms: 0, total_traces: 0 })
const trendPoints = ref([])
let pollTimer = null

const loadStr = ref('—')
const loadTip = ref('')

const statCards = reactive([
  { key:'cpu', label:'CPU', value:'--%', sub:'使用率', color:'#409EFF' },
  { key:'mem', label:'内存', value:'--%', sub:'已用', color:'#67C23A' },
  { key:'disk',label:'磁盘', value:'--%', sub:'使用率', color:'#E6A23C' },
  { key:'proc',label:'进程', value:'--', sub:'总数', color:'#8b5cf6' },
  { key:'load',label:'负载1m', value:'--', sub:'1/5/15min', color:'#f59e0b' },
  { key:'uptime',label:'运行', value:'--h', sub:'uptime', color:'#06b6d4' },
])

const testCases = reactive([
  { key:'scan', label:'安全扫描', flow:'scan_report', description:'进程/端口+报告', status:'', elapsed_ms:null },
  { key:'exec_safe', label:'安全命令', flow:'secure_exec', description:'ls (放行)', status:'', elapsed_ms:null, context:{command:'ls -la /tmp',user_message:'查看',user_confirmed:true} },
  { key:'exec_block', label:'拦截命令', flow:'secure_exec', description:'rm -rf / (拦截)', status:'', elapsed_ms:null, context:{command:'rm -rf /',user_message:'删除',user_confirmed:false} },
  { key:'cleanup_scan', label:'清理扫描', flow:'system_cleanup_scan', description:'扫描可清理', status:'', elapsed_ms:null },
  { key:'cleanup_run', label:'清理执行', flow:'system_cleanup_run', description:'apt/log', status:'', elapsed_ms:null, context:{categories:['apt','journal','log']} },
  { key:'alert', label:'告警响应', flow:'alert_response', description:'模拟告警路由', status:'', elapsed_ms:null, context:{alert_event:{message:'CPU>90%',level:'高'}} },
])

const progressColor = (p) => p > 85 ? '#F56C6C' : p > 70 ? '#E6A23C' : '#67C23A'
const sevColor = (s) => ({critical:'danger',high:'warning',medium:'',low:'info'}[String(s||'').toLowerCase()]||'info')

async function fetchAll() {
  try {
    const [flow, health, mcpRes, evalRes] = await Promise.all([
      api.get('/workflow/flow-status').catch(()=>null),
      api.get('/health').catch(()=>null),
      api.get('/mcp/servers').catch(()=>[]),
      api.get('/eval/score').catch(()=>null),
    ])
    if (health?.modules) modules.value = health.modules
    if (evalRes?.latest) {
      evalScore.value = { ...evalRes.latest, total_evaluations: evalRes.total_evaluations, efficiency_ratio: evalRes.efficiency_ratio }
      evalDims.value = evalRes.dimension_scores || {}
      traceMetrics.value = evalRes.trace_metrics || {}
      trendPoints.value = evalRes.trend_points || []
    }
    if (flow?.layers?.collection) {
      const ns = flow.layers.collection.nodes || []
      const byId = {}; ns.forEach(n=>byId[n.id]=n)
      statCards[0].value = byId.C1?.value || '0%'
      statCards[1].value = byId.C2?.value || '0%'
      statCards[2].value = byId.C3?.value || '0%'
      statCards[3].value = byId.C4?.value || '0'
      const lv = (byId.C1?.subtitle||'').replace('负载 ','').split(' ')
      statCards[4].value = lv[0] || '—'
      const ut = flow.uptime_seconds || 0
      statCards[5].value = `${Math.floor(ut/3600)}h${Math.floor((ut%3600)/60)}m`
      loadStr.value = lv.join(' / ')
      const cores = 8; const l1 = parseFloat(lv[0])||0
      loadTip.value = l1<=cores*.5?'轻载':l1<=cores*.8?'中载':l1<=cores*1.5?'高载':'过载'
    }
    await alertsStore.fetchRecent(5)
    alerts.value = alertsStore.recent || []
    nextTick(renderChart)
  } catch {}
}

async function refreshProc() {
  procLoading.value = true
  try { procSummary.value = await api.get('/ops/processes/summary') } catch {}
  finally { procLoading.value = false }
}

async function runStress(duration) {
  stressLoading.value = true
  stressResult.value = `⏳ ${duration}秒压测中...`
  try {
    const res = await api.post('/ops/cpu/stress', null, { params: { duration, cores: 0 } })
    const a = res.analysis || {}
    stressResult.value = [
      `🔬 ${a.summary || ''}`,
      a.bottlenecks?.length ? `⚠️ ${a.bottlenecks.join('; ')}` : '✅ 无瓶颈',
    ].join('\n')
    setTimeout(fetchAll, 2000)
  } catch (e) { stressResult.value = '压测失败: '+(e.message||'') }
  finally { stressLoading.value = false }
}

async function runSingleTest(tc) {
  tc.status = 'running'; const t0 = Date.now()
  try {
    const res = await api.post(`/skills/flows/${tc.flow}/run`, { context: tc.context || {} })
    tc.elapsed_ms = Date.now() - t0
    const blocked = (res.steps||[]).some(s=>s.blocked)
    tc.status = blocked ? 'blocked' : (res.ok ? 'ok' : 'fail')
  } catch { tc.status = 'fail'; tc.elapsed_ms = Date.now() - t0 }
}
async function runAllTests() { testAllLoading.value = true; for (const tc of testCases) await runSingleTest(tc); testAllLoading.value = false }

function renderChart() {
  if (!resourceBar.value) return
  const chart = echarts.init(resourceBar.value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { top:8, bottom:24, left:40, right:12 },
    xAxis: { type:'category', data:['CPU','内存','磁盘'] },
    yAxis: { type:'value', max:100, axisLabel:{ formatter:'{value}%' } },
    series: [{
      type:'bar', barWidth:50, label:{ show:true, position:'top', formatter:'{c}%' },
      data: [
        { value:parseFloat(statCards[0].value)||0, itemStyle:{ color:progressColor(parseFloat(statCards[0].value)||0), borderRadius:[4,4,0,0] } },
        { value:parseFloat(statCards[1].value)||0, itemStyle:{ color:progressColor(parseFloat(statCards[1].value)||0), borderRadius:[4,4,0,0] } },
        { value:parseFloat(statCards[2].value)||0, itemStyle:{ color:progressColor(parseFloat(statCards[2].value)||0), borderRadius:[4,4,0,0] } },
      ],
    }],
  })
}

onMounted(() => { fetchAll(); refreshProc(); pollTimer = setInterval(fetchAll, pollSec.value*1000) })
onUnmounted(() => { clearInterval(pollTimer) })
</script>

<style scoped>
.dashboard-root { display: flex; height: calc(100vh - var(--topbar-height, 56px)); overflow: hidden; }

/* 左侧抽屉 */
.ops-drawer {
  background: #fff; border-right: 1px solid var(--color-neutral-200);
  transition: width var(--duration-slow) var(--ease-out), opacity var(--duration-normal) var(--ease-out);
  flex-shrink: 0; overflow: hidden;
  width: 260px; display: flex; flex-direction: column;
}
.ops-drawer.collapsed { width: 40px; }
.drawer-toggle {
  display: flex; align-items: center; justify-content: center;
  height: 36px; cursor: pointer; color: var(--color-neutral-400);
  border-bottom: 1px solid var(--color-neutral-100);
  transition: color .15s;
}
.drawer-toggle:hover { color: var(--color-primary-500); }
.drawer-body { flex: 1; overflow-y: auto; padding: 6px 12px; }
.drawer-section { margin-bottom: 12px; }
.drawer-section-title { font-size: 11px; font-weight: 600; color: var(--color-neutral-500); margin-bottom: 6px; text-transform: uppercase; letter-spacing: .03em; }
.drawer-result { font-size: 11px; color: var(--color-neutral-500); margin-top: 6px; padding: 4px 8px; background: var(--color-neutral-50); border-radius: 4px; }
.port-line { font-size: 10px; padding: 2px 0; display: flex; gap: 6px; align-items: center; }
.port-line code { font-size: 10px; color: var(--color-primary-500); background: var(--color-primary-50); padding: 0 4px; border-radius: 2px; }

/* 主内容 */
.main-content {
  flex: 1; overflow-y: auto; padding: 12px 16px;
  max-width: 1200px; margin: 0 auto;
}

/* 指标卡片 */
.metric-cards {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 12px;
}
.metric-card {
  background: #fff; border: 1px solid var(--color-neutral-200);
  border-radius: var(--radius-lg); padding: 12px 14px; text-align: center;
  transition: all var(--duration-normal) var(--ease-out);
  cursor: default; position: relative; overflow: hidden;
  animation: slide-up var(--duration-normal) var(--ease-out) both;
}
.metric-card:nth-child(1) { animation-delay: 0ms; }
.metric-card:nth-child(2) { animation-delay: 50ms; }
.metric-card:nth-child(3) { animation-delay: 100ms; }
.metric-card:nth-child(4) { animation-delay: 150ms; }
.metric-card:nth-child(5) { animation-delay: 200ms; }
.metric-card:nth-child(6) { animation-delay: 250ms; }
.metric-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--shadow-lg);
  border-color: var(--color-primary-200);
}
/* 顶部色条 */
.metric-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: var(--color-primary-500);
  opacity: 0;
  transition: opacity var(--duration-fast) var(--ease-out);
}
.metric-card:hover::before {
  opacity: 1;
}
.metric-card-value { font-size: 22px; font-weight: 700; font-variant-numeric: tabular-nums; transition: color var(--duration-fast) var(--ease-out); }
.metric-card-label { font-size: 11px; font-weight: 600; color: var(--color-neutral-700); margin-top: 2px; }
.metric-card-sub { font-size: 10px; color: var(--color-neutral-400); }

/* 面板卡片 */
.panel-card { border: 1px solid var(--color-neutral-200); border-radius: var(--radius-lg); background: #fff; }

/* 评估面板 */
.eval-panel { text-align: center; padding: 12px 0; animation: fade-in var(--duration-slow) var(--ease-out); }
.eval-grade {
  display: inline-flex; align-items: center; justify-content: center;
  width: 48px; height: 48px; border-radius: 50%; font-size: 24px; font-weight: 800;
  color: #fff; margin-bottom: 4px;
  animation: scale-in var(--duration-normal) var(--ease-spring);
}
.grade-A { background: linear-gradient(135deg, #10b981, #34d399); }
.grade-B { background: linear-gradient(135deg, #3b82f6, #60a5fa); }
.grade-C { background: linear-gradient(135deg, #f59e0b, #fbbf24); }
.grade-D { background: linear-gradient(135deg, #f97316, #fb923c); }
.grade-F { background: linear-gradient(135deg, #ef4444, #f87171); }
.eval-composite { font-size: 18px; font-weight: 700; color: var(--color-neutral-800); }
.eval-label { font-size: 10px; color: var(--color-neutral-400); }
.eval-dim { display: flex; flex-direction: column; align-items: center; gap: 2px; }
.eval-dim-name { font-size: 9px; color: var(--color-neutral-500); }

@media (max-width: 900px) {
  .metric-cards { grid-template-columns: repeat(2, 1fr); }
  .ops-drawer { width: 220px; }
}
</style>
