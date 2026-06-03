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
              <el-autocomplete
                v-model="form.command"
                :fetch-suggestions="queryCommands"
                placeholder="输入命令或关键词搜索命令库"
                clearable
                size="large"
                style="width:100%"
                @select="onSelectCommand"
              >
                <template #default="{ item }">
                  <div style="display:flex;justify-content:space-between;align-items:center">
                    <span><code>{{ item.value }}</code></span>
                    <div style="display:flex;gap:4px;align-items:center">
                      <el-tag v-if="item.cat" size="small" type="info" effect="plain">{{ catLabelMap[item.cat] || item.cat }}</el-tag>
                      <el-tag :type="item.riskColor" size="small" effect="plain">{{ item.riskLabel }}</el-tag>
                    </div>
                  </div>
                </template>
              </el-autocomplete>
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
              <el-radio-button value="log">📋 日志</el-radio-button>
              <el-radio-button value="security">🔒 安全</el-radio-button>
              <el-radio-button value="service">🔧 服务</el-radio-button>
            </el-radio-group>
          </div>
          <el-input
            v-model="cmdSearch"
            placeholder="搜索命令或说明…"
            size="small"
            clearable
            style="margin-bottom:8px"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <div class="cmd-lib-list">
            <div
              v-for="cmd in filteredExecCmds"
              :key="cmd.cmd"
              class="cmd-lib-item"
              @click="form.command = cmd.cmd"
            >
              <div style="display:flex;align-items:center;justify-content:space-between;flex:1;min-width:0">
                <code style="font-size:12px;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ cmd.cmd }}</code>
                <el-tag :type="cmd.riskColor" size="small" effect="plain" style="margin-left:6px;flex-shrink:0">{{ cmd.riskLabel }}</el-tag>
              </div>
              <div style="font-size:11px;color:#999;margin-top:2px">{{ cmd.label }}</div>
            </div>
          </div>
          <el-empty v-if="!filteredExecCmds.length" description="无匹配命令" :image-size="40" />
        </el-card>

        <el-card header="🧠 安全知识库检索">
          <div style="display:flex;gap:6px;margin-bottom:10px;flex-wrap:wrap;align-items:center">
            <el-input
              v-model="kbQuery"
              placeholder="关键词：后门、SSH、Sigma"
              size="small"
              style="width:200px"
              clearable
              @keyup.enter="searchKb"
            >
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
            <el-button size="small" type="primary" @click="searchKb" :loading="kbLoading">检索</el-button>
          </div>
          <div style="display:flex;gap:4px;margin-bottom:8px;flex-wrap:wrap">
            <el-tag
              v-for="t in kbTags.slice(0, 8)"
              :key="t.name"
              :type="kbActiveTag === t.name ? '' : 'info'"
              :effect="kbActiveTag === t.name ? 'dark' : 'plain'"
              size="small"
              style="cursor:pointer"
              @click="toggleKbTag(t.name)"
            >{{ t.name }} ({{ t.count }})</el-tag>
          </div>
          <div v-if="kbResults.length" class="kb-list">
            <div v-for="item in kbResults" :key="item.id" class="kb-item" @click="toggleKbDetail(item)">
              <div style="display:flex;align-items:center;gap:6px">
                <el-tag :type="sevType(item.severity)" size="small">{{ item.severity }}</el-tag>
                <span style="font-weight:500;font-size:13px">{{ item.title }}</span>
                <el-tag v-if="item._score" size="small" type="success" effect="plain" style="margin-left:auto">{{ '★'.repeat(Math.min(item._score, 5)) }}</el-tag>
                <el-tag v-if="item.requires_root_confirm" size="small" type="danger" effect="dark" style="margin-left:2px">需Root确认</el-tag>
              </div>
              <div style="font-size:11px;color:#999;margin-top:2px;line-clamp:2;-webkit-line-clamp:2;display:-webkit-box;-webkit-box-orient:vertical;overflow:hidden">{{ item.body }}</div>
              <div style="margin-top:4px;display:flex;gap:3px;flex-wrap:wrap">
                <el-tag v-for="tag in item.threat_tags" :key="tag" size="small" type="info" effect="plain">{{ tag }}</el-tag>
              </div>
              <div v-if="kbDetailItem?.id === item.id" style="margin-top:8px;padding:8px;background:#f9f9f9;border-radius:4px;font-size:12px;line-height:1.6">
                <div v-if="item.suggested_actions?.length"><strong>建议操作：</strong>{{ item.suggested_actions.join('；') }}</div>
                <div v-if="item.do_not?.length" style="margin-top:4px;color:#e6a23c"><strong>⚠️ 禁止：</strong>{{ item.do_not.join('；') }}</div>
              </div>
            </div>
          </div>
          <el-empty v-else-if="kbSearched" description="未找到匹配项" :image-size="40" />
          <el-text v-else type="info" size="small">输入关键词或点击标签检索（共 {{ kbTotal }} 条）</el-text>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, watch, computed, onMounted } from 'vue'
import { Search } from '@element-plus/icons-vue'
import api from '../api'
import { ElMessage } from 'element-plus'

const form = reactive({ command: '', sandbox: true, timeout: 30 })
const result = ref(null)
const executing = ref(false)
const history = ref([])
const previewRisk = ref('')
const previewRiskLabel = ref('')
const execCategory = ref('')
const cmdSearch = ref('')

const RISK_MAP = {
  readonly: { color: 'success', label: '只读' },
  reversible: { color: 'warning', label: '可逆' },
  irreversible: { color: 'danger', label: '不可逆' },
  critical: { color: 'danger', label: '关键' },
}

const catLabelMap = {
  system: '🖥️ 系统',
  process: '⚙️ 进程',
  network: '🌐 网络',
  disk: '💾 磁盘',
  log: '📋 日志',
  security: '🔒 安全',
  service: '🔧 服务',
}

// 命令库（统一结构，包含风险标签）
const execCmdLibrary = [
  // 系统信息
  { cat: 'system', label: '系统版本', cmd: 'uname -a', risk: 'readonly' },
  { cat: 'system', label: '发行版信息', cmd: 'cat /etc/os-release', risk: 'readonly' },
  { cat: 'system', label: '运行时间', cmd: 'uptime', risk: 'readonly' },
  { cat: 'system', label: '内存使用', cmd: 'free -h', risk: 'readonly' },
  { cat: 'system', label: '磁盘使用', cmd: 'df -h', risk: 'readonly' },
  { cat: 'system', label: 'CPU信息', cmd: 'lscpu', risk: 'readonly' },
  { cat: 'system', label: '系统负载', cmd: 'top -bn1 | head -20', risk: 'readonly' },
  { cat: 'system', label: '系统时间', cmd: 'date +"%Y-%m-%d %H:%M:%S"', risk: 'readonly' },

  // 进程管理
  { cat: 'process', label: 'CPU Top进程', cmd: 'ps aux --sort=-%cpu | head -20', risk: 'readonly' },
  { cat: 'process', label: '内存Top进程', cmd: 'ps aux --sort=-%mem | head -20', risk: 'readonly' },
  { cat: 'process', label: '僵尸进程', cmd: 'ps aux | grep -i zombie', risk: 'readonly' },
  { cat: 'process', label: '进程树', cmd: 'ps -ef --forest | head -30', risk: 'readonly' },
  { cat: 'process', label: '强制终止进程', cmd: 'kill -9 PID', risk: 'irreversible' },
  { cat: 'process', label: '按名称终止', cmd: 'pkill -f "进程名"', risk: 'irreversible' },

  // 磁盘空间
  { cat: 'disk', label: '日志目录大小', cmd: 'du -sh /var/log/*', risk: 'readonly' },
  { cat: 'disk', label: '临时文件大小', cmd: 'du -sh /tmp/*', risk: 'readonly' },
  { cat: 'disk', label: '大文件扫描', cmd: 'find / -size +100M -type f 2>/dev/null', risk: 'readonly' },
  { cat: 'disk', label: '日志文件占用', cmd: 'lsof +D /var/log 2>/dev/null', risk: 'readonly' },

  // 网络安全
  { cat: 'network', label: '监听端口', cmd: 'ss -tlnp', risk: 'readonly' },
  { cat: 'network', label: '连接统计', cmd: 'ss -s', risk: 'readonly' },
  { cat: 'network', label: '网络接口', cmd: 'ip addr show', risk: 'readonly' },
  { cat: 'network', label: '路由表', cmd: 'ip route show', risk: 'readonly' },
  { cat: 'network', label: '防火墙规则', cmd: 'iptables -L -n --line-numbers', risk: 'readonly' },
  { cat: 'network', label: 'DNS配置', cmd: 'cat /etc/resolv.conf', risk: 'readonly' },
  { cat: 'network', label: '最近登录', cmd: 'last -20', risk: 'readonly' },
  { cat: 'network', label: '当前登录用户', cmd: 'who', risk: 'readonly' },
  { cat: 'network', label: '失败登录', cmd: 'lastb -10', risk: 'readonly' },

  // 日志审计
  { cat: 'log', label: '最近1小时日志', cmd: 'journalctl --since "1 hour ago" --no-pager', risk: 'readonly' },
  { cat: 'log', label: '今日错误日志', cmd: 'journalctl -p err --since today --no-pager', risk: 'readonly' },
  { cat: 'log', label: 'SSH日志', cmd: 'journalctl -u sshd --since today --no-pager', risk: 'readonly' },
  { cat: 'log', label: '登录失败日志', cmd: 'grep -i "failed password" /var/log/auth.log | tail -20', risk: 'readonly' },
  { cat: 'log', label: '内核日志', cmd: 'dmesg | tail -30', risk: 'readonly' },
  { cat: 'log', label: '审计认证摘要', cmd: 'aureport --auth --summary', risk: 'readonly' },

  // 安全加固
  { cat: 'security', label: '可登录用户', cmd: 'cat /etc/passwd | grep -v nologin', risk: 'readonly' },
  { cat: 'security', label: 'SUID文件', cmd: 'find / -perm -4000 -type f 2>/dev/null', risk: 'readonly' },
  { cat: 'security', label: 'SGID文件', cmd: 'find / -perm -2000 -type f 2>/dev/null', risk: 'readonly' },
  { cat: 'security', label: '当前用户计划任务', cmd: 'crontab -l', risk: 'readonly' },
  { cat: 'security', label: '系统计划任务', cmd: 'cat /etc/crontab', risk: 'readonly' },
  { cat: 'security', label: 'sudo配置', cmd: 'sudo -l', risk: 'readonly' },

  // 服务管理
  { cat: 'service', label: '运行中的服务', cmd: 'systemctl list-units --type=service --state=running', risk: 'readonly' },
  { cat: 'service', label: 'SSH服务状态', cmd: 'systemctl status sshd', risk: 'readonly' },
  { cat: 'service', label: '定时器', cmd: 'systemctl list-timers', risk: 'readonly' },
  { cat: 'service', label: '重启SSH', cmd: 'systemctl restart sshd', risk: 'reversible' },
].map(item => {
  const rm = RISK_MAP[item.risk] || RISK_MAP.readonly
  return { ...item, riskColor: rm.color, riskLabel: rm.label, value: item.cmd }
})

// 按分类+搜索过滤
const filteredExecCmds = computed(() => {
  let list = execCmdLibrary
  if (execCategory.value) {
    list = list.filter(c => c.cat === execCategory.value)
  }
  const q = cmdSearch.value?.toLowerCase().trim()
  if (q) {
    list = list.filter(c =>
      c.cmd.toLowerCase().includes(q) ||
      c.label.toLowerCase().includes(q)
    )
  }
  return list
})

// 自动补全搜索
function queryCommands(queryString, cb) {
  const q = queryString.toLowerCase()
  const results = queryString
    ? execCmdLibrary.filter(c =>
        c.cmd.toLowerCase().includes(q) ||
        c.label.toLowerCase().includes(q)
      )
    : execCmdLibrary.slice(0, 20)
  cb(results)
}

function onSelectCommand(item) {
  form.command = item.cmd
}

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

// ---- 知识库检索 (shared composable) ----
import { useKnowledgeSearch } from '../composables/useKnowledgeSearch'
import { sevTypeCN } from '../utils/severity'
const {
  query: kbQuery, activeTag: kbActiveTag, results: kbResults,
  tags: kbTags, total: kbTotal, loading: kbLoading,
  searched: kbSearched,
  search: searchKb, toggleTag: toggleKbTag, toggleDetail: toggleKbDetail,
} = useKnowledgeSearch({ limit: 20 })
function sevType(s) { return sevTypeCN(s) }

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
.cmd-lib-list { max-height: 360px; overflow-y: auto; }
.cmd-lib-item {
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 4px;
  transition: background 0.2s;
  border: 1px solid transparent;
}
.cmd-lib-item:hover {
  background: #f0f7ff;
  border-color: #d0e3ff;
}
.risk-bar { margin-top: 8px; display: flex; flex-wrap: wrap; align-items: center; gap: 4px; }
.kb-list { max-height: 300px; overflow-y: auto; }
.kb-item {
  padding: 8px 10px;
  border-radius: 6px;
  margin-bottom: 6px;
  border: 1px solid #ebeef5;
  transition: border-color 0.2s;
}
.kb-item:hover {
  border-color: #409eff;
}
</style>
