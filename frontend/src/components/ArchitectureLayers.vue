<template>
  <el-card shadow="never" class="arch-card">
    <template #header>
      <div class="arch-header" @click="expanded = !expanded">
        <span>架构分层说明</span>
        <el-icon><component :is="expanded ? 'ArrowUp' : 'ArrowDown'" /></el-icon>
      </div>
    </template>
    <div v-show="expanded" class="arch-body">
      <div class="arch-row" :class="{ active: highlight === 'L3' }">
        <el-tag type="primary" size="small">L3</el-tag>
        <div>
          <strong>编排 · 思考与选择</strong>
          <p>「智能助手」= L3：听懂问题、选 L2 剧本或 L1 工具、LLM 推理总结。</p>
        </div>
      </div>
      <div class="arch-row" :class="{ active: highlight === 'L2' }">
        <el-tag type="success" size="small">L2</el-tag>
        <div>
          <strong>Skill 流程 · 固定多步</strong>
          <p>「Skill 流程」页 4 条 flow，步骤固定、可答辩演示。</p>
        </div>
      </div>
      <div class="arch-row" :class="{ active: highlight === 'L1' }">
        <el-tag type="info" size="small">L1</el-tag>
        <div>
          <strong>原子能力 · 单工具</strong>
          <p>「MCP 管理」页注册的能力；助手消息里「L1 · 工具名」即本层被调用。</p>
        </div>
      </div>
      <div class="arch-row" :class="{ active: highlight === 'trace' }">
        <el-tag type="warning" size="small">Trace</el-tag>
        <div>
          <strong>推理溯源 · 记录黑匣子</strong>
          <p>不是 L3；记录 L3/L2 的执行阶段、工具与 token。</p>
        </div>
      </div>
      <el-button v-if="traceId" type="primary" link size="small" @click="goTrace">查看本条 Trace →</el-button>
    </div>
  </el-card>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const props = defineProps({
  highlight: { type: String, default: 'L3' },
  traceId: { type: String, default: '' },
  defaultExpanded: { type: Boolean, default: false },
})

const expanded = ref(props.defaultExpanded)
const router = useRouter()

function goTrace() {
  if (props.traceId) {
    router.push({ path: '/trace', query: { id: props.traceId } })
  }
}
</script>

<style scoped>
.arch-card { margin-bottom: 12px; }
.arch-card :deep(.el-card__header) { padding: 8px 12px; }
.arch-card :deep(.el-card__body) { padding: 8px 12px 12px; }
.arch-header { display: flex; justify-content: space-between; align-items: center; cursor: pointer; font-size: 13px; font-weight: 600; }
.arch-body { font-size: 12px; color: #606266; }
.arch-row { display: flex; gap: 10px; margin-bottom: 10px; padding: 8px; border-radius: 6px; border: 1px solid transparent; }
.arch-row.active { background: #ecf5ff; border-color: #d9ecff; }
.arch-row p { margin: 4px 0 0; line-height: 1.45; color: #909399; }
</style>
