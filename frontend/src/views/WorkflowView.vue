<template>
  <div class="workflow-root">
    <!-- 顶栏 -->
    <div class="top-bar">
      <div>
        <h1 class="top-title">运维流程控制台</h1>
        <p class="top-subtitle">实时泳道 · 数据同步 · 可回滚可追溯</p>
      </div>
      <div class="top-actions">
        <el-tag v-if="polling" type="success" effect="dark" size="small">● 实时同步中 ({{ pollInterval }}s)</el-tag>
        <el-tag v-else type="info" size="small">已暂停</el-tag>
        <el-button size="small" @click="togglePolling">{{ polling ? '暂停' : '恢复' }}</el-button>
        <el-button size="small" type="primary" @click="fetchAll" :loading="loading">立即刷新</el-button>
        <span class="top-clock">{{ currentTime }}</span>
      </div>
    </div>

    <!-- Tab 切换 -->
    <el-tabs v-model="activeTab" class="main-tabs">
      <el-tab-pane label="实时执行流程" name="flow">
        <div class="swimlane-grid">
          <!-- 泳道 1: 采集层 -->
          <div class="swimlane" style="border-top: 3px solid #3b82f6">
            <div class="swimlane-header" style="background: #eff6ff">
              <div class="swimlane-header-left">
                <span class="swimlane-badge" style="background:#3b82f6">L1</span>
                <span class="swimlane-title">采集层 · OS 深度感知</span>
                <span class="swimlane-desc">psutil / lsof / netstat / journalctl</span>
              </div>
              <el-tag size="small" :type="layers.collection.status === 'active' ? 'success' : 'warning'">
                {{ layers.collection.status === 'active' ? '运行中' : '待命' }}
              </el-tag>
            </div>
            <div class="swimlane-body">
              <TransitionGroup name="node-pop">
                <div v-for="node in layers.collection.nodes" :key="node.id"
                     class="node-card" :class="{ 'node-alert': node.alert, 'node-pulse': node.alert }"
                     @click="selectNode('collection', node)">
                  <div class="node-indicator" :class="node.alert ? 'bg-danger' : (node.trend === 'up' ? 'bg-warn' : 'bg-success')"></div>
                  <div class="node-content">
                    <span class="node-title">{{ node.title }}</span>
                    <span class="node-value" :class="{ 'text-danger': node.alert }">{{ node.value }}</span>
                    <span class="node-sub">{{ node.subtitle }}</span>
                  </div>
                  <div v-if="node.alert" class="node-alert-dot"></div>
                </div>
              </TransitionGroup>
            </div>
          </div>

          <!-- 泳道间箭头 -->
          <div class="lane-arrow"><span>▼ 感知数据注入 LLM 上下文 ▼</span></div>

          <!-- 泳道 2: 管控层 -->
          <div class="swimlane" style="border-top: 3px solid #10b981">
            <div class="swimlane-header" style="background: #ecfdf5">
              <div class="swimlane-header-left">
                <span class="swimlane-badge" style="background:#10b981">L2</span>
                <span class="swimlane-title">管控层 · MCP 插件化 + 三层防御</span>
                <span class="swimlane-desc">17 Skills · 热插拔 · 安全闸门</span>
              </div>
              <el-tag size="small" type="success">{{ mcpCount }} Skills 已注册</el-tag>
            </div>
            <div class="swimlane-body">
              <div v-for="node in layers.control.nodes" :key="node.id"
                   class="node-card node-skill" @click="selectNode('control', node)">
                <div class="node-indicator bg-success"></div>
                <div class="node-content">
                  <span class="node-title">{{ node.title }}</span>
                  <span class="node-sub">{{ node.subtitle }}</span>
                </div>
                <el-tag size="small" type="info">{{ node.value }}</el-tag>
              </div>
              <div v-if="!layers.control.nodes.length" class="node-empty">MCP 注册中心待加载...</div>
            </div>
          </div>

          <div class="lane-arrow"><span>▼ Skill Flow 编排 → 安全执行 ▼</span></div>

          <!-- 泳道 3: 执行层 -->
          <div class="swimlane" style="border-top: 3px solid #f59e0b">
            <div class="swimlane-header" style="background: #fffbeb">
              <div class="swimlane-header-left">
                <span class="swimlane-badge" style="background:#f59e0b">L3</span>
                <span class="swimlane-title">执行层 · 沙箱 + 快照 + 自动回滚</span>
                <span class="swimlane-desc">PrivilegeBroker · SandboxExecutor · SnapshotManager</span>
              </div>
              <el-tag size="small" :type="layers.execution.nodes.length ? 'warning' : 'info'">
                {{ layers.execution.nodes.length }} 个快照
              </el-tag>
            </div>
            <div class="swimlane-body">
              <div v-for="node in layers.execution.nodes" :key="node.id"
                   class="node-card" :class="{ 'node-alert': node.alert, 'node-restored': node.restored }"
                   @click="selectNode('execution', node)">
                <div class="node-indicator" :class="node.restored ? 'bg-success' : (node.alert ? 'bg-danger' : 'bg-warn')"></div>
                <div class="node-content">
                  <span class="node-title">{{ node.title }}</span>
                  <span class="node-value" :class="{ 'text-danger': node.alert }">{{ node.value }}</span>
                  <span class="node-sub" v-if="node.files_count">{{ node.files_count }} 文件</span>
                </div>
                <el-tag v-if="node.restored" size="small" type="success">已回滚</el-tag>
                <el-button v-else size="small" type="danger" text @click.stop="rollbackSnapshot(node.id)">
                  ⏪ 回滚
                </el-button>
              </div>
              <div v-if="!layers.execution.nodes.length" class="node-empty">暂无快照 — 高危操作时自动创建</div>
            </div>
          </div>

          <div class="lane-arrow"><span>▼ 全链路追踪 ▼</span></div>

          <!-- 泳道 4: 审计层 -->
          <div class="swimlane" style="border-top: 3px solid #8b5cf6">
            <div class="swimlane-header" style="background: #f5f3ff">
              <div class="swimlane-header-left">
                <span class="swimlane-badge" style="background:#8b5cf6">Audit</span>
                <span class="swimlane-title">审计层 · 推理链路溯源</span>
                <span class="swimlane-desc">IncidentSpine · 六阶段 Tracing · 执行纪要导出</span>
              </div>
              <el-tag size="small" type="info">{{ layers.audit.nodes.length }} 条 Trace</el-tag>
            </div>
            <div class="swimlane-body">
              <div v-for="node in layers.audit.nodes" :key="node.id"
                   class="node-card node-trace" :class="{ 'node-alert': node.alert }"
                   @click="selectNode('audit', node)">
                <div class="node-indicator" :class="node.alert ? 'bg-danger' : 'bg-success'"></div>
                <div class="node-content">
                  <span class="node-title">{{ node.title || 'Trace 记录' }}</span>
                  <span class="node-value">{{ node.value }}</span>
                  <span class="node-sub">{{ node.subtitle }}</span>
                </div>
                <el-tag size="small" :type="node.alert ? 'danger' : ''">{{ node.alert ? '异常' : '正常' }}</el-tag>
              </div>
              <div v-if="!layers.audit.nodes.length" class="node-empty">暂无 Trace — 执行操作后自动生成</div>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- Tab 2: 工作流模板 -->
      <el-tab-pane label="工作流模板" name="template">
        <div class="template-panel">
          <div class="section-card">
            <div class="section-card-header">
              <h3>{{ workflow.title }}</h3>
              <span>{{ workflow.description }}</span>
            </div>
            <div class="template-body">
              <el-steps :active="null" finish-status="success" align-center>
                <el-step v-for="s in workflow.steps" :key="s.id"
                         :title="s.title" :description="s.pillar" />
              </el-steps>
              <el-table :data="workflow.steps" stripe size="small" style="margin-top:24px">
                <el-table-column prop="id" label="步骤" width="70" />
                <el-table-column prop="title" label="名称" width="160" />
                <el-table-column prop="pillar" label="支柱" width="100" />
                <el-table-column prop="api" label="API" width="280" show-overflow-tooltip />
                <el-table-column prop="detail" label="说明" min-width="200" show-overflow-tooltip />
              </el-table>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- Tab 3: Skill 目录 -->
      <el-tab-pane label="Skill 目录" name="skills">
        <div class="skills-grid">
          <div v-for="skill in skills" :key="skill.name"
               class="skill-card" @click="showSkillDetail(skill)">
            <div class="skill-card-header">
              <span class="skill-name">{{ skill.display_name || skill.name }}</span>
              <el-tag size="small" type="info">{{ skill.tool_count || '?' }} 工具</el-tag>
            </div>
            <p class="skill-desc">{{ skill.description || '—' }}</p>
            <div class="skill-tags">
              <el-tag v-for="tag in (skill.tags || [])" :key="tag" size="small" effect="plain">{{ tag }}</el-tag>
            </div>
          </div>
          <div v-if="!skills.length" class="node-empty">Skill 目录加载中...</div>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 右侧抽屉: 节点详情 -->
    <el-drawer v-model="drawerVisible" :title="drawerTitle" size="480px" direction="rtl">
      <template v-if="drawerNode">
        <div class="drawer-grid" v-for="(v, k) in drawerNode" :key="k">
          <div v-if="k !== 'id' && v !== undefined && v !== null" class="drawer-row">
            <span class="drawer-label">{{ k }}</span>
            <span class="drawer-value" :class="{ 'mono': k === 'id' || k === 'value' }">{{ v }}</span>
          </div>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, computed, watch } from 'vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import api from '../api'

const loading = ref(false)
const polling = ref(true)
const pollInterval = ref(3)
const currentTime = ref('')
const activeTab = ref('flow')
const mcpCount = ref(0)
const skills = ref([])
const drawerVisible = ref(false)
const drawerTitle = ref('')
const drawerNode = ref(null)

const workflow = reactive({ title: '', description: '', steps: [] })

const layers = reactive({
  collection: { status: 'idle', nodes: [], thresholds: {} },
  control: { status: 'idle', nodes: [] },
  execution: { status: 'idle', nodes: [] },
  audit: { status: 'idle', nodes: [] },
})

let _timer = null
let _clock = null

// ---- 数据同步 ----

async function fetchAll() {
  loading.value = true
  try {
    const [flow, mcp, snapshots] = await Promise.all([
      api.get('/workflow/flow-status').catch(() => null),
      api.get('/mcp/servers').catch(() => []),
      api.get('/executor/snapshots?limit=8').catch(() => []),
    ])
    if (flow?.layers) {
      Object.assign(layers.collection, flow.layers.collection)
      Object.assign(layers.control, flow.layers.control)
      Object.assign(layers.execution, flow.layers.execution)
      Object.assign(layers.audit, flow.layers.audit)
    }
    if (Array.isArray(mcp)) {
      mcpCount.value = mcp.length
      skills.value = mcp
      // 如果 control 泳道为空，用 mcp 数据填充
      if (!layers.control.nodes.length) {
        layers.control.nodes = mcp.slice(0, 8).map(s => ({
          id: s.name,
          title: s.display_name || s.name,
          subtitle: s.description || '',
          value: `${s.tools_count || 0} 工具`,
          alert: false,
        }))
      }
    }
    // 执行层: 如果 flow-status 中的 snapshots 为空，用 executor/snapshots 填充
    if (!layers.execution.nodes.length && Array.isArray(snapshots)) {
      layers.execution.nodes = snapshots.slice(0, 5).map(s => ({
        id: s.id,
        title: s.operation || '快照',
        value: s.risk_level || '—',
        subtitle: s.created_at?.slice(0, 19) || '',
        alert: s.risk_level === 'CRITICAL',
        restored: !!s.restored_at,
        files_count: s.files_count || 0,
      }))
    }
  } catch {} finally { loading.value = false }
}

async function fetchWorkflow() {
  try {
    const res = await api.get('/workflow/standard')
    Object.assign(workflow, res)
  } catch {}
}

async function rollbackSnapshot(snapId) {
  try {
    await ElMessageBox.confirm(`确认回滚到快照 ${snapId}？`, '回滚确认', { type: 'warning' })
  } catch { return }
  try {
    await api.post(`/executor/rollback`, { rollback_id: snapId })
    ElMessage.success('回滚成功')
    fetchAll()
  } catch (e) {
    ElMessage.error('回滚失败: ' + (e.response?.data?.detail || e.message))
  }
}

function togglePolling() {
  polling.value = !polling.value
  if (polling.value) startPolling()
  else stopPolling()
}

function startPolling() {
  if (_timer) return
  fetchAll()
  _timer = setInterval(fetchAll, pollInterval.value * 1000)
}

function stopPolling() {
  clearInterval(_timer)
  _timer = null
}

function selectNode(layer, node) {
  drawerTitle.value = `${node.title || node.id}`
  drawerNode.value = node
  drawerVisible.value = true
}

function showSkillDetail(skill) {
  drawerTitle.value = `${skill.display_name || skill.name}`
  drawerNode.value = {
    name: skill.name,
    display_name: skill.display_name,
    description: skill.description,
    tool_count: skill.tool_count,
    tags: (skill.tags || []).join(', '),
    version: skill.version || '—',
  }
  drawerVisible.value = true
}

// 时钟
function updateClock() {
  const d = new Date()
  currentTime.value = d.toLocaleTimeString('zh-CN', { hour12: false })
}

onMounted(() => {
  updateClock()
  _clock = setInterval(updateClock, 1000)
  fetchAll()
  fetchWorkflow()
  startPolling()
})

onUnmounted(() => {
  stopPolling()
  clearInterval(_clock)
})

watch(pollInterval, (v) => {
  if (polling.value) { stopPolling(); startPolling() }
})
</script>

<style scoped>
.workflow-root {
  max-width: var(--content-max-width, 1200px);
  margin: 0 auto;
  padding-bottom: var(--space-12);
}

/* ---- 顶栏 ---- */
.top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.top-title {
  font-size: var(--text-2xl);
  font-weight: 700;
  margin: 0;
  color: var(--color-neutral-900);
  letter-spacing: var(--tracking-tight);
}

.top-subtitle {
  font-size: var(--text-sm);
  color: var(--color-neutral-400);
  margin: 2px 0 0;
}

.top-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.top-clock {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  color: var(--color-neutral-400);
  min-width: 70px;
  text-align: right;
}

/* ---- Tabs ---- */
.main-tabs { margin-top: 0; }

/* ---- 泳道网格 ---- */
.swimlane-grid {
  display: flex;
  flex-direction: column;
  gap: 0;
}

/* ---- 单条泳道 ---- */
.swimlane {
  background: #fff;
  border-radius: var(--radius-lg);
  overflow: hidden;
  box-shadow: var(--shadow-sm);
  margin-bottom: var(--space-3);
}

.swimlane-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-3) var(--space-4);
}

.swimlane-header-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.swimlane-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  color: #fff;
  font-size: 11px;
  font-weight: 800;
  flex-shrink: 0;
}

.swimlane-title {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--color-neutral-800);
}

.swimlane-desc {
  font-size: var(--text-xs);
  color: var(--color-neutral-400);
}

/* ---- 泳道 body ---- */
.swimlane-body {
  display: flex;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4) var(--space-4);
  overflow-x: auto;
  flex-wrap: wrap;
}

/* ---- 节点卡片 ---- */
.node-card {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3);
  background: var(--color-neutral-50);
  border: 1px solid var(--color-neutral-200);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all .2s;
  min-width: 180px;
  position: relative;
}

.node-card:hover {
  border-color: var(--color-primary-300);
  box-shadow: var(--shadow-sm);
  transform: translateY(-1px);
}

.node-alert {
  border-color: var(--color-danger-300);
  background: var(--color-danger-50);
}

.node-restored {
  border-color: var(--color-success-400);
  opacity: 0.75;
}

.node-pulse {
  animation: pulse-border 2s infinite;
}

@keyframes pulse-border {
  0%, 100% { border-color: var(--color-danger-300); }
  50% { border-color: var(--color-danger-500); box-shadow: 0 0 6px rgba(239,68,68,0.3); }
}

.node-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.bg-success { background: #10b981; }
.bg-warn    { background: #f59e0b; }
.bg-danger  { background: #ef4444; }

.node-content {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
}

.node-title {
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--color-neutral-700);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.node-value {
  font-family: var(--font-mono);
  font-size: var(--text-lg);
  font-weight: 700;
  color: var(--color-neutral-800);
}

.text-danger { color: var(--color-danger-600); }

.node-sub {
  font-size: 11px;
  color: var(--color-neutral-400);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.node-alert-dot {
  position: absolute;
  top: -4px;
  right: -4px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #ef4444;
  box-shadow: 0 0 4px rgba(239,68,68,0.5);
}

.node-skill { min-width: 160px; }
.node-trace { min-width: 200px; }
.node-empty {
  font-size: var(--text-sm);
  color: var(--color-neutral-400);
  padding: var(--space-4);
}

/* ---- 泳道间箭头 ---- */
.lane-arrow {
  display: flex;
  justify-content: center;
  padding: var(--space-1) 0;
  color: var(--color-neutral-300);
  font-size: 11px;
}

/* ---- 模板面板 ---- */
.template-panel { margin-top: 0; }

.section-card {
  background: #fff;
  border: 1px solid var(--color-neutral-200);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.section-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--color-neutral-100);
}

.section-card-header h3 { margin: 0; font-size: var(--text-sm); font-weight: 600; }
.section-card-header span { font-size: var(--text-xs); color: var(--color-neutral-400); }

.template-body { padding: var(--space-5); }

/* ---- Skill 卡片网格 ---- */
.skills-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: var(--space-4);
}

.skill-card {
  background: #fff;
  border: 1px solid var(--color-neutral-200);
  border-radius: var(--radius-md);
  padding: var(--space-4);
  cursor: pointer;
  transition: all .2s;
}

.skill-card:hover {
  border-color: var(--color-primary-300);
  box-shadow: var(--shadow-sm);
}

.skill-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-2);
}

.skill-name {
  font-size: var(--text-sm);
  font-weight: 600;
}

.skill-desc {
  font-size: var(--text-xs);
  color: var(--color-neutral-400);
  margin: 0 0 var(--space-2);
  line-height: 1.4;
}

.skill-tags { display: flex; gap: 4px; flex-wrap: wrap; }

/* ---- 抽屉 ---- */
.drawer-grid { margin-bottom: var(--space-2); }
.drawer-row { display: flex; gap: var(--space-2); padding: var(--space-2) 0; border-bottom: 1px solid var(--color-neutral-100); font-size: var(--text-sm); }
.drawer-label { font-weight: 600; color: var(--color-neutral-500); width: 80px; flex-shrink: 0; }
.drawer-value { color: var(--color-neutral-700); word-break: break-all; }
.mono { font-family: var(--font-mono); font-size: var(--text-xs); }

/* 节点进出动画 */
.node-pop-enter-active { transition: all .3s ease; }
.node-pop-leave-active { transition: all .2s ease; }
.node-pop-enter-from { opacity: 0; transform: scale(0.9); }
.node-pop-leave-to { opacity: 0; transform: scale(0.95); }

@media (max-width: 768px) {
  .swimlane-body { flex-wrap: wrap; }
  .top-bar { flex-direction: column; align-items: flex-start; }
  .skills-grid { grid-template-columns: 1fr; }
}
</style>
