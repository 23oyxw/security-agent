<template>
  <el-card header="安全门禁 — 三层防御评估 (30/35/35)">
    <el-form :model="form" label-width="100px" style="max-width: 720px">
      <el-form-item label="用户意图">
        <el-input v-model="form.user_message" type="textarea" :rows="2" placeholder="例：帮我查看一下日志目录" />
      </el-form-item>
      <el-form-item label="待执行命令">
        <el-input v-model="form.target" placeholder="例: ls -la /var/log" />
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
import { reactive, ref } from 'vue'
import api from '../api'
import { ElMessage } from 'element-plus'

const form = reactive({ user_message: '', target: '', sudo: false })
const result = ref(null)
const loading = ref(false)
const pending = ref([])
const pendingLoading = ref(false)

const DENY_VERDICTS = new Set(['deny', 'escalate', 'quarantine'])

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
