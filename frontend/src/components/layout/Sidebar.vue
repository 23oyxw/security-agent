<template>
  <aside class="sidebar" :class="{ collapsed, overlay }">
    <div class="sidebar-accent"></div>

    <div class="sidebar-header">
      <div class="brand-mark">
        <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
          <rect width="28" height="28" rx="6" fill="url(#sg-brand)"/>
          <path d="M8 14L12 18L20 10" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
          <defs>
            <linearGradient id="sg-brand" x1="0" y1="0" x2="28" y2="28">
              <stop offset="0%" stop-color="var(--color-primary-600, #2563eb)"/>
              <stop offset="100%" stop-color="var(--color-primary-500, #3b82f6)"/>
            </linearGradient>
          </defs>
        </svg>
      </div>
      <transition name="fade">
        <span v-if="!collapsed" class="brand-text">安全运维控制台</span>
      </transition>
    </div>

    <!-- 唯一导航：五层流程 + 三 Agent 色带（旧分组菜单已移除） -->
    <PipelineArchitectureRail
      :collapsed="collapsed"
      :alert-count="alertsStore.unreadCount"
      @expand="$emit('toggle')"
    />

    <div v-if="!collapsed" class="sidebar-footer">
      <div class="footer-links">
        <button
          v-for="link in footerLinks"
          :key="link.path"
          type="button"
          class="footer-link"
          @click="$emit('navigate', link.path)"
        >
          <el-icon :size="14"><component :is="link.icon" /></el-icon>
          {{ link.label }}
        </button>
      </div>
      <div class="status-row" :class="statusClass">
        <span class="status-dot"></span>
        <span class="status-label">{{ statusText }}</span>
      </div>
    </div>
    <div v-else class="sidebar-footer sidebar-footer--mini">
      <div class="status-row status-row--mini" :class="statusClass">
        <span class="status-dot"></span>
      </div>
    </div>

    <div
      v-if="!collapsed"
      class="sidebar-resize-handle"
      title="拖动调整侧栏宽度"
      @pointerdown="$emit('resize-start', $event)"
    />
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useMetricsStore } from '../../stores/metrics'
import { useAlertsStore } from '../../stores/alerts'
import { useBackendStore } from '../../stores/backend'
import { useUserStore } from '../../stores/user'
import { buildSidebarFooterLinks } from '../../constants/navigation'
import PipelineArchitectureRail from './PipelineArchitectureRail.vue'

defineProps({
  collapsed: Boolean,
  overlay: Boolean,
})
defineEmits(['toggle', 'navigate', 'resize-start'])

const route = useRoute()
const metricsStore = useMetricsStore()
const alertsStore = useAlertsStore()
const backendStore = useBackendStore()
const userStore = useUserStore()

const footerLinks = computed(() => buildSidebarFooterLinks(userStore.role))

const statusClass = computed(() => {
  if (!backendStore.online) return 'danger'
  const cpu = metricsStore.cpuPercent || 0
  const mem = metricsStore.memoryPercent || 0
  const alerts = alertsStore.unreadCount || 0
  if (cpu > 90 || mem > 90 || alerts > 10) return 'danger'
  if (cpu > 70 || mem > 70 || alerts > 0) return 'warning'
  return 'healthy'
})

const statusText = computed(() => {
  if (!backendStore.online) return '后端离线'
  if (statusClass.value === 'healthy') return '运行中'
  if (statusClass.value === 'warning') return '高负载'
  return '严重告警'
})
</script>

<style scoped>
.sidebar {
  width: var(--sidebar-width);
  min-width: var(--sidebar-min-width, 300px);
  max-width: var(--sidebar-max-width, 520px);
  background: var(--gradient-sidebar);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  flex-shrink: 0;
  border-right: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: var(--shadow-lg);
  position: relative;
  z-index: 2;
  transition:
    width var(--duration-normal) var(--ease-out),
    min-width var(--duration-normal) var(--ease-out),
    max-width var(--duration-normal) var(--ease-out);
}

body.sidebar-resizing .sidebar {
  transition: none;
}

.sidebar.collapsed {
  width: var(--sidebar-collapsed-width);
  min-width: var(--sidebar-collapsed-width);
  max-width: var(--sidebar-collapsed-width);
}

.sidebar.overlay {
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  z-index: 11;
  max-width: min(var(--sidebar-width), 88vw);
}

.sidebar-accent {
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 2px;
  background: linear-gradient(90deg, #3b82f6 0%, #10b981 50%, #8b5cf6 100%);
  opacity: 0.9;
  z-index: 1;
}

.sidebar-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4);
  height: 56px;
  cursor: pointer;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  user-select: none;
  flex-shrink: 0;
}

.brand-mark { flex-shrink: 0; display: flex; align-items: center; justify-content: center; }
.brand-text {
  color: var(--color-text-inverse);
  font-size: var(--text-sm);
  font-weight: var(--weight-semibold);
  white-space: nowrap;
}

.sidebar-resize-handle {
  position: absolute;
  top: 0;
  right: 0;
  width: 8px;
  height: 100%;
  cursor: col-resize;
  z-index: 20;
  background: transparent;
  transition: background 0.15s;
  touch-action: none;
}

.sidebar-resize-handle:hover,
.sidebar-resize-handle:active {
  background: rgba(96, 165, 250, 0.35);
}

.sidebar-footer {
  padding: var(--space-2) var(--space-3);
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
}

.footer-links {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: var(--space-2);
}

.footer-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.04);
  color: rgba(255, 255, 255, 0.6);
  font-size: 10px;
  cursor: pointer;
}

.footer-link:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.08);
}

.sidebar-footer--mini {
  padding: var(--space-2);
  display: flex;
  justify-content: center;
}

.status-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-xs);
  color: rgba(255, 255, 255, 0.45);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-row.healthy .status-dot {
  background: var(--color-success);
  box-shadow: 0 0 6px rgba(16, 185, 129, 0.5);
}
.status-row.warning .status-dot {
  background: var(--color-warning);
}
.status-row.danger .status-dot {
  background: var(--color-danger);
}

.fade-enter-active, .fade-leave-active { transition: opacity var(--duration-normal) var(--ease-out); }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
