<template>
  <div>
    <PageHeader
      :title="pageMeta.label"
      :subtitle="pageMeta.subtitle"
      :layer="pageMeta.layer"
    />
    <ArchitectureLayers highlight="L3" :default-expanded="true" />
    <el-card>
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span>MCP 服务注册 · 四工具簇</span>
          <div style="display:flex;gap:8px">
            <el-tag type="info">服务: {{ servers.length }}</el-tag>
            <el-tag type="success">工具: {{ totalTools }}</el-tag>
            <el-tag v-if="lastCheckLabel" type="info" size="small">上次检查: {{ lastCheckLabel }}</el-tag>
            <el-button type="warning" size="small" :loading="mcpStore.loading" @click="doReload">热插拔 Reload</el-button>
            <el-button type="success" size="small" :loading="checkingAll" @click="checkAllHealth">全部健康检查</el-button>
            <el-button type="primary" size="small" :loading="mcpStore.loading" @click="fetch">刷新列表</el-button>
          </div>
        </div>
      </template>

      <el-alert type="info" :closable="false" show-icon style="margin-bottom:12px"
        title="L3 execute 阶段调用 MCP/Skill。本页负责 L3 工具簇注册、健康检查与热插拔 — L1/L2 禁止直接调工具。" />

      <el-table :data="servers" v-loading="mcpStore.loading" stripe empty-text="暂无 MCP 服务">
        <el-table-column prop="name" label="服务名" width="180">
          <template #default="{ row }">
            <div style="display:flex;align-items:center;gap:6px">
              <el-icon :color="row.status === 'running' ? '#67C23A' : row.status === 'error' ? '#F56C6C' : '#909399'">
                <component :is="row.status === 'running' ? 'CircleCheckFilled' : row.status === 'error' ? 'CircleCloseFilled' : 'RemoveFilled'" />
              </el-icon>
              <span style="font-weight:500">{{ row.name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'running' ? 'success' : row.status === 'error' ? 'danger' : 'info'" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="protocol" label="协议" width="80" />
        <el-table-column prop="command" label="命令" show-overflow-tooltip />
        <el-table-column prop="tools_count" label="工具数" width="80" align="center">
          <template #default="{ row }">
            <el-tag type="info" size="small">{{ row.tools_count || 0 }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="上次检查" width="180">
          <template #default="{ row }">{{ formatTime(row.last_health_check) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="viewTools(row)">查看工具</el-button>
            <el-button text type="success" size="small" @click="healthCheck(row)">健康检查</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 工具调用统计（MCP 评分维度硬性要求） -->
    <el-card style="margin-top:16px" v-loading="statsLoading">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span>工具调用统计</span>
          <el-button size="small" text type="primary" @click="fetchStats">刷新统计</el-button>
        </div>
      </template>
      <div v-if="toolStats" class="stats-grid">
        <div class="stat-item">
          <div class="stat-num">{{ toolStats.total_tools }}</div>
          <div class="stat-label">已追踪工具</div>
        </div>
        <div class="stat-item">
          <div class="stat-num">{{ toolStats.total_calls }}</div>
          <div class="stat-label">总调用次数</div>
        </div>
        <div class="stat-item">
          <div class="stat-num" :style="{ color: toolStats.overall_success_rate >= 0.95 ? '#10b981' : '#f59e0b' }">{{ (toolStats.overall_success_rate * 100).toFixed(1) }}%</div>
          <div class="stat-label">成功率</div>
        </div>
      </div>
      <el-table v-if="toolStats && Object.keys(toolStats.tools).length" :data="statsTableData" size="small" stripe style="margin-top:12px" empty-text="暂无调用记录">
        <el-table-column prop="name" label="工具名" width="200" />
        <el-table-column prop="calls" label="调用次数" width="100" align="center" />
        <el-table-column prop="success_rate" label="成功率" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.success_rate >= 0.95 ? 'success' : row.success_rate >= 0.8 ? 'warning' : 'danger'" size="small">{{ (row.success_rate * 100).toFixed(0) }}%</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="avg_latency_ms" label="平均延迟" width="100" align="center">
          <template #default="{ row }">{{ row.avg_latency_ms.toFixed(1) }}ms</template>
        </el-table-column>
        <el-table-column prop="last_error" label="最近错误" show-overflow-tooltip />
      </el-table>
      <el-empty v-else-if="toolStats && !Object.keys(toolStats.tools).length" description="暂无工具调用记录 — 使用 AgentChat 或终端执行后自动统计" />
    </el-card>

    <!-- 工具详情对话框 -->
    <el-dialog v-model="toolDialog" :title="`${selectedServer} 的工具列表`" width="700px">
      <el-table :data="toolList" stripe size="small" empty-text="暂无工具">
        <el-table-column prop="name" label="工具名" width="180" />
        <el-table-column prop="description" label="描述" show-overflow-tooltip />
        <el-table-column label="参数" width="80" align="center">
          <template #default="{ row }">
            <el-tag size="small">{{ Object.keys(row.input_schema?.properties || {}).length }} 个</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../api'
import { useMcpStore } from '../stores/mcp'
import ArchitectureLayers from '../components/ArchitectureLayers.vue'
import PageHeader from '../components/common/PageHeader.vue'
import { NAV_PAGES } from '../constants/navigation'
import { ElMessage } from 'element-plus'

const pageMeta = NAV_PAGES.mcp

const mcpStore = useMcpStore()
const toolDialog = ref(false)
const toolList = ref([])
const selectedServer = ref('')

const checkingAll = ref(false)
const lastCheckLabel = ref('')
const statsLoading = ref(false)
const toolStats = ref(null)
const statsTableData = computed(() => {
  if (!toolStats.value?.tools) return []
  return Object.entries(toolStats.value.tools).map(([name, d]) => ({ name, ...d }))
})

const servers = computed(() => mcpStore.servers)
const totalTools = computed(() => mcpStore.tools.length || servers.value.reduce((s, srv) => s + (srv.tools_count || 0), 0))

function formatTime(ts) {
  if (!ts) return '--'
  if (typeof ts === 'number') return new Date(ts * 1000).toLocaleString('zh-CN')
  return String(ts).replace('T', ' ').slice(0, 19)
}

async function fetch() {
  await mcpStore.refresh()
}

async function doReload() {
  try {
    const res = await mcpStore.reload()
    ElMessage.success(`已重载 ${res.servers_count ?? mcpStore.servers.length} 个 MCP 服务`)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '重载失败')
  }
}

function viewTools(row) {
  selectedServer.value = row.name
  // 兼容两种数据格式: tools 已加载 或 tools_count 仅有计数
  if (row.tools?.length) {
    toolList.value = row.tools
  } else if (row.tools_count) {
    toolList.value = [{ name: '_info', description: `${row.tools_count} 个工具已注册（点击健康检查刷新详情）` }]
  } else {
    toolList.value = mcpStore.tools.filter(t => t.server_name === row.name)
  }
  toolDialog.value = true
}

async function checkAllHealth() {
  checkingAll.value = true
  try {
    const res = await api.post('/mcp/health')
    lastCheckLabel.value = formatTime(res.checked_at || Date.now() / 1000)
    await fetch()
    ElMessage.success(`已检查 ${(res.results || []).length} 个服务`)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '健康检查失败')
  } finally {
    checkingAll.value = false
  }
}

async function healthCheck(row) {
  try {
    const res = await api.post(`/mcp/servers/${row.name}/health`)
    lastCheckLabel.value = formatTime(res.timestamp)
    await fetch()
    ElMessage.success(`${row.name}: ${res.status}`)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '检查失败')
  }
}

async function fetchStats() {
  statsLoading.value = true
  try {
    const res = await api.get('/mcp/stats')
    toolStats.value = res.data
  } catch { toolStats.value = null }
  finally { statsLoading.value = false }
}

onMounted(async () => {
  await fetch()
  await fetchStats()
})
</script>

<style scoped>
.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}
.stat-item {
  text-align: center;
  padding: var(--space-4);
  background: var(--glass-surface, var(--color-neutral-50));
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-glass-outer, var(--color-neutral-200));
}
.stat-num {
  font-size: var(--text-2xl);
  font-weight: 800;
  color: var(--color-primary-600);
}
.stat-label {
  font-size: var(--text-sm);
  color: var(--color-neutral-500);
  margin-top: 4px;
}
</style>