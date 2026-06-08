<template>
  <div class="blue-team">
    <div class="page-header">
      <div>
        <h1 class="page-title">蓝队安全</h1>
        <p class="page-subtitle">Webshell 检测 · Sigma 规则 · IOC 匹配 · Auditd 规则 · 文件完整性 · 内核加固</p>
      </div>
      <div class="page-actions">
        <el-button size="small" type="primary" :loading="loading" @click="loadAll">
          <el-icon style="margin-right:4px"><Refresh /></el-icon> 刷新
        </el-button>
      </div>
    </div>

    <!-- 蓝队规则统计 -->
    <div class="stat-grid">
      <div v-for="s in ruleStats" :key="s.label" class="stat-card" :style="{ '--accent': s.color }">
        <div class="stat-icon">
          <el-icon :size="20"><component :is="s.icon" /></el-icon>
        </div>
        <div class="stat-body">
          <div class="stat-value">{{ s.value }}</div>
          <div class="stat-label">{{ s.label }}</div>
        </div>
      </div>
    </div>

    <!-- 蓝队规则引擎卡片 -->
    <div class="section-grid">
      <div v-for="rule in blueTeamRules" :key="rule.key" class="section-card">
        <div class="section-card-header">
          <div class="card-header-left">
            <div class="rule-icon" :style="{ background: rule.color + '15', color: rule.color }">
              <el-icon :size="18"><component :is="rule.icon" /></el-icon>
            </div>
            <h3>{{ rule.label }}</h3>
          </div>
          <el-tag :type="rule.status === 'active' ? 'success' : 'danger'" size="small" effect="plain">
            {{ rule.status === 'active' ? '运行中' : '未启用' }}
          </el-tag>
        </div>
        <div class="section-card-body">
          <p class="rule-desc">{{ rule.description }}</p>
          <div class="rule-meta">
            <div class="rule-meta-item">
              <span class="meta-label">规则数</span>
              <span class="meta-value">{{ rule.rule_count }}</span>
            </div>
            <div class="rule-meta-item">
              <span class="meta-label">最近匹配</span>
              <span class="meta-value">{{ rule.last_match || '无' }}</span>
            </div>
            <div class="rule-meta-item">
              <span class="meta-label">总命中</span>
              <span class="meta-value">{{ rule.total_hits }}</span>
            </div>
          </div>
          <div class="rule-actions">
            <el-button size="small" :type="rule.status === 'active' ? 'warning' : 'success'" plain @click="toggleRule(rule)">
              {{ rule.status === 'active' ? '停用' : '启用' }}
            </el-button>
            <el-button size="small" plain @click="viewRuleDetail(rule)">查看详情</el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 蓝队知识库快捷入口 -->
    <div class="section-card">
      <div class="section-card-header">
        <h3>蓝队知识库</h3>
        <el-button size="small" type="primary" plain @click="$router.push('/knowledge')">
          进入知识库 →
        </el-button>
      </div>
      <div class="knowledge-grid">
        <div v-for="item in blueTeamKnowledge" :key="item.key" class="knowledge-card" @click="$router.push({ path: '/knowledge', query: { q: item.key } })">
          <div class="knowledge-icon" :style="{ background: item.color + '15', color: item.color }">
            <el-icon :size="16"><component :is="item.icon" /></el-icon>
          </div>
          <div class="knowledge-info">
            <span class="knowledge-title">{{ item.label }}</span>
            <span class="knowledge-desc">{{ item.desc }}</span>
          </div>
          <el-icon class="knowledge-arrow" color="var(--color-neutral-300)"><ArrowRight /></el-icon>
        </div>
      </div>
    </div>

    <!-- 蓝队安全审计日志 -->
    <div class="section-card">
      <div class="section-card-header">
        <h3>安全审计日志</h3>
        <div class="section-card-actions">
          <el-radio-group v-model="auditFilter" size="small">
            <el-radio-button label="all">全部</el-radio-button>
            <el-radio-button label="webshell">Webshell</el-radio-button>
            <el-radio-button label="sigma">Sigma</el-radio-button>
            <el-radio-button label="ioc">IOC</el-radio-button>
            <el-radio-button label="auditd">Auditd</el-radio-button>
          </el-radio-group>
        </div>
      </div>
      <div class="audit-table">
        <div class="audit-table-header">
          <span class="audit-col-time">时间</span>
          <span class="audit-col-type">类型</span>
          <span class="audit-col-severity">级别</span>
          <span class="audit-col-message">消息</span>
          <span class="audit-col-source">来源</span>
        </div>
        <div v-for="(log, i) in filteredAuditLogs" :key="i" class="audit-table-row">
          <span class="audit-col-time">{{ log.timestamp }}</span>
          <span class="audit-col-type">
            <span class="type-tag" :class="log.type">{{ log.type }}</span>
          </span>
          <span class="audit-col-severity">
            <span class="sev-tag" :class="log.severity">{{ log.severity }}</span>
          </span>
          <span class="audit-col-message">{{ log.message }}</span>
          <span class="audit-col-source">{{ log.source }}</span>
        </div>
        <div v-if="!filteredAuditLogs.length" class="audit-empty">暂无审计日志</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../api'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const auditFilter = ref('all')

const ruleStats = ref([
  { label: '规则引擎', value: '6', icon: 'Lock', color: '#4f6ef7' },
  { label: '总规则数', value: '42', icon: 'List', color: '#10b981' },
  { label: '今日命中', value: '7', icon: 'WarningFilled', color: '#f59e0b' },
  { label: '安全事件', value: '3', icon: 'Bell', color: '#ef4444' },
])

const blueTeamRules = ref([
  {
    key: 'webshell',
    label: 'Webshell 检测',
    icon: 'WarningFilled',
    color: '#ef4444',
    status: 'active',
    description: '检测 Web 目录中的可疑脚本文件，识别 PHP/JSP/ASP 一句话木马、加密后门等恶意 WebShell。',
    rule_count: 8,
    last_match: '2026-06-08 12:34',
    total_hits: 23,
  },
  {
    key: 'sigma',
    label: 'Sigma 规则',
    icon: 'List',
    color: '#f59e0b',
    status: 'active',
    description: '将 Sigma 通用安全检测规则转换为可执行的日志查询，覆盖 ATT&CK 框架的各类检测场景。',
    rule_count: 12,
    last_match: '2026-06-08 11:20',
    total_hits: 45,
  },
  {
    key: 'ioc',
    label: 'IOC 匹配',
    icon: 'Search',
    color: '#8b5cf6',
    status: 'active',
    description: '基于威胁情报的 IOC（IP/域名/Hash）匹配引擎，实时检测已知恶意指标。',
    rule_count: 10,
    last_match: '2026-06-08 10:15',
    total_hits: 18,
  },
  {
    key: 'auditd',
    label: 'Auditd 规则',
    icon: 'Monitor',
    color: '#10b981',
    status: 'active',
    description: 'Linux Auditd 内核审计规则，监控文件访问、系统调用、权限变更等关键事件。',
    rule_count: 6,
    last_match: '2026-06-08 09:45',
    total_hits: 31,
  },
  {
    key: 'file_integrity',
    label: '文件完整性',
    icon: 'CircleCheck',
    color: '#06b6d4',
    status: 'active',
    description: '监控关键系统文件和配置文件的完整性，检测未授权的文件修改和篡改行为。',
    rule_count: 4,
    last_match: '2026-06-07 22:30',
    total_hits: 12,
  },
  {
    key: 'kernel_hardening',
    label: '内核加固',
    icon: 'Lock',
    color: '#3b82f6',
    status: 'active',
    description: '系统内核安全加固规则，包括 sysctl 参数优化、内核模块限制、内存保护等。',
    rule_count: 2,
    last_match: '2026-06-07 18:00',
    total_hits: 8,
  },
])

const blueTeamKnowledge = [
  { key: 'webshell', label: 'Webshell 检测', desc: 'PHP/JSP/ASP 一句话木马识别', icon: 'WarningFilled', color: '#ef4444' },
  { key: 'sigma', label: 'Sigma 规则', desc: '通用安全检测规则转换', icon: 'List', color: '#f59e0b' },
  { key: 'ioc', label: 'IOC 匹配', desc: '威胁情报指标匹配引擎', icon: 'Search', color: '#8b5cf6' },
  { key: 'auditd', label: 'Auditd 规则', desc: '内核审计规则配置', icon: 'Monitor', color: '#10b981' },
  { key: 'file_integrity', label: '文件完整性', desc: '关键文件篡改监控', icon: 'CircleCheck', color: '#06b6d4' },
  { key: 'kernel_hardening', label: '内核加固', desc: '系统内核安全加固', icon: 'Lock', color: '#3b82f6' },
]

const auditLogs = ref([
  { timestamp: '2026-06-08 12:34:22', type: 'webshell', severity: 'critical', message: '检测到可疑 PHP 文件 /var/www/html/shell.php', source: 'Webshell Detector' },
  { timestamp: '2026-06-08 11:20:15', type: 'sigma', severity: 'high', message: 'Sigma 规则匹配: 可疑 PowerShell 执行', source: 'Sigma Bridge' },
  { timestamp: '2026-06-08 10:15:08', type: 'ioc', severity: 'high', message: 'IOC 匹配: 恶意 IP 185.220.101.x 连接尝试', source: 'IOC Matcher' },
  { timestamp: '2026-06-08 09:45:33', type: 'auditd', severity: 'medium', message: '检测到 /etc/shadow 文件访问', source: 'Auditd Rules' },
  { timestamp: '2026-06-08 08:30:11', type: 'webshell', severity: 'medium', message: '可疑 JSP 文件上传 /uploads/test.jsp', source: 'Webshell Detector' },
  { timestamp: '2026-06-07 22:30:45', type: 'file_integrity', severity: 'warning', message: '/etc/passwd 文件哈希变更', source: 'File Integrity' },
  { timestamp: '2026-06-07 18:00:22', type: 'kernel_hardening', severity: 'info', message: '内核参数 net.ipv4.ip_forward 已加固', source: 'Kernel Hardening' },
  { timestamp: '2026-06-07 15:20:10', type: 'sigma', severity: 'medium', message: 'Sigma 规则匹配: 异常计划任务创建', source: 'Sigma Bridge' },
  { timestamp: '2026-06-07 14:10:05', type: 'ioc', severity: 'low', message: 'IOC 匹配: 已知恶意域名检测', source: 'IOC Matcher' },
  { timestamp: '2026-06-07 12:00:00', type: 'auditd', severity: 'info', message: '用户 root 执行 sudo 命令', source: 'Auditd Rules' },
])

const filteredAuditLogs = computed(() => {
  if (auditFilter.value === 'all') return auditLogs.value
  return auditLogs.value.filter(l => l.type === auditFilter.value)
})

async function loadAll() {
  loading.value = true
  try {
    // 模拟加载蓝队规则状态
    await new Promise(r => setTimeout(r, 500))
    ElMessage.success('蓝队安全状态已刷新')
  } catch (e) {
    ElMessage.error('加载失败: ' + (e.message || '未知'))
  } finally {
    loading.value = false
  }
}

function toggleRule(rule) {
  rule.status = rule.status === 'active' ? 'inactive' : 'active'
  ElMessage.success(`${rule.label} 已${rule.status === 'active' ? '启用' : '停用'}`)
}

function viewRuleDetail(rule) {
  ElMessage.info(`${rule.label}: 共 ${rule.rule_count} 条规则，总命中 ${rule.total_hits} 次`)
}

onMounted(() => {})
</script>

<style scoped>
.blue-team {
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
}

/* ---- 统计卡片 ---- */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-4);
}

.stat-card {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-5);
  background: #fff;
  border: 1px solid var(--color-neutral-200);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  position: relative;
  overflow: hidden;
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

.stat-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: var(--radius-lg);
  background: var(--color-neutral-50);
  color: var(--accent);
  flex-shrink: 0;
}

.stat-body {
  flex: 1;
}

.stat-value {
  font-size: var(--text-xl);
  font-weight: 700;
  color: var(--color-neutral-900);
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}

.stat-label {
  font-size: var(--text-xs);
  color: var(--color-neutral-400);
  margin-top: var(--space-1);
}

/* ---- 规则卡片网格 ---- */
.section-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-4);
}

.section-card {
  background: #fff;
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

.card-header-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.card-header-left h3 {
  margin: 0;
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--color-neutral-700);
}

.rule-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.section-card-body {
  padding: var(--space-4) var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.rule-desc {
  font-size: var(--text-xs);
  color: var(--color-neutral-500);
  line-height: var(--leading-relaxed);
  margin: 0;
}

.rule-meta {
  display: flex;
  gap: var(--space-4);
  padding: var(--space-3);
  background: var(--color-neutral-50);
  border-radius: var(--radius-md);
}

.rule-meta-item {
  flex: 1;
  text-align: center;
}

.meta-label {
  display: block;
  font-size: 10px;
  color: var(--color-neutral-400);
  margin-bottom: var(--space-1);
}

.meta-value {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--color-neutral-700);
  font-variant-numeric: tabular-nums;
}

.rule-actions {
  display: flex;
  gap: var(--space-2);
}

/* ---- 知识库快捷入口 ---- */
.knowledge-grid {
  padding: var(--space-4) var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.knowledge-card {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--color-neutral-200);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}

.knowledge-card:hover {
  border-color: var(--color-primary-200);
  background: var(--color-primary-50);
}

.knowledge-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.knowledge-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.knowledge-title {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--color-neutral-700);
}

.knowledge-desc {
  font-size: var(--text-xs);
  color: var(--color-neutral-400);
}

.knowledge-arrow {
  flex-shrink: 0;
}

/* ---- 审计日志表格 ---- */
.audit-table {
  padding: 0 var(--space-5) var(--space-4);
}

.audit-table-header {
  display: grid;
  grid-template-columns: 160px 90px 70px 1fr 140px;
  gap: var(--space-2);
  padding: var(--space-2);
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--color-neutral-400);
  text-transform: uppercase;
  letter-spacing: var(--tracking-wide);
  border-bottom: 1px solid var(--color-neutral-200);
}

.audit-table-row {
  display: grid;
  grid-template-columns: 160px 90px 70px 1fr 140px;
  gap: var(--space-2);
  padding: var(--space-2);
  font-size: var(--text-sm);
  align-items: center;
  border-bottom: 1px solid var(--color-neutral-100);
  transition: background var(--duration-fast) var(--ease-out);
}

.audit-table-row:hover {
  background: var(--color-neutral-50);
}

.audit-col-time {
  font-size: var(--text-xs);
  color: var(--color-neutral-400);
  font-variant-numeric: tabular-nums;
}

.type-tag {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  text-transform: uppercase;
}

.type-tag.webshell { background: var(--color-danger-bg); color: var(--color-danger); }
.type-tag.sigma { background: var(--color-warning-bg); color: var(--color-warning); }
.type-tag.ioc { background: var(--color-primary-50); color: var(--color-primary-500); }
.type-tag.auditd { background: var(--color-success-bg); color: var(--color-success); }
.type-tag.file_integrity { background: var(--color-info-bg); color: var(--color-info); }
.type-tag.kernel_hardening { background: var(--color-neutral-100); color: var(--color-neutral-600); }

.sev-tag {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  text-transform: uppercase;
}

.sev-tag.critical { background: var(--color-danger-bg); color: var(--color-danger); }
.sev-tag.high { background: var(--color-warning-bg); color: var(--color-warning); }
.sev-tag.medium { background: var(--color-info-bg); color: var(--color-info); }
.sev-tag.warning { background: var(--color-neutral-100); color: var(--color-neutral-500); }
.sev-tag.info { background: var(--color-neutral-100); color: var(--color-neutral-500); }

.audit-col-message {
  font-size: var(--text-xs);
  color: var(--color-neutral-600);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.audit-col-source {
  font-size: var(--text-xs);
  color: var(--color-neutral-400);
}

.audit-empty {
  padding: var(--space-6);
  text-align: center;
  color: var(--color-neutral-300);
  font-size: var(--text-sm);
}

/* ---- 响应式 ---- */
@media (max-width: 1200px) {
  .stat-grid { grid-template-columns: repeat(2, 1fr); }
  .section-grid { grid-template-columns: repeat(2, 1fr); }
}

@media (max-width: 768px) {
  .stat-grid { grid-template-columns: repeat(2, 1fr); }
  .section-grid { grid-template-columns: 1fr; }
  .audit-table-header, .audit-table-row { grid-template-columns: 120px 70px 60px 1fr; }
  .audit-col-source { display: none; }
}
</style>
