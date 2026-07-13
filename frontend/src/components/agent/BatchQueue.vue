<template>
  <div class="batch-panel">
    <div class="batch-header">
      <h3>批量指令队列</h3>
      <span class="batch-hint">L1 前置分析 · 每条独立 trace · 共享 batch_id</span>
    </div>
    <el-input
      v-model="batchText"
      type="textarea"
      :rows="4"
      placeholder="每行一条指令&#10;查看 CPU 使用率&#10;分析 auth.log 异常&#10;安全评估：rm -rf /tmp/test"
      :disabled="processing"
    />
    <div class="batch-actions">
      <PipelineBtn
        action="batchEnqueue"
        size="small"
        :loading="processing"
        @click="enqueue"
      />
      <PipelineBtn action="clear" size="small" :disabled="!queue.length" @click="$emit('clear')" />
    </div>
    <div v-if="queue.length" class="queue-list">
      <div
        v-for="item in queue"
        :key="item.id"
        class="queue-item"
        :class="item.status"
        @click="$emit('select', item)"
      >
        <span class="queue-status">{{ statusLabel(item.status) }}</span>
        <span class="queue-msg">{{ item.message }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import PipelineBtn from '../common/PipelineBtn.vue'
import { BATCH_STATUS } from '../../constants/agents'

defineProps({
  queue: { type: Array, default: () => [] },
  processing: { type: Boolean, default: false },
})

const emit = defineEmits(['enqueue', 'clear', 'select'])
const batchText = ref('')

function statusLabel(s) {
  return BATCH_STATUS[s] || s
}

function enqueue() {
  const t = batchText.value.trim()
  if (!t) return
  emit('enqueue', t)
  batchText.value = ''
}
</script>

<style scoped>
.batch-panel { display: flex; flex-direction: column; gap: var(--space-2); }

.batch-header h3 {
  margin: 0;
  font-size: var(--text-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-neutral-500);
}

.batch-hint {
  font-size: var(--text-xs);
  color: var(--color-neutral-400);
}

.batch-actions {
  display: flex;
  gap: var(--space-2);
}

.queue-list {
  max-height: 180px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.queue-item {
  display: flex;
  gap: var(--space-2);
  padding: 6px 8px;
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  cursor: pointer;
  border: 1px solid var(--color-neutral-200);
  transition: background var(--duration-fast);
}

.queue-item:hover { background: var(--color-neutral-50); }
.queue-item.analyzing { border-color: var(--color-primary-300); }
.queue-item.awaiting_approval { border-color: var(--color-warning); }
.queue-item.done { border-color: var(--color-success); opacity: 0.85; }
.queue-item.failed, .queue-item.blocked { border-color: var(--color-danger); }

.queue-status {
  flex-shrink: 0;
  font-weight: 600;
  min-width: 52px;
  color: var(--page-accent, var(--color-primary-600));
}

.queue-msg {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-neutral-700);
}
</style>
