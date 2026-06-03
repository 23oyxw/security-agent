<template>
  <div>
    <el-row :gutter="16">
      <el-col :span="14">
        <el-card>
          <template #header>
            <span>⚡ 安全执行器</span>
          </template>

          <el-form :model="form" label-width="80px" @submit.prevent="execute">
            <el-form-item label="命令">
              <el-input v-model="form.command" placeholder="输入要执行的命令，例如: ls -la /tmp" clearable size="large" />
            </el-form-item>
            <el-form-item label="模式">
              <el-radio-group v-model="form.sandbox">
                <el-radio-button :value="true">沙箱模式</el-radio-button>
                <el-radio-button :value="false">直接执行</el-radio-button>
              </el-radio-group>
              <el-tag v-if="!form.sandbox" type="danger" size="small" style="margin-left:8px">⚠️ 危险</el-tag>
            </el-form-item>
            <el-form-item v-if="previewRisk" label="预估风险">
              <el-tag :type="riskColor(previewRisk)" effect="dark" size="small">
                {{ normRisk(previewRisk) }}（{{ previewRiskLabel || RISK_CN[normRisk(previewRisk)] }}）
              </el-tag>
              <span style="margin-left:8px;font-size:12px;color:#999">执行后以下方结果为准</span>
            </el-form-item>
            <el-form-item label="超时">
              <el-input-number v-model="form.timeout" :min="5" :max="120" :step="5" />
              <span style="margin-left:8px;color:#999">秒</span>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="executing" @click="execute" :disabled="!form.command.trim()">
                <el-icon><CaretRight /></el-icon> 执行
              </el-button>
              <el-button @click="form.command = ''">清空</el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <!-- 执行结果 -->
        <el-card v-if="result" style="margin-top:16px">
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span>执行结果</span>
              <el-tag :type="result.success ? 'success' : 'danger'" size="small">
                {{ result.success ? '成功' : '失败' }} · {{ result.duration_ms?.toFixed(0) || 0 }}ms
              </el-tag>
            </div>
          </template>
          <div class="output-box" :class="result.success ? 'success' : 'error'">
            <pre>{{ result.output || result.error || '（无输出）' }}</pre>
          </div>
          <div class="risk-bar">
            <el-tag :type="riskColor(result.risk_level)" size="small" effect="dark">
              风险等级: {{ riskDisplay(result) }}
            </el-tag>
            <el-tag v-if="result.execution_mode" size="small" type="info" style="margin-left:8px">
              {{ result.execution_mode === 'sandbox' ? '沙箱执行' : '直接执行' }}
            </el-tag>
            <el-tag v-if="result.rollback_id" type="warning" size="small" style="margin-left:8px">
              可回滚: {{ result.rollback_id }}
            </el-tag>
          </div>
        </el-card>
      </el-col>

      <el-col :span="10">
        <el-card header="执行历史" style="margin-bottom:16px">
          <div v-for="(h, i) in history" :key="i" class="history-item" @click="form.command = h.command">
            <div style="display:flex;align-items:center;gap:6px">
              <el-icon :color="h.success ? '#67C23A' : '#F56C6C'" :size="14">
                <component :is="h.success ? 'CircleCheckFilled' : 'CircleCloseFilled'" />
              </el-icon>
              <code style="font-size:12px;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ h.command }}</code>
              <span style="font-size:11px;color:#999">{{ h.duration_ms?.toFixed(0) }}ms</span>
            </div>
          </div>
          <el-empty v-if="!history.length" description="暂无执行记录" :image-size="40" />
        </el-card>

        <el-card header="📖 命令库" style="margin-bottom:16px">
          <div style="display:flex;gap:4px;margin-bottom:8px;flex-wrap:wrap">
            <el-radio-group v-model="execCategory" size="small">
              <el-radio-button value="">全部</el-radio-button>
              <el-radio-button value="system">🖥️ 系统</el-radio-button>
              <el-radio-button value="process">⚙️ 进程</el-radio-button>
              <el-radio-button value="network">🌐 网络</el-radio-button>
              <el-radio-button value="disk">💾 磁盘</el-radio-button>
              <el-radio-button value="security">🔒 安全</el-radio-button>
            </el-radio-group>
          </div>
          <div class="quick-cmds">
            <el-button v-for="cmd in filteredExecCmds" :key="cmd.cmd" size="small" @click="form.command = cmd.cmd" :type="cmd.type || ''">
              {{ cmd.label }}
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, watch, computed } from 'vue'
import api from '../api'
import { ElMessage } from 'element-plus'

const form = reactive({ command: '', sandbox: true, timeout: 30 })
const result = ref(null)
const executing = ref(false)
const history = ref([])
const previewRisk = ref('')
const previewRiskLabel = ref('')
const execCategory = ref('')

const quickCmds = [
  { label: '磁盘空间', cmd: 'df -h', type: '' },
  { label: '内存使用', cmd: 'free -h', type: '' },
  { label: '系统负载', cmd: 'uptime', type: '' },
  { label: '网络连接', cmd: 'ss -tlnp', type: '' },
  { label: '最近登录', cmd: 'last -10', type: '' },
  { label: '进程TOP10', cmd: 'ps aux --sort=-%cpu | head -11', type: '' },
]

const execCmdLibrary = [
  { cat: 'system', label: '系统版本', cmd: 'uname -a' },
  { cat: 'system', label: '发行版', cmd: 'cat /etc/os-release' },
  { cat: 'system', label: '运行时间', cmd: 'uptime' },
  { cat: 'system', label: '内存', cmd: 'free -h' },
  { cat: 'system', label: '磁盘', cmd: 'df -h' },
  { cat: 'system', label: 'CPU信息', cmd: 'lscpu' },
  { cat: 'system', label: '系统负载', cmd: 'top -bn1 | head -20' },
  { cat: 'process', label: 'CPU Top', cmd: 'ps aux --sort=-%cpu | head -11' },
  { cat: 'process', label: '内存Top', cmd: 'ps aux --sort=-%mem | head -11' },
  { cat: 'process', label: '僵尸进程', cmd: 'ps aux | grep -i zombie' },
  { cat: 'process', label: '进程树', cmd: 'ps -ef --forest | head -30' },
  { cat: 'network', label: '监听端口', cmd: 'ss -tlnp' },
  { cat: 'network', label: '连接统计', cmd: 'ss -s' },
  { cat: 'network', label: '网络接口', cmd: 'ip addr show' },
  { cat: 'network', label: '路由表', cmd: 'ip route show' },
  { cat: 'network', label: '防火墙', cmd: 'iptables -L -n --line-numbers' },
  { cat: 'network', label: '最近登录', cmd: 'last -20' },
  { cat: 'network', label: '当前用户', cmd: 'who' },
  { cat: 'network', label: '失败登录', cmd: 'lastb -10' },
  { cat: 'disk', label: '日志大小', cmd: 'du -sh /var/log/*' },
  { cat: 'disk', label: '临时文件', cmd: 'du -sh /tmp/*' },
  { cat: 'disk', label: '大文件', cmd: 'find / -size +100M -type f 2>/dev/null' },
  { cat: 'disk', label: '打开文件', cmd: 'lsof +D /var/log 2>/dev/null' },
  { cat: 'security', label: '可登录用户', cmd: 'cat /etc/passwd | grep -v nologin' },
  { cat: 'security', label: 'SUID文件', cmd: 'find / -perm -4000 -type f 2>/dev/null' },
  { cat: 'security', label: '计划任务', cmd: 'crontab -l' },
  { cat: 'security', label: '系统crontab', cmd: 'cat /etc/crontab' },
  { cat: 'security', label: '运行服务', cmd: 'systemctl list-units --type=service --state=running' },
]

const filteredExecCmds = computed(() => {
  if (!execCategory.value) return quickCmds
  return execCmdLibrary.filter(c => c.cat === execCategory.value)
})

const RISK_CN = { READONLY: '只读', REVERSIBLE: '可逆', IRREVERSIBLE: '不可逆', CRITICAL: '关键' }

function normRisk(r) {
  return String(r || 'READONLY').toUpperCase()
}

function riskColor(r) {
  const k = normRisk(r)
  return { CRITICAL: 'danger', IRREVERSIBLE: 'danger', REVERSIBLE: 'warning', READONLY: 'success' }[k] || 'info'
}

function riskDisplay(resOrLevel) {
  if (resOrLevel && typeof resOrLevel === 'object') {
    const lv = normRisk(resOrLevel.risk_level)
    return resOrLevel.risk_label ? `${lv}（${resOrLevel.risk_label}）` : `${lv}（${RISK_CN[lv] || lv}）`
  }
  const lv = normRisk(resOrLevel)
  return `${lv}（${RISK_CN[lv] || lv}）`
}

let previewTimer = null
watch(() => form.command, (cmd) => {
  clearTimeout(previewTimer)
  if (!cmd?.trim()) {
    previewRisk.value = ''
    previewRiskLabel.value = ''
    return
  }
  previewTimer = setTimeout(async () => {
    try {
      const res = await api.get('/executor/assess-risk', { params: { command: cmd.trim() } })
      previewRisk.value = res.risk_level
      previewRiskLabel.value = res.risk_label
    } catch {
      previewRisk.value = ''
    }
  }, 400)
})

async function execute() {
  if (!form.command.trim()) return
  executing.value = true
  result.value = null
  try {
    const res = await api.post('/executor/execute', {
      command: form.command.trim(),
      sandbox: form.sandbox,
      timeout: form.timeout,
    })
    result.value = res
    history.value.unshift({
      command: form.command.trim(),
      success: res.success,
      duration_ms: res.duration_ms,
      timestamp: Date.now(),
    })
    if (history.value.length > 20) history.value = history.value.slice(0, 20)
    if (res.success) ElMessage.success('执行成功')
    else ElMessage.warning('执行完成（有错误）')
  } catch (e) {
    const err = { success: false, output: '', error: e.response?.data?.detail || e.message, duration_ms: 0 }
    result.value = err
    history.value.unshift({ command: form.command.trim(), ...err, timestamp: Date.now() })
    ElMessage.error('执行失败')
  } finally { executing.value = false }
}
</script>

<style scoped>
.output-box { background: #1e1e1e; color: #d4d4d4; border-radius: 8px; padding: 16px; max-height: 400px; overflow-y: auto; }
.output-box.error { background: #2d1b1b; }
.output-box pre { margin: 0; font-family: 'Fira Code', 'Consolas', monospace; font-size: 13px; line-height: 1.5; white-space: pre-wrap; word-break: break-all; }
.history-item { padding: 6px 8px; border-radius: 4px; cursor: pointer; margin-bottom: 4px; transition: background 0.2s; }
.history-item:hover { background: #f5f7fa; }
.quick-cmds { display: flex; flex-wrap: wrap; gap: 8px; }
.risk-bar { margin-top: 8px; display: flex; flex-wrap: wrap; align-items: center; gap: 4px; }
</style>