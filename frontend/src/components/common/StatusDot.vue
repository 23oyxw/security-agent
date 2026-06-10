<template>
  <span class="status-dot-wrapper" :class="[status, { pulse }]" :style="sizeStyle">
    <span class="status-dot-core"></span>
    <span v-if="pulse" class="status-dot-ring"></span>
  </span>
</template>

<script setup>
/**
 * StatusDot — 统一状态指示灯组件
 * 提供健康/警告/危险三种状态，可选脉冲环效果
 *
 * @prop {string} status - 状态：healthy | warning | danger
 * @prop {boolean} pulse - 是否显示脉冲环动画
 * @prop {number} size - 点的尺寸（px），默认 8
 */
const props = defineProps({
  status: { type: String, default: 'healthy', validator: v => ['healthy', 'warning', 'danger'].includes(v) },
  pulse: { type: Boolean, default: true },
  size: { type: Number, default: 8 },
})

const sizeStyle = {
  '--dot-size': `${props.size}px`,
}
</script>

<style scoped>
.status-dot-wrapper {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: calc(var(--dot-size) + 8px);
  height: calc(var(--dot-size) + 8px);
  flex-shrink: 0;
}

.status-dot-core {
  width: var(--dot-size);
  height: var(--dot-size);
  border-radius: 50%;
  transition: all var(--duration-fast) var(--ease-out);
}

/* 健康状态 */
.healthy .status-dot-core {
  background: var(--color-success);
  box-shadow: 0 0 6px var(--color-success);
}

/* 警告状态 */
.warning .status-dot-core {
  background: var(--color-warning);
  box-shadow: 0 0 6px var(--color-warning);
}

/* 危险状态 */
.danger .status-dot-core {
  background: var(--color-danger);
  box-shadow: 0 0 8px var(--color-danger);
}

/* 脉冲环 */
.status-dot-ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  opacity: 0;
}

.healthy .status-dot-ring {
  background: var(--color-success);
  animation: pulse-ring 2s ease-in-out infinite;
}

.warning .status-dot-ring {
  background: var(--color-warning);
  animation: pulse-ring 1.2s ease-in-out infinite;
}

.danger .status-dot-ring {
  background: var(--color-danger);
  animation: pulse-ring 0.8s ease-in-out infinite;
}

@keyframes pulse-ring {
  0%, 100% { transform: scale(0.8); opacity: 0.4; }
  50% { transform: scale(1.6); opacity: 0; }
}
</style>
