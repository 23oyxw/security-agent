<template>
  <div>
    <ArchitectureLayers highlight="L2" />
    <el-card header="Skill 流程（L2）— 确定性多步编排" style="margin-bottom: 16px">
      <el-alert type="success" :closable="false" show-icon style="margin-bottom: 12px"
        title="本页 = L2 固定步骤。智能助手（L3）说「生成扫描报告」也会调用同一 REST API。" />
      <el-button type="primary" @click="loadFlows" :loading="loading">刷新列表</el-button>
      <el-table :data="flows" v-loading="loading" stripe style="margin-top: 12px">
        <el-table-column prop="display_name" label="名称" width="150" />
        <el-table-column prop="name" label="ID" width="130" />
        <el-table-column prop="description" label="说明" min-width="200" />
        <el-table-column label="步骤链" min-width="220">
          <template #default="{ row }">
            <el-tag v-for="s in row.steps || []" :key="s" size="small" style="margin:2px">{{ s }}</el-tag>
            <span v-if="!row.steps?.length" style="color:#999">{{ row.step_count }} 步</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="selectFlow(row)">运行</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card v-if="selected" :header="`运行：${selected.display_name} (${selected.name})`">
      <p v-if="selected.description" style="color:#666;font-size:13px;margin:0 0 12px">{{ selected.description }}</p>
      <el-form label-width="110px" style="max-width: 680px">
        <el-form-item v-if="selected.name === 'scan_report'" label="说明">
          <span style="font-size:13px;color:#606266">无需参数，将依次：进程扫描 → 端口暴露 → 健康摘要 → 文本报告 → HTML 文件</span>
        </el-form-item>
        <el-form-item v-if="selected.name === 'secure_exec'" label="命令">
          <el-input v-model="form.command" placeholder="例: ls -la /tmp" />
        </el-form-item>
        <el-form-item v-if="selected.name === 'secure_exec'" label="用户意图">
          <el-input v-model="form.user_message" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item v-if="selected.name === 'secure_exec'" label="已确认">
          <el-switch v-model="form.user_confirmed" />
        </el-form-item>
        <el-form-item v-if="selected.name === 'alert_response'" label="告警描述">
          <el-input v-model="form.alert_message" type="textarea" :rows="3" placeholder="模拟告警内容" />
        </el-form-item>
        <el-form-item v-if="selected.name === 'alert_response'" label="告警级别">
          <el-select v-model="form.alert_level" style="width:120px">
            <el-option label="严重" value="严重" />
            <el-option label="高" value="高" />
            <el-option label="中" value="中" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="selected.name === 'block_process'" label="PID">
          <el-input-number v-model="form.pid" :min="1" :max="999999" controls-position="right" />
        </el-form-item>
        <el-form-item v-if="selected.name === 'block_process'" label="强制拦截">
          <el-switch v-model="form.force" />
          <span style="margin-left:8px;font-size:12px;color:#909399">非高危进程需开启</span>
        </el-form-item>
        <el-form-item v-if="selected.name === 'block_process'" label="说明">
          <el-input v-model="form.user_message" placeholder="可选，如：拦截进程 4911" />
        </el-form-item>
        <el-form-item v-if="selected.name === 'system_cleanup'" label="清理分类">
          <el-checkbox-group v-model="form.cleanup_categories">
            <el-checkbox label="apt">APT 缓存</el-checkbox>
            <el-checkbox label="journal">Journal 日志</el-checkbox>
            <el-checkbox label="log">旧日志文件</el-checkbox>
            <el-checkbox label="tmp">/tmp 旧文件</el-checkbox>
            <el-checkbox label="pip">pip 缓存</el-checkbox>
            <el-checkbox label="docker">Docker 悬空</el-checkbox>
            <el-checkbox label="kernel">旧内核</el-checkbox>
            <el-checkbox label="trash">回收站</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item v-if="selected.name === 'system_cleanup'" label="高风险项">
          <el-switch v-model="form.cleanup_confirm_all" />
          <span style="margin-left:8px;font-size:12px;color:#909399">确认执行 tmp/docker/kernel/trash 清理</span>
        </el-form-item>
        <el-form-item v-if="selected.name === 'cpu_stress'" label="压测模式">
          <el-select v-model="form.stress_mode" style="width:140px">
            <el-option label="单核" value="single" />
            <el-option label="多核" value="multi" />
            <el-option label="满载" value="full" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="selected.name === 'cpu_stress'" label="最大时长(秒)">
          <el-input-number v-model="form.stress_duration" :min="5" :max="300" :step="5" />
        </el-form-item>
        <el-form-item v-if="selected.name === 'cpu_stress'" label="自动停止阈值(%)">
          <el-input-number v-model="form.stress_threshold" :min="50" :max="98" :step="5" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="runFlow" :loading="running">执行流程</el-button>
          <el-button @click="selected = null">取消</el-button>
        </el-form-item>
      </el-form>

      <template v-if="result">
        <el-divider />
        <div class="result-header">
          <el-tag :type="result.ok ? 'success' : 'danger'">{{ result.ok ? '成功' : '失败' }}</el-tag>
          <span class="trace">Trace: {{ result.trace_id }}</span>
          <span class="time" :title="result.started_at ? `开始 ${result.started_at}` : ''">
            {{ formatFlowTime(result.finished_at) }}
          </span>
        </div>

        <el-steps v-if="result.steps?.length" :active="result.steps.length" finish-status="success" style="margin:16px 0">
          <el-step
            v-for="(st, i) in result.steps"
            :key="i"
            :title="stepTitle(st, i)"
            :status="st.ok === false ? 'error' : 'success'"
            :description="stepDesc(st)"
          />
        </el-steps>

        <el-card v-if="result.report" shadow="never" class="report-card">
          <template #header>文本报告</template>
          <pre class="report-text">{{ result.report }}</pre>
        </el-card>

        <div v-if="result.report || result.report_html_path" class="report-actions">
          <el-button v-if="result.report" type="primary" size="small" @click="downloadTextReport">下载文本报告 (.txt)</el-button>
          <el-button v-if="result.report_html_path" type="success" size="small" @click="openHtmlReport">打开 HTML 报告</el-button>
          <el-button v-if="result.report_html_path" size="small" @click="downloadHtmlReport">下载 HTML</el-button>
        </div>
        <el-alert
          v-else-if="result.ok && selected?.name === 'scan_report'"
          type="info"
          :closable="false"
          show-icon
          style="margin-top:12px"
          title="流程已完成，但未返回报告正文（可查看下方步骤或 JSON 调试）"
        />

        <el-collapse style="margin-top:12px">
          <el-collapse-item title="原始 JSON（仅调试，日常请用上方下载）" name="json">
            <pre class="result-box">{{ JSON.stringify(result, null, 2) }}</pre>
          </el-collapse-item>
        </el-collapse>
      </template>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api'
import { ElMessage } from 'element-plus'
import ArchitectureLayers from '../components/ArchitectureLayers.vue'
import { basename, downloadBlob, fetchWithAuth } from '../utils/download'
import { formatBeijingTime } from '../utils/formatTime'

const STEP_LABELS = {
  security_scan: '进程/路径扫描',
  exposed_ports: '端口暴露',
  system_health: '系统健康',
  text_report: '文本报告',
  html_report: 'HTML 报告',
  safety_evaluate: '三层防御',
  terminal_exec: '安全执行',
  route_alert: '告警路由',
  block_process: '进程拦截',
  cleanup_scan: '扫描可清理项',
  cleanup_run: '执行清理',
  cpu_stress: '启动压测',
  cpu_stop: '停止压测',
}

const route = useRoute()
const flows = ref([])
const loading = ref(false)
const running = ref(false)
const selected = ref(null)
const result = ref(null)
const form = reactive({
  command: 'ls -la /tmp',
  user_message: '查看临时目录',
  user_confirmed: false,
  alert_message: 'CPU 使用率持续高于 90%',
  alert_level: '高',
  alert_occurred_at: '',
  pid: 4911,
  force: false,
  cleanup_categories: ['apt', 'journal', 'log'],
  cleanup_confirm_all: false,
  stress_mode: 'multi',
  stress_duration: 60,
  stress_threshold: 85,
})

async function loadFlows() {
  loading.value = true
  try {
    const res = await api.get('/skills/flows/')
    flows.value = res.flows || []
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function selectFlow(row) {
  selected.value = row
  result.value = null
}

function buildContext() {
  const name = selected.value?.name
  if (name === 'secure_exec') {
    return {
      command: form.command,
      user_message: form.user_message,
      user_confirmed: form.user_confirmed,
    }
  }
  if (name === 'alert_response') {
    const ev = {
      message: form.alert_message,
      source: 'skill_flows_page',
      level: form.alert_level || '高',
    }
    if (form.alert_occurred_at) ev.ts = form.alert_occurred_at
    return { alert_event: ev }
  }
  if (name === 'block_process') {
    return {
      pid: form.pid,
      force: form.force,
      user_message: form.user_message || `拦截进程 ${form.pid}`,
    }
  }
  if (name === 'system_cleanup') {
    return {
      categories: form.cleanup_categories,
      confirm_all: form.cleanup_confirm_all,
    }
  }
  if (name === 'cpu_stress') {
    return {
      mode: form.stress_mode,
      duration: form.stress_duration,
      threshold: form.stress_threshold,
    }
  }
  return {}
}

function stepTitle(st, index) {
  const key = st.step || `step_${index}`
  return STEP_LABELS[key] || key
}

function formatFlowTime(v) {
  if (!v) return '—'
  return formatBeijingTime(v)
}

function stepDesc(st) {
  if (st.duration_ms != null) {
    const base = st.error || (st.ok === false ? '失败' : '完成')
    return `${base} · ${st.duration_ms}ms`
  }
  if (st.error) return st.error
  if (st.path) return st.path
  if (st.report_len != null) return `长度 ${st.report_len}`
  if (st.risk_count != null) return `风险 ${st.risk_count}`
  if (st.risky_count != null) return `暴露 ${st.risky_count}`
  if (st.message) return String(st.message).slice(0, 80)
  return st.ok === false ? '失败' : '完成'
}

async function runFlow() {
  if (!selected.value) return
  running.value = true
  result.value = null
  try {
    result.value = await api.post(`/skills/flows/${selected.value.name}/run`, {
      context: buildContext(),
    })
    ElMessage.success(result.value.ok ? '流程完成' : '流程未完全成功')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message || '执行失败')
  } finally {
    running.value = false
  }
}

function downloadTextReport() {
  const text = result.value?.report
  if (!text) {
    ElMessage.warning('无文本报告')
    return
  }
  const ts = (result.value.finished_at || '').replace(/\D/g, '').slice(0, 14) || 'report'
  downloadBlob(text, `scan-report-${ts}.txt`)
  ElMessage.success('已下载文本报告')
}

async function openHtmlReport() {
  const fn = basename(result.value?.report_html_path)
  if (!fn) {
    ElMessage.warning('无 HTML 路径')
    return
  }
  try {
    const res = await fetchWithAuth(`/api/reports/files/${fn}`)
    if (!res.ok) throw new Error('报告文件不存在')
    const html = await res.text()
    const w = window.open('', '_blank')
    if (w) {
      w.document.write(html)
      w.document.close()
    } else {
      downloadBlob(html, fn, 'text/html;charset=utf-8')
      ElMessage.info('弹窗被拦截，已改为下载 HTML')
    }
  } catch (e) {
    ElMessage.error(e.message || '打开失败')
  }
}

async function downloadHtmlReport() {
  const fn = basename(result.value?.report_html_path)
  if (!fn) return
  try {
    const res = await fetchWithAuth(`/api/reports/files/${fn}`)
    if (!res.ok) throw new Error('报告不存在')
    downloadBlob(await res.text(), fn, 'text/html;charset=utf-8')
    ElMessage.success('已下载 HTML')
  } catch (e) {
    ElMessage.error(e.message || '下载失败')
  }
}

function applyRouteQuery() {
  const q = route.query
  if (q.message) form.alert_message = String(q.message)
  if (q.severity === 'critical') form.alert_level = '严重'
  else if (q.severity === 'high') form.alert_level = '高'
  const flowName = q.flow ? String(q.flow) : ''
  if (!flowName || !flows.value.length) return
  const row = flows.value.find(f => f.name === flowName)
  if (row) selectFlow(row)
}

onMounted(async () => {
  await loadFlows()
  applyRouteQuery()
})
</script>

<style scoped>
.report-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.result-header { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; font-size: 13px; }
.trace { color: #409eff; }
.time { color: #909399; }
.report-card { margin-top: 8px; }
.report-text {
  white-space: pre-wrap;
  font-size: 13px;
  line-height: 1.6;
  margin: 0;
  max-height: 360px;
  overflow: auto;
}
.result-box {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 8px;
  font-size: 12px;
  max-height: 400px;
  overflow: auto;
}
</style>
