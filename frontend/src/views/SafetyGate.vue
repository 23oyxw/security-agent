<template>
  <el-card header="安全门禁 — 三层防御评估 (30/35/35)">
    <el-form :model="form" label-width="100px" style="max-width: 720px">
      <el-form-item label="用户意图">
        <el-input v-model="form.user_message" type="textarea" :rows="2" placeholder="例：帮我查看一下日志目录" />
      </el-form-item>
      <el-form-item label="待执行命令">
        <el-autocomplete
          v-model="form.target"
          :fetch-suggestions="queryCommands"
          placeholder="输入命令或关键词搜索案例库"
          style="width:100%"
          @select="onSelectCommand"
          clearable
        >
          <template #default="{ item }">
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span><code>{{ item.value }}</code></span>
              <el-tag :type="item.riskColor" size="small" effect="plain">{{ item.riskLabel }}</el-tag>
            </div>
          </template>
        </el-autocomplete>
      </el-form-item>
      <el-form-item v-if="selectedCase" label="案例说明">
        <el-descriptions :column="1" size="small" border style="width:100%">
          <el-descriptions-item label="场景">{{ selectedCase.scene }}</el-descriptions-item>
          <el-descriptions-item label="风险等级">
            <el-tag :type="selectedCase.riskColor" size="small">{{ selectedCase.riskLabel }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="说明">{{ selectedCase.desc }}</el-descriptions-item>
          <el-descriptions-item v-if="selectedCase.alt" label="安全替代">{{ selectedCase.alt }}</el-descriptions-item>
        </el-descriptions>
      </el-form-item>
      <el-form-item label="sudo">
        <el-switch v-model="form.sudo" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="validate" :loading="loading">三层防御评估</el-button>
        <el-button @click="quickAssess" :loading="loading">快速风险评估</el-button>
      </el-form-item>
    </el-form>
    <el-divider />
    <el-result
      v-if="result"
      :icon="result.allowed ? 'success' : 'error'"
      :title="verdictLabel(result.overall_verdict)"
      :sub-title="result.message"
    >
      <template #extra>
        <el-descriptions :column="2" border size="small" style="margin-bottom: 16px">
          <el-descriptions-item label="综合得分">{{ result.overall_score?.toFixed?.(1) ?? result.overall_score }}</el-descriptions-item>
          <el-descriptions-item label="判决">{{ result.overall_verdict }}</el-descriptions-item>
          <el-descriptions-item label="Trace ID">{{ result.trace_id }}</el-descriptions-item>
          <el-descriptions-item label="需确认">{{ result.requires_user_confirmation ? '是' : '否' }}</el-descriptions-item>
        </el-descriptions>
        <el-table v-if="result.layers?.length" :data="result.layers" size="small" stripe>
          <el-table-column prop="layer" label="层级" width="140" />
          <el-table-column prop="weight" label="权重" width="80">
            <template #default="{ row }">{{ (row.weight * 100).toFixed(0) }}%</template>
          </el-table-column>
          <el-table-column prop="score" label="得分" width="80" />
          <el-table-column prop="verdict" label="判定" width="80" />
          <el-table-column prop="detail" label="说明" />
        </el-table>
      </template>
    </el-result>
  </el-card>

  <!-- 命令案例库 -->
  <el-card header="📖 命令案例库" style="margin-top:16px">
    <div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap">
      <el-radio-group v-model="activeCategory" size="small">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button v-for="cat in categories" :key="cat.key" :value="cat.key">{{ cat.label }}</el-radio-button>
      </el-radio-group>
    </div>
    <el-table :data="filteredCases" size="small" stripe max-height="400" style="cursor:pointer" @row-click="useCase">
      <el-table-column prop="cmd" label="命令" width="260">
        <template #default="{ row }"><code>{{ row.cmd }}</code></template>
      </el-table-column>
      <el-table-column prop="scene" label="场景" width="140" />
      <el-table-column prop="riskLabel" label="风险" width="90">
        <template #default="{ row }"><el-tag :type="row.riskColor" size="small">{{ row.riskLabel }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="desc" label="说明" show-overflow-tooltip />
      <el-table-column label="操作" width="70">
        <template #default="{ row }">
          <el-button size="small" type="primary" link @click.stop="useCase(row)">填入</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <!-- 安全知识库检索 -->
  <el-card header="🧠 安全知识库检索" style="margin-top:16px">
    <div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap;align-items:center">
      <el-input
        v-model="kbQuery"
        placeholder="搜索关键词：如后门、入侵排查、SSH、日志、Sigma"
        style="width:300px"
        clearable
        @keyup.enter="searchKnowledge"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-button type="primary" @click="searchKnowledge" :loading="kbLoading">检索</el-button>
      <el-divider direction="vertical" />
      <el-tag
        v-for="t in kbTags.slice(0, 12)"
        :key="t.name"
        :type="kbActiveTag === t.name ? '' : 'info'"
        :effect="kbActiveTag === t.name ? 'dark' : 'plain'"
        size="small"
        style="cursor:pointer"
        @click="toggleTag(t.name)"
      >
        {{ t.name }} ({{ t.count }})
      </el-tag>
    </div>
    <el-table v-if="kbResults.length" :data="kbResults" size="small" stripe max-height="350" @row-click="toggleKbDetail">
      <el-table-column prop="id" label="编号" width="130" />
      <el-table-column prop="title" label="标题" width="200" />
      <el-table-column prop="severity" label="严重度" width="80">
        <template #default="{ row }">
          <el-tag :type="sevType(row.severity)" size="small">{{ row.severity }}</el-tag>
          <el-tag v-if="row.requires_root_confirm" type="danger" size="small" effect="dark" style="margin-left:2px">Root</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="标签" width="200">
        <template #default="{ row }">
          <el-tag v-for="tag in row.threat_tags" :key="tag" size="small" type="info" effect="plain" style="margin:1px">{{ tag }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="body" label="说明" show-overflow-tooltip />
    </el-table>
    <el-empty v-else-if="kbSearched" description="未找到匹配的知识条目" />
    <div v-if="kbDetailItem" style="margin-top:8px;padding:10px;background:#f9f9f9;border-radius:6px;font-size:12px;line-height:1.6">
      <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px">
        <el-tag size="small" type="warning">{{ kbDetailItem.id }}</el-tag>
        <span style="font-weight:500">{{ kbDetailItem.title }}</span>
        <el-button text type="primary" size="small" style="margin-left:auto" @click="kbDetailItem = null">关闭</el-button>
      </div>
      <div>{{ kbDetailItem.body }}</div>
      <div v-if="kbDetailItem.suggested_actions?.length" style="margin-top:6px"><strong>建议：</strong>{{ kbDetailItem.suggested_actions.join('；') }}</div>
      <div v-if="kbDetailItem.do_not?.length" style="margin-top:4px;color:#e6a23c"><strong>⚠️ 禁止：</strong>{{ kbDetailItem.do_not.join('；') }}</div>
    </div>
    <el-text v-else type="info" size="small">输入关键词或点击标签检索安全知识库（共 {{ kbTotal }} 条）</el-text>
  </el-card>

  <el-card header="人工审批队列（S4 · 持久化）" style="margin-top:16px">
    <div style="display:flex;gap:8px;margin-bottom:12px">
      <el-button size="small" @click="loadPending" :loading="pendingLoading">刷新待审批</el-button>
      <el-tag type="warning">待处理: {{ pending.length }}</el-tag>
    </div>
    <el-table :data="pending" size="small" stripe empty-text="暂无待审批">
      <el-table-column prop="request_id" label="单号" width="140" />
      <el-table-column prop="command" label="命令/动作" show-overflow-tooltip />
      <el-table-column prop="risk_level" label="风险" width="80" />
      <el-table-column prop="trace_id" label="Trace" width="160" show-overflow-tooltip />
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button size="small" type="success" @click="decide(row.request_id, 'approve')">批准</el-button>
          <el-button size="small" type="danger" @click="decide(row.request_id, 'reject')">拒绝</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup>
import { reactive, ref, computed, onMounted } from 'vue'
import { Search } from '@element-plus/icons-vue'
import api from '../api'
import { ElMessage } from 'element-plus'

const form = reactive({ user_message: '', target: '', sudo: false })
const result = ref(null)
const loading = ref(false)
const pending = ref([])
const pendingLoading = ref(false)
const activeCategory = ref('')
const selectedCase = ref(null)

// ---- 知识库检索 (shared composable) ----
import { useKnowledgeSearch } from '../composables/useKnowledgeSearch'
const {
  query: kbQuery, activeTag: kbActiveTag, results: kbResults,
  tags: kbTags, total: kbTotal, loading: kbLoading,
  searched: kbSearched, detailItem: kbDetailItem,
  sevType, search: searchKnowledge, toggleTag, toggleDetail: toggleKbDetail,
} = useKnowledgeSearch({ limit: 30 })

const DENY_VERDICTS = new Set(['deny', 'escalate', 'quarantine'])

const RISK_MAP = {
  readonly: { color: 'success', label: '只读' },
  reversible: { color: 'warning', label: '可逆' },
  irreversible: { color: 'danger', label: '不可逆' },
  critical: { color: 'danger', label: '关键' },
}

// 命令案例库
const categories = [
  { key: 'system', label: '🖥️ 系统信息' },
  { key: 'process', label: '⚙️ 进程管理' },
  { key: 'disk', label: '💾 磁盘空间' },
  { key: 'network', label: '🌐 网络安全' },
  { key: 'log', label: '📋 日志审计' },
  { key: 'security', label: '🔒 安全加固' },
  { key: 'service', label: '🔧 服务管理' },
  { key: 'danger', label: '⚠️ 高危操作' },
]

const commandCases = [
  // 系统信息
  { cat: 'system', cmd: 'uname -a', scene: '系统版本', risk: 'readonly', desc: '查看内核版本和系统架构信息', alt: '' },
  { cat: 'system', cmd: 'cat /etc/os-release', scene: '发行版信息', risk: 'readonly', desc: '查看操作系统发行版详情', alt: '' },
  { cat: 'system', cmd: 'uptime', scene: '运行时间', risk: 'readonly', desc: '查看系统运行时间和负载', alt: '' },
  { cat: 'system', cmd: 'free -h', scene: '内存使用', risk: 'readonly', desc: '查看内存和交换分区使用情况', alt: '' },
  { cat: 'system', cmd: 'df -h', scene: '磁盘使用', risk: 'readonly', desc: '查看各挂载点磁盘使用率', alt: '' },
  { cat: 'system', cmd: 'lscpu', scene: 'CPU信息', risk: 'readonly', desc: '查看CPU型号、核心数、架构', alt: '' },
  { cat: 'system', cmd: 'top -bn1 | head -20', scene: '系统概览', risk: 'readonly', desc: '一次性采集系统资源使用快照', alt: '' },
  { cat: 'system', cmd: 'date +"%Y-%m-%d %H:%M:%S"', scene: '系统时间', risk: 'readonly', desc: '查看当前系统时间', alt: '' },

  // 进程管理
  { cat: 'process', cmd: 'ps aux --sort=-%cpu | head -20', scene: 'CPU Top进程', risk: 'readonly', desc: '按CPU使用率排序查看前20进程', alt: '' },
  { cat: 'process', cmd: 'ps aux --sort=-%mem | head -20', scene: '内存Top进程', risk: 'readonly', desc: '按内存使用率排序查看前20进程', alt: '' },
  { cat: 'process', cmd: 'ps aux | grep -i zombie', scene: '僵尸进程', risk: 'readonly', desc: '查找僵尸进程', alt: '' },
  { cat: 'process', cmd: 'ps -ef --forest | head -30', scene: '进程树', risk: 'readonly', desc: '以树形结构查看进程关系', alt: '' },
  { cat: 'process', cmd: 'kill -9 PID', scene: '强制终止进程', risk: 'irreversible', desc: '强制终止指定PID进程（不可恢复）', alt: 'kill -15 PID（优雅终止）' },
  { cat: 'process', cmd: 'pkill -f "进程名"', scene: '按名称终止', risk: 'irreversible', desc: '按进程名模式匹配终止', alt: 'pkill -15 -f "进程名"' },
  { cat: 'process', cmd: 'killall -9 进程名', scene: '终止同名进程', risk: 'irreversible', desc: '终止所有同名进程', alt: 'killall -15 进程名' },

  // 磁盘空间
  { cat: 'disk', cmd: 'du -sh /var/log/*', scene: '日志目录大小', risk: 'readonly', desc: '查看日志目录各子目录占用空间', alt: '' },
  { cat: 'disk', cmd: 'du -sh /tmp/*', scene: '临时文件大小', risk: 'readonly', desc: '查看临时目录占用空间', alt: '' },
  { cat: 'disk', cmd: 'find / -size +100M -type f 2>/dev/null', scene: '大文件扫描', risk: 'readonly', desc: '查找大于100MB的文件', alt: '' },
  { cat: 'disk', cmd: 'lsof +D /var/log 2>/dev/null', scene: '日志文件占用', risk: 'readonly', desc: '查看哪些进程打开了日志文件', alt: '' },
  { cat: 'disk', cmd: 'rm -rf /tmp/*', scene: '清理临时文件', risk: 'irreversible', desc: '删除/tmp下所有文件', alt: 'find /tmp -mtime +7 -delete（只删7天前）' },

  // 网络安全
  { cat: 'network', cmd: 'ss -tlnp', scene: '监听端口', risk: 'readonly', desc: '查看所有TCP监听端口及对应进程', alt: '' },
  { cat: 'network', cmd: 'ss -s', scene: '连接统计', risk: 'readonly', desc: '查看TCP连接状态统计', alt: '' },
  { cat: 'network', cmd: 'ip addr show', scene: '网络接口', risk: 'readonly', desc: '查看所有网络接口和IP地址', alt: '' },
  { cat: 'network', cmd: 'ip route show', scene: '路由表', risk: 'readonly', desc: '查看系统路由表', alt: '' },
  { cat: 'network', cmd: 'iptables -L -n --line-numbers', scene: '防火墙规则', risk: 'readonly', desc: '查看iptables防火墙规则', alt: '' },
  { cat: 'network', cmd: 'cat /etc/resolv.conf', scene: 'DNS配置', risk: 'readonly', desc: '查看DNS服务器配置', alt: '' },
  { cat: 'network', cmd: 'last -20', scene: '最近登录', risk: 'readonly', desc: '查看最近20条登录记录', alt: '' },
  { cat: 'network', cmd: 'who', scene: '当前登录', risk: 'readonly', desc: '查看当前登录用户', alt: '' },
  { cat: 'network', cmd: 'lastb -10', scene: '失败登录', risk: 'readonly', desc: '查看最近失败的登录尝试', alt: '' },
  { cat: 'network', cmd: 'iptables -F', scene: '清空防火墙', risk: 'critical', desc: '清空所有iptables规则（极度危险！）', alt: 'iptables -D 规则编号（逐条删除）' },

  // 日志审计
  { cat: 'log', cmd: 'journalctl --since "1 hour ago" --no-pager', scene: '最近1小时日志', risk: 'readonly', desc: '查看最近1小时的系统日志', alt: '' },
  { cat: 'log', cmd: 'journalctl -p err --since today --no-pager', scene: '今日错误日志', risk: 'readonly', desc: '查看今天的错误级别日志', alt: '' },
  { cat: 'log', cmd: 'journalctl -u sshd --since today --no-pager', scene: 'SSH日志', risk: 'readonly', desc: '查看今天的SSH服务日志', alt: '' },
  { cat: 'log', cmd: 'grep -i "failed password" /var/log/auth.log | tail -20', scene: '登录失败', risk: 'readonly', desc: '查看最近的登录失败尝试', alt: '' },
  { cat: 'log', cmd: 'cat /var/log/secure | tail -50', scene: '安全日志', risk: 'readonly', desc: '查看安全认证日志末尾', alt: '' },
  { cat: 'log', cmd: 'dmesg | tail -30', scene: '内核日志', risk: 'readonly', desc: '查看最近的内核消息', alt: '' },
  { cat: 'log', cmd: 'cat /var/log/cron', scene: '计划任务日志', risk: 'readonly', desc: '查看cron定时任务执行日志', alt: '' },
  { cat: 'log', cmd: 'aureport --auth --summary', scene: '审计认证摘要', risk: 'readonly', desc: '生成认证审计摘要报告', alt: '' },

  // 安全加固
  { cat: 'security', cmd: 'cat /etc/passwd | grep -v nologin', scene: '可登录用户', risk: 'readonly', desc: '查看可登录系统的用户列表', alt: '' },
  { cat: 'security', cmd: 'cat /etc/shadow', scene: '密码哈希', risk: 'critical', desc: '查看密码哈希（敏感信息！）', alt: 'sudo -l（查看当前用户sudo权限）' },
  { cat: 'security', cmd: 'find / -perm -4000 -type f 2>/dev/null', scene: 'SUID文件', risk: 'readonly', desc: '查找所有SUID权限文件', alt: '' },
  { cat: 'security', cmd: 'find / -perm -2000 -type f 2>/dev/null', scene: 'SGID文件', risk: 'readonly', desc: '查找所有SGID权限文件', alt: '' },
  { cat: 'security', cmd: 'cat /etc/sudoers', scene: 'sudo配置', risk: 'critical', desc: '查看sudo权限配置（敏感）', alt: 'sudo -l（查看当前用户sudo权限）' },
  { cat: 'security', cmd: 'crontab -l', scene: '当前用户计划任务', risk: 'readonly', desc: '查看当前用户的crontab', alt: '' },
  { cat: 'security', cmd: 'cat /etc/crontab', scene: '系统计划任务', risk: 'readonly', desc: '查看系统级crontab', alt: '' },
  { cat: 'security', cmd: 'chmod 777 /', scene: '根目录777', risk: 'critical', desc: '绝对不要执行！会导致系统不可用', alt: '' },
  { cat: 'security', cmd: 'echo "" > /etc/passwd', scene: '清空密码文件', risk: 'critical', desc: '绝对不要执行！会导致系统无法登录', alt: '' },

  // 服务管理
  { cat: 'service', cmd: 'systemctl list-units --type=service --state=running', scene: '运行中的服务', risk: 'readonly', desc: '查看所有正在运行的服务', alt: '' },
  { cat: 'service', cmd: 'systemctl status sshd', scene: 'SSH服务状态', risk: 'readonly', desc: '查看SSH服务运行状态', alt: '' },
  { cat: 'service', cmd: 'systemctl restart sshd', scene: '重启SSH', risk: 'reversible', desc: '重启SSH服务（可能断开当前连接）', alt: '' },
  { cat: 'service', cmd: 'systemctl stop firewalld', scene: '关闭防火墙', risk: 'irreversible', desc: '停止防火墙服务（安全风险！）', alt: '临时放行端口代替关闭防火墙' },
  { cat: 'service', cmd: 'systemctl disable firewalld', scene: '禁用防火墙', risk: 'critical', desc: '禁止防火墙开机启动（安全风险！）', alt: '' },
  { cat: 'service', cmd: 'systemctl list-timers', scene: '定时器', risk: 'readonly', desc: '查看systemd定时器列表', alt: '' },
  { cat: 'service', cmd: 'journalctl -u 服务名 --since today', scene: '服务日志', risk: 'readonly', desc: '查看指定服务今天的日志', alt: '' },

  // 高危操作
  { cat: 'danger', cmd: 'rm -rf /', scene: '删除根目录', risk: 'critical', desc: '绝对禁止！会删除整个系统', alt: '' },
  { cat: 'danger', cmd: 'mkfs.ext4 /dev/sda', scene: '格式化磁盘', risk: 'critical', desc: '格式化系统盘（数据全丢！）', alt: '' },
  { cat: 'danger', cmd: 'dd if=/dev/zero of=/dev/sda', scene: '擦除磁盘', risk: 'critical', desc: '用零覆盖磁盘（不可恢复！）', alt: '' },
  { cat: 'danger', cmd: 'shutdown -h now', scene: '立即关机', risk: 'irreversible', desc: '立即关机（中断所有服务）', alt: 'shutdown -h +5（5分钟后关机）' },
  { cat: 'danger', cmd: 'reboot', scene: '重启系统', risk: 'irreversible', desc: '立即重启（短暂中断服务）', alt: 'shutdown -r +5（5分钟后重启）' },
  { cat: 'danger', cmd: 'userdel -r root', scene: '删除root', risk: 'critical', desc: '绝对禁止！删除root用户', alt: '' },
  { cat: 'danger', cmd: 'passwd root', scene: '修改root密码', risk: 'irreversible', desc: '修改root密码', alt: '确保记录新密码' },
  { cat: 'danger', cmd: 'visudo', scene: '编辑sudoers', risk: 'critical', desc: '编辑sudo配置（错误可导致sudo不可用）', alt: '使用 sudoers.d/ 目录添加规则' },
  { cat: 'danger', cmd: 'setenforce 0', scene: '关闭SELinux', risk: 'irreversible', desc: '临时关闭SELinux（降低安全性）', alt: '' },
  { cat: 'danger', cmd: 'swapoff -a', scene: '关闭交换分区', risk: 'reversible', desc: '关闭所有交换分区', alt: '' },
].map(item => {
  const rm = RISK_MAP[item.risk] || RISK_MAP.readonly
  return { ...item, riskColor: rm.color, riskLabel: rm.label, value: item.cmd }
})

const filteredCases = computed(() => {
  if (!activeCategory.value) return commandCases
  return commandCases.filter(c => c.cat === activeCategory.value)
})

function queryCommands(queryString, cb) {
  const q = queryString.toLowerCase()
  const results = queryString
    ? commandCases.filter(c =>
        c.cmd.toLowerCase().includes(q) ||
        c.scene.toLowerCase().includes(q) ||
        c.desc.toLowerCase().includes(q)
      )
    : commandCases.slice(0, 15)
  cb(results)
}

function onSelectCommand(item) {
  form.target = item.cmd
  selectedCase.value = item
}

function useCase(row) {
  form.target = row.cmd
  selectedCase.value = row
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function verdictLabel(v) {
  const map = { allow: '允许执行', confirm: '需用户确认', approve: '需人工审批', deny: '拒绝执行', quarantine: '隔离执行', escalate: '升级处理' }
  return map[v] || v
}

function normalizeDefense(data) {
  const verdict = String(data.overall_verdict || '').toLowerCase()
  return {
    ...data,
    allowed: !DENY_VERDICTS.has(verdict),
    overall_verdict: verdict,
  }
}

async function validate() {
  if (!form.target.trim()) return ElMessage.warning('请填写待执行命令')
  loading.value = true
  result.value = null
  selectedCase.value = null
  try {
    const data = await api.post('/safety/defense/evaluate', {
      target: form.target.trim(),
      target_type: 'terminal',
      user_message: form.user_message.trim(),
      sudo: form.sudo,
    })
    result.value = normalizeDefense(data)
    if (data.confirmation_request_id) {
      ElMessage.warning(`已入审批队列: ${data.confirmation_request_id}`)
      loadPending()
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '评估失败')
  } finally {
    loading.value = false
  }
}

async function quickAssess() {
  if (!form.target.trim()) return ElMessage.warning('请填写待执行命令')
  loading.value = true
  result.value = null
  selectedCase.value = null
  try {
    const data = await api.post('/safety/assess', {
      command: form.target.trim(),
      context: form.user_message.trim() || undefined,
    })
    result.value = {
      allowed: data.verdict !== 'deny',
      overall_verdict: data.verdict || data.level,
      overall_score: typeof data.score === 'number' ? data.score : 0,
      message: (data.reasons || []).join('；') || '评估完成',
      trace_id: data.trace_id,
      requires_user_confirmation: data.requires_approval,
      layers: [],
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '评估失败')
  } finally {
    loading.value = false
  }
}

async function loadPending() {
  pendingLoading.value = true
  try {
    const list = await api.get('/safety/pending')
    pending.value = Array.isArray(list) ? list : []
  } catch {
    pending.value = []
  } finally {
    pendingLoading.value = false
  }
}

async function decide(requestId, action) {
  try {
    await api.post('/safety/approve', { request_id: requestId, task_id: requestId, action, reason: 'ui' })
    ElMessage.success(action === 'approve' ? '已批准' : '已拒绝')
    loadPending()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  }
}

loadPending()
</script>