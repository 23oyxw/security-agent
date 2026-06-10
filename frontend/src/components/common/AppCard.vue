<template>
  <div class="app-card" :class="[size, { hoverable, elevated }]">
    <div v-if="title || $slots.extra" class="card-header">
      <div class="card-title">
        <el-icon v-if="icon" :size="18"><component :is="icon" /></el-icon>
        <span>{{ title }}</span>
      </div>
      <div v-if="$slots.extra" class="card-extra">
        <slot name="extra" />
      </div>
    </div>
    <div class="card-body">
      <slot />
    </div>
    <div v-if="$slots.footer" class="card-footer">
      <slot name="footer" />
    </div>
  </div>
</template>

<script setup>
/**
 * AppCard — 统一卡片组件
 * 提供一致的圆角、阴影、间距和悬浮效果
 *
 * @prop {string} title - 卡片标题
 * @prop {string|object} icon - 标题图标
 * @prop {string} size - 尺寸：sm | md | lg
 * @prop {boolean} hoverable - 是否启用悬浮浮起效果
 * @prop {boolean} elevated - 是否默认提升阴影
 */
defineProps({
  title: String,
  icon: [String, Object],
  size: { type: String, default: 'md', validator: v => ['sm', 'md', 'lg'].includes(v) },
  hoverable: Boolean,
  elevated: Boolean,
})
</script>

<style scoped>
.app-card {
  background: #fff;
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-neutral-200);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.app-card.hoverable:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-lg);
  border-color: var(--color-primary-300);
}

.app-card.elevated {
  box-shadow: var(--shadow-md);
}

/* 尺寸变体 */
.app-card.sm .card-body { padding: var(--space-3); }
.app-card.sm .card-header { padding: var(--space-3) var(--space-4); }

.app-card.md .card-body { padding: var(--space-5); }
.app-card.md .card-header { padding: var(--space-4) var(--space-5); }

.app-card.lg .card-body { padding: var(--space-6); }
.app-card.lg .card-header { padding: var(--space-5) var(--space-6); }

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--color-neutral-100);
}

.card-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--color-neutral-800);
}

.card-extra {
  display: flex;
  align-items: center;
}

.card-footer {
  padding: var(--space-3) var(--space-5);
  border-top: 1px solid var(--color-neutral-100);
  background: var(--color-neutral-50);
  border-radius: 0 0 var(--radius-lg) var(--radius-lg);
}
</style>
