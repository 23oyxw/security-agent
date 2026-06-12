<template>
  <button
    type="button"
    class="rail-btn"
    :class="[`rail-btn--${layer}`, { 'is-disabled': disabled, 'is-block': block }]"
    :disabled="disabled"
    @click="$emit('click')"
  >
    <el-icon v-if="icon" :size="13"><component :is="icon" /></el-icon>
    <span>{{ label }}</span>
  </button>
</template>

<script setup>
defineProps({
  label: { type: String, required: true },
  layer: { type: String, default: 'L1' },
  icon: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
  block: { type: Boolean, default: true },
})
defineEmits(['click'])
</script>

<style scoped>
.rail-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  padding: 6px 10px;
  border-radius: 6px;
  border: 1px solid transparent;
  font-size: 10px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s, opacity 0.15s;
  width: auto;
}

.rail-btn.block { width: 100%; }

.rail-btn--L1 { background: rgba(59, 130, 246, 0.25); color: #bfdbfe; border-color: rgba(96, 165, 250, 0.4); }
.rail-btn--L2 { background: rgba(16, 185, 129, 0.2); color: #a7f3d0; border-color: rgba(52, 211, 153, 0.35); }
.rail-btn--L3 { background: rgba(245, 158, 11, 0.2); color: #fde68a; border-color: rgba(251, 191, 36, 0.35); }
.rail-btn--L4 { background: rgba(139, 92, 246, 0.2); color: #ddd6fe; border-color: rgba(167, 139, 250, 0.35); }
.rail-btn--L5 { background: rgba(14, 165, 233, 0.2); color: #bae6fd; border-color: rgba(56, 189, 248, 0.35); }
.rail-btn--GATE { background: rgba(255, 255, 255, 0.08); color: rgba(255, 255, 255, 0.75); border-color: rgba(255, 255, 255, 0.15); }

.rail-btn:hover:not(:disabled) { filter: brightness(1.12); }
.rail-btn.is-disabled { opacity: 0.45; cursor: not-allowed; }
</style>
