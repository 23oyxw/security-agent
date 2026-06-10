<template>
  <div class="skill-flows">
    <div class="page-header">
      <div>
        <h1 class="page-title">Skill Flow 编排</h1>
        <p class="page-subtitle">L2 固定流程 · 安全扫描 · 告警响应 · 命令执行 · 系统清理 · 蓝队安全编排</p>
      </div>
      <div class="page-actions">
        <el-button size="small" type="primary" :loading="loading" @click="loadFlows">
          <el-icon style="margin-right:4px"><Refresh /></el-icon> 刷新
        </el-button>
      </div>
    </div>

    <div v-if="flows.length" class="flow-grid">
      <div v-for="flow in flows" :key="flow.name" class="flow-card">
        <div class="flow-card-header">
          <div class="flow-card-title">
            <div class="flow-icon" :style="{ background: (flow.color || '#4f6ef7') + '15', color: flow.color || '#4f6ef7' }">
              <el-icon :size="18"><component :is="flow.icon || 'SetUp'" /></el-icon>
            </div>
            <span>{{ flow.display_name || flow.name }}</span>
          </div>
          <span class="flow-level">L2</span>
        </div>
        <div class="flow-card-desc">{{ flow.description || '无描述' }}</div>

        <div class="flow-steps">
          <div v-for="(step, si) in flow.steps" :key="si" class="flow-step">
            <div class="step-index">{{ si + 1 }}</div>
            <div class="step-body">
              <div class="step-name">{{ step.step || step.name || `步骤 ${si + 1}` }}</div>
              <div class="step-detail">
                <span v-if="step.tool" class="step-tag tool">{{ step.tool }}</span>
                <span v-if="step.action" class="step-tag action">{{ step.action }}</span>
                <span v-if="step.description" class="step-desc">{{ step.description }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="flow-card-actions">
          <el-button size="small" type="primary" :loading="runningFlows[flow.name]" @click="runFlow(flow)">
            <el-icon><CaretRight /></el-icon> 运行
          </el-button>
          <el-button size="small" plain @click="showFlowDetail(flow)">查看详情</el-button>
        </div>

        <div v-if="flowResults[flow.name]" class="flow-result" :class="flowResults[flow.name].ok ? 'success' : 'error'">
          <div class="flow-result-header">
            <el-icon v-if="flowResults[flow.name].ok" :size="14" color="var(--color-success)"><CircleCheckFilled /></el-icon>
            <el-icon v-else :size="14" color="var(--color-danger)"><CircleCloseFilled /></el-icon>
            <span>
              {{ flowResults[flow.name].ok ? '✓ 通过' : '✗ 失败' }}
              <span v-if="flowResults[flow.name].blocked" style="color:var(--color-warning);font-size:11px">(已拦截·安全门生效)</span>
            </span>
            <span class="flow-result-time">{{ flowResults[flow.name].elapsed_ms }}ms</span>
          </div>
          <div v-if="flowResults[flow.name].steps" class="flow-result-steps">
            <div v-for="(s, si) in flowResults[flow.name].steps" :key="si" class="flow-result-step" :class="s.ok === false ? 'fail' : s.blocked ? 'blocked' : 'ok'">
              <span class="step-status-icon">{{ s.ok === false ? '✗' : s.blocked ? '⊘' : '✓' }}</span>
              <span>{{ s.step || `Step ${si + 1}` }}</span>
              <span v-if="s.message || s.error" class="step-msg">{{ s.message || s.error }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-else-if="!loading" class="empty-state">
      <el-icon :size="48" color="var(--color-neutral-200)"><SetUp /></el-icon>
      <p>暂无可用 Flow</p>
    </div>

    <!-- Flow 详情弹窗 -->
    <el-dialog v-model="detailVisible" :title="detailFlow?.display_name || detailFlow?.name" width="640px" class="flow-detail-dialog">
      <div v-if="detailFlow" class="detail-content">
        <div class="detail-meta">
          <span class="detail-meta-item"><strong>名称:</strong> {{ detailFlow.name }}</span>
          <span class="detail-meta-item"><strong>级别:</strong> L2</span>
          <span class="detail-meta-item"><strong>描述:</strong> {{ detailFlow.description }}</span>
        </div>
        <div class="detail-steps">
          <div v-for="(step, si) in detailFlow.steps" :key="si" class="detail-step">
            <div class="detail-step-num">{{ si + 1 }}</div>
            <div class="detail-step-body">
              <div class="detail-step-name">{{ step.step || step.name || `步骤 ${si + 1}` }}</div>
              <div class="detail-step-info">
                <span v-if="step.tool" class="step-tag tool">{{ step.tool }}</span>
                <span v-if="step.action" class="step-tag action">{{ step.action }}</span>
              </div>
              <div v-if="step.description" class="detail-step-desc">{{ step.description }}</div>
              <div v-if="step.args" class="detail-step-args">
                <pre>{{ JSON.stringify(step.args, null, 2) }}</pre>
              </div>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import api from '../api'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const flows = ref([])
const runningFlows = reactive({})
const flowResults = reactive({})
const detailVisible = ref(false)
const detailFlow = ref(null)

async function loadFlows() {
  loading.value = true
  try {
    const res = await api.get('/skills/flows')
    flows.value = res.flows || res || []
  } catch (e) {
    ElMessage.error('加载 Flow 失败: ' + (e.message || '未知'))
  } finally {
    loading.value = false
  }
}

async function runFlow(flow) {
  runningFlows[flow.name] = true
  const t0 = Date.now()
  try {
    const res = await api.post(`/skills/flows/${flow.name}/run`, { context: {} })
    const steps = res.steps || []
    const blocked = steps.some(s => s.blocked)
    const ok = res.ok || blocked  // 拦截 = 安全门正常生效，标记为通过
    flowResults[flow.name] = { ok, steps, elapsed_ms: Date.now() - t0 }
    if (ok && !blocked) {
      ElMessage.success(`${flow.display_name || flow.name} 执行成功`)
    } else if (blocked) {
      ElMessage.warning(`${flow.display_name || flow.name} 已拦截（安全门正常生效）`)
    } else {
      ElMessage.error(`${flow.display_name || flow.name} 执行失败`)
    }
  } catch (e) {
    flowResults[flow.name] = { ok: false, steps: [], elapsed_ms: Date.now() - t0 }
    ElMessage.error('执行失败: ' + (e.message || '未知'))
  } finally {
    runningFlows[flow.name] = false
  }
}

function showFlowDetail(flow) {
  detailFlow.value = flow
  detailVisible.value = true
}

onMounted(loadFlows)
</script>

<style scoped>
.skill-flows {
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

/* ---- Flow 卡片网格 ---- */
.flow-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: var(--space-4);
}

.flow-card {
  background: transparent;
  border: 1px solid var(--color-neutral-200);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
  transition: box-shadow var(--duration-normal) var(--ease-out);
}

.flow-card:hover {
  box-shadow: var(--shadow-md);
}

.flow-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--color-neutral-100);
}

.flow-card-title {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--color-neutral-800);
}

.flow-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
}

.flow-level {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  background: var(--color-warning-bg);
  color: var(--color-warning);
  letter-spacing: var(--tracking-wide);
}

.flow-card-desc {
  padding: var(--space-3) var(--space-5);
  font-size: var(--text-xs);
  color: var(--color-neutral-400);
  border-bottom: 1px solid var(--color-neutral-100);
}

/* ---- 步骤列表 ---- */
.flow-steps {
  padding: var(--space-3) var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.flow-step {
  display: flex;
  gap: var(--space-3);
  align-items: flex-start;
}

.step-index {
  width: 20px;
  height: 20px;
  border-radius: var(--radius-full);
  background: var(--color-neutral-100);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 700;
  color: var(--color-neutral-500);
  flex-shrink: 0;
  margin-top: 1px;
}

.step-body {
  flex: 1;
  min-width: 0;
}

.step-name {
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--color-neutral-700);
  margin-bottom: var(--space-1);
}

.step-detail {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
  align-items: center;
}

.step-tag {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: var(--radius-sm);
}

.step-tag.tool {
  background: var(--color-info-bg);
  color: var(--color-info);
}

.step-tag.action {
  background: var(--color-success-bg);
  color: var(--color-success);
}

.step-desc {
  font-size: var(--text-xs);
  color: var(--color-neutral-400);
}

/* ---- 操作按钮 ---- */
.flow-card-actions {
  display: flex;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-5);
  border-top: 1px solid var(--color-neutral-100);
}

/* ---- 执行结果 ---- */
.flow-result {
  border-top: 1px solid var(--color-neutral-100);
}

.flow-result.success {
  background: var(--color-success-bg);
}

.flow-result.error {
  background: var(--color-danger-bg);
}

.flow-result-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-5);
  font-size: var(--text-xs);
  font-weight: 600;
}

.flow-result-time {
  margin-left: auto;
  font-weight: 500;
  opacity: 0.7;
}

.flow-result-steps {
  padding: 0 var(--space-5) var(--space-2);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.flow-result-step {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-xs);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-sm);
}

.flow-result-step.ok { color: var(--color-success); }
.flow-result-step.fail { color: var(--color-danger); }
.flow-result-step.blocked { color: var(--color-warning); }

.step-status-icon {
  font-weight: 700;
  width: 14px;
  text-align: center;
}

.step-msg {
  color: var(--color-neutral-500);
  margin-left: auto;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 200px;
}

/* ---- 空状态 ---- */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-12);
  color: var(--color-neutral-300);
}

.empty-state p {
  margin: 0;
  font-size: var(--text-sm);
}

/* ---- 详情弹窗 ---- */
.detail-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.detail-meta {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  font-size: var(--text-sm);
  color: var(--color-neutral-600);
}

.detail-meta-item strong {
  color: var(--color-neutral-800);
}

.detail-steps {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.detail-step {
  display: flex;
  gap: var(--space-3);
}

.detail-step-num {
  width: 24px;
  height: 24px;
  border-radius: var(--radius-full);
  background: var(--color-primary-500);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-xs);
  font-weight: 700;
  flex-shrink: 0;
}

.detail-step-body {
  flex: 1;
}

.detail-step-name {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--color-neutral-800);
  margin-bottom: var(--space-1);
}

.detail-step-info {
  display: flex;
  gap: var(--space-1);
  margin-bottom: var(--space-1);
}

.detail-step-desc {
  font-size: var(--text-xs);
  color: var(--color-neutral-500);
}

.detail-step-args pre {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  background: var(--color-neutral-50);
  padding: var(--space-2);
  border-radius: var(--radius-md);
  overflow-x: auto;
  margin: var(--space-2) 0 0;
}

@media (max-width: 768px) {
  .flow-grid { grid-template-columns: 1fr; }
}
</style>
