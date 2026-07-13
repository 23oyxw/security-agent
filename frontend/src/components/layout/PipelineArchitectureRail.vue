<template>
  <div v-if="!collapsed" class="pipeline-rail">
    <header class="rail-header">
      <span class="rail-title">五步刚性流程</span>
      <span class="rail-formula">{{ PIPELINE_FORMULA }}</span>
      <div class="agent-legend">
        <span
          v-for="a in agentLegend"
          :key="a.id"
          class="agent-legend-item"
          :style="{ '--agent-color': a.color }"
        >
          <span class="agent-legend-dot" />
          {{ a.shortLabel }}
          <span class="agent-legend-bracket">{{ a.bracket }}</span>
        </span>
      </div>
    </header>

    <div class="timeline-with-spine">
      <!-- 主线状态灯 -->
      <div class="spine-column" aria-hidden="true">
        <div
          v-for="(node, si) in spineNodes"
          :key="node.id"
          class="spine-segment"
        >
          <span
            class="spine-light"
            :class="[node.state, `agent-${node.agentId}`]"
            :style="{ '--agent-color': node.color }"
            :title="`${node.id} · ${node.state || 'idle'}`"
          />
          <span v-if="si < spineNodes.length - 1" class="spine-wire" :style="{ background: node.color }" />
        </div>
      </div>

      <div class="timeline">
        <template v-for="(layer, idx) in layers" :key="layer.id">
          <div
            v-if="showAgentBracket(layer, idx)"
            class="agent-bracket"
            :style="{ '--agent-color': agentColor(layer.agentId), borderColor: agentColor(layer.agentId) }"
          >
            {{ agentVisual(layer.agentId).shortLabel }}
            <span class="agent-bracket-sub">{{ agentVisual(layer.agentId).bracket }}</span>
          </div>

          <article
            class="layer-card"
            :class="{
              'is-active': activeLayer === layer.id,
              'is-done': isLayerDone(layer.id),
            }"
            :style="{ '--layer-accent': layer.accent, '--agent-color': agentColor(layer.agentId) }"
          >
            <div class="layer-head">
              <span
                class="layer-spine-dot"
                :class="layerStatus(layer.id)"
                :style="{ borderColor: agentColor(layer.agentId), boxShadow: activeLayer === layer.id ? `0 0 8px ${agentColor(layer.agentId)}` : 'none' }"
              />
              <span class="layer-badge">{{ layer.badge }}</span>
              <div class="layer-head-text">
                <h3 class="layer-name">{{ layer.name }}</h3>
                <span v-if="layer.roleTag" class="layer-role-tag">{{ layer.roleTag }}</span>
                <span class="layer-agent">{{ layer.agent }}</span>
              </div>
              <span v-if="layerStatus(layer.id)" class="layer-status" :class="layerStatus(layer.id)">
                {{ statusLabel(layer.id) }}
              </span>
            </div>

            <div v-if="layer.important" class="layer-important">{{ layer.important }}</div>
            <div v-if="layer.constraint" class="layer-constraint">{{ layer.constraint }}</div>

            <div v-if="layer.nested" class="layer-nested">
              <div class="nested-label">{{ layer.nested.label }}</div>
              <div class="nested-grid">
                <component
                  :is="item.path ? 'button' : 'div'"
                  v-for="item in layer.nested.items"
                  :key="item.key"
                  type="button"
                  class="nested-item"
                  :class="{ 'nested-item--link': item.path, 'nested-item--primary': item.primary }"
                  @click="item.path && goExtra(item.path)"
                >
                  <span class="nested-title">
                    {{ item.title }}
                    <span v-if="item.titleEn" class="nested-en">{{ item.titleEn }}</span>
                  </span>
                  <span class="nested-desc">{{ item.desc }}</span>
                  <span v-if="item.path && item.openLabel" class="nested-go">{{ item.openLabel }}</span>
                </component>
              </div>
            </div>

            <ul v-else-if="layer.items?.length" class="layer-tags">
              <li v-for="(t, i) in layer.items" :key="i">{{ t }}</li>
            </ul>

            <RailActionBtn
              :label="actionDef(layer.action).label"
              :layer="layer.id"
              :icon="actionDef(layer.action).icon"
              block
              @click="runAction(layer.action)"
            />

            <div v-if="layer.extras?.length" class="layer-extras">
              <button
                v-for="ex in layer.extras"
                :key="ex.path"
                type="button"
                class="extra-link"
                :class="{ 'is-current': isExtraActive(ex.path) }"
                @mouseenter="prefetchRoute(ex.path)"
                @click="goExtra(ex.path)"
              >
                <el-icon :size="12"><component :is="ex.icon" /></el-icon>
                {{ ex.label }}
                <span v-if="ex.badgeKey && badgeCount(ex.badgeKey)" class="extra-badge">{{ badgeCount(ex.badgeKey) }}</span>
              </button>
            </div>
          </article>

          <div v-if="layer.id === 'L2'" class="gate-connector">
            <div class="connector-line" />
            <div class="gate-card" :class="{ 'is-active': gateActive }">
              <div class="gate-head">
                <span
                  class="layer-spine-dot gate-dot"
                  :class="layerStatus('GATE')"
                  :style="{ borderColor: agentColor(transition.agentId) }"
                />
                <el-icon :size="12" class="gate-icon-el"><ArrowRight /></el-icon>
                <span class="gate-title">{{ transition.title }}</span>
              </div>
              <p class="gate-desc">{{ transition.desc }}</p>
              <div v-if="gateSummary" class="gate-live">{{ gateSummary }}</div>
              <RailActionBtn
                :label="SIDEBAR_ACTIONS.gateExecute.label"
                layer="GATE"
                icon="ArrowRight"
                block
                :disabled="!canSwitchExecute"
                @click="runAction('gateExecute')"
              />
            </div>
            <div class="connector-line" />
          </div>

          <div v-else-if="idx < layers.length - 1 && layer.id !== 'L2'" class="connector-only">
            <div class="connector-line" />
          </div>
        </template>
      </div>
    </div>
  </div>

  <div v-else class="pipeline-mini">
    <template v-for="item in miniLayers" :key="item.id">
      <button
        type="button"
        class="mini-layer"
        :class="{ active: activeLayer === item.id }"
        :style="{ '--mini-accent': item.accent, borderColor: item.accent }"
        :title="item.name"
        @click="onMiniClick(item)"
      >
        {{ item.badge }}
      </button>
      <button
        v-if="item.id === 'L2'"
        type="button"
        class="mini-gate"
        :class="{ active: gateActive, unlocked: canSwitchExecute }"
        title="层间门禁 · plan+L2→execute（非独立层）"
        @click="runAction('gateExecute')"
      >
        ⇒
      </button>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAgentStore } from '../../stores/agent'
import RailActionBtn from './RailActionBtn.vue'
import {
  PIPELINE_FORMULA,
  SIDEBAR_LAYERS,
  SIDEBAR_ACTIONS,
  LAYER_TRANSITION,
  SPINE_ORDER,
} from '../../constants/pipeline-architecture'
import { getActiveLayerForPath, normalizePath } from '../../constants/navigation'
import { LAYER_ACCENTS } from '../../constants/layer-colors'
import { buildAgentQuery, buildL5Query, buildSafetyQuery, buildTraceQuery } from '../../utils/pipeline-context'
import { AGENT_VISUAL, agentVisual, agentColor } from '../../constants/agent-visual'

const props = defineProps({
  collapsed: Boolean,
  alertCount: { type: Number, default: 0 },
})
defineEmits(['expand'])

const router = useRouter()
const route = useRoute()
const agentStore = useAgentStore()

const layers = SIDEBAR_LAYERS
const transition = LAYER_TRANSITION
const agentLegend = Object.values(AGENT_VISUAL)

const miniLayers = computed(() => layers)

function onMiniClick(item) {
  if (item.action) runAction(item.action)
}

const PREFETCH_ROUTES = {
  '/l5': () => import('../../views/L5Analytics.vue'),
  '/workflow': () => import('../../views/WorkflowView.vue'),
  '/canvas': () => import('../../views/InfiniteCanvas.vue'),
}

function prefetchRoute(path) {
  PREFETCH_ROUTES[path]?.()
}

const spineNodes = computed(() =>
  SPINE_ORDER.map(id => {
    const agentId = id === 'GATE' ? transition.agentId : (layers.find(l => l.id === id)?.agentId || 'core_dispatch')
    return {
      id,
      agentId,
      color: agentColor(agentId),
      state: layerStatus(id),
    }
  }),
)

function showAgentBracket(layer, idx) {
  if (idx === 0) return true
  return layers[idx - 1].agentId !== layer.agentId
}

function badgeCount(key) {
  if (key === 'alerts') return props.alertCount
  return 0
}

function goExtra(path) {
  prefetchRoute(path)
  router.push(path)
}

function isExtraActive(path) {
  const p = normalizePath(route.path)
  const target = normalizePath(path)
  return p === target || p.startsWith(`${target}/`)
}

const routeLayer = computed(() =>
  getActiveLayerForPath(route.path, { agentMode: agentStore.mode }),
)

const activeLayer = computed(() => {
  const fromRoute = routeLayer.value
  if (fromRoute && route.path !== '/agent') return fromRoute

  const p = agentStore.dispatchPhase
  if (p === 'executed') return 'L5'
  if (p === 'execute' || agentStore.mode === 'execute') return 'L3'
  if (agentStore.currentPlan) return 'L2'
  return fromRoute || 'L1'
})

const canSwitchExecute = computed(() => {
  return Boolean(agentStore.currentPlan?.plan_id) && agentStore.canExecute
})

const gateActive = computed(() => {
  if (!agentStore.currentPlan || agentStore.isBlocked) return false
  if (!canSwitchExecute.value) return false
  const p = agentStore.dispatchPhase
  return agentStore.mode === 'execute' && !['execute', 'executed'].includes(p)
})

const gateSummary = computed(() => {
  if (!agentStore.currentPlan) return '等待 L1 生成 plan'
  const v = agentStore.l2Result?.verdict || agentStore.currentPlan.l2_verdict
  if (!v) return '等待 L2 预检'
  const map = { pass: 'L2 已通过，可切换执行模式', confirm: '需二次确认', deny: 'L2 拒绝，不可执行' }
  return map[v] || v
})

function actionDef(key) {
  return SIDEBAR_ACTIONS[key] || { label: key, icon: 'Right' }
}

function isLayerDone(id) {
  const order = ['L1', 'L2', 'L3', 'L4', 'L5']
  const ai = order.indexOf(activeLayer.value)
  const li = order.indexOf(id)
  return li >= 0 && ai > li
}

function layerStatus(id) {
  if (id === 'GATE') {
    if (gateActive.value) return 'running'
    if (canSwitchExecute.value) return 'done'
    return ''
  }
  if (activeLayer.value === id) return 'running'
  if (isLayerDone(id)) return 'done'
  if (id === 'L3' && agentStore.isBlocked) return 'blocked'
  return 'idle'
}

function statusLabel(id) {
  const s = layerStatus(id)
  return { running: '进行中', done: '已完成', blocked: '拒绝' }[s] || ''
}

function runAction(actionKey) {
  switch (actionKey) {
    case 'l1PlanMode':
      agentStore.setMode('plan')
      router.push({ path: '/agent', query: buildAgentQuery(agentStore, { tab: 'pipeline' }) })
      break
    case 'l2Safety':
      router.push({ path: '/safety', query: buildSafetyQuery(agentStore) })
      break
    case 'l3ExecuteMode':
    case 'gateExecute':
      agentStore.setMode('execute')
      if (agentStore.currentPlan?.plan_id && agentStore.canExecute) {
        router.push({
          path: '/agent',
          query: buildAgentQuery(agentStore, {
            tab: 'plan',
            autorun: agentStore.needsConfirm ? '0' : '1',
            toL5: '1',
          }),
        })
      } else {
        router.push({ path: '/agent', query: buildAgentQuery(agentStore, { tab: 'pipeline' }) })
      }
      break
    case 'l4Trace':
      router.push({ path: '/trace', query: buildTraceQuery(agentStore) })
      break
    case 'l5Dashboard':
      prefetchRoute('/l5')
      router.push({ path: '/l5', query: buildL5Query(agentStore) })
      break
    default:
      break
  }
}
</script>

<style scoped>
.pipeline-rail {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 0 var(--space-2) var(--space-3);
}

.pipeline-rail::-webkit-scrollbar { width: 3px; }
.pipeline-rail::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.12);
  border-radius: 4px;
}

.rail-header {
  position: sticky;
  top: 0;
  z-index: 2;
  padding: var(--space-2) var(--space-1);
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.98) 70%, transparent);
}

.rail-title {
  display: block;
  font-size: var(--text-sm);
  font-weight: 700;
  color: rgba(255, 255, 255, 0.92);
}

.rail-formula {
  font-size: 9px;
  color: rgba(255, 255, 255, 0.4);
}

.agent-legend {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 8px;
}

.agent-legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 9px;
  color: rgba(255, 255, 255, 0.75);
}

.agent-legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--agent-color);
  box-shadow: 0 0 6px var(--agent-color);
  flex-shrink: 0;
}

.agent-legend-bracket {
  color: rgba(255, 255, 255, 0.38);
  font-size: 8px;
}

.timeline-with-spine {
  display: flex;
  gap: 10px;
  align-items: stretch;
}

.spine-column {
  width: 14px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: 6px;
}

.spine-segment {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
  min-height: 48px;
}

.spine-light {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 2px solid var(--agent-color);
  background: rgba(15, 23, 42, 0.9);
  flex-shrink: 0;
  transition: background 0.2s, box-shadow 0.2s;
}

.spine-light.running {
  background: var(--agent-color);
  box-shadow: 0 0 10px var(--agent-color);
  animation: spine-pulse 1.4s ease-in-out infinite;
}

.spine-light.done { background: var(--agent-color); opacity: 0.85; }
.spine-light.blocked { background: #ef4444; border-color: #ef4444; }
.spine-light.idle { opacity: 0.45; }

.spine-wire {
  width: 2px;
  flex: 1;
  min-height: 12px;
  margin: 2px 0;
  opacity: 0.35;
  border-radius: 1px;
}

@keyframes spine-pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.15); opacity: 0.75; }
}

.agent-bracket {
  font-size: 9px;
  font-weight: 700;
  color: var(--agent-color);
  padding: 4px 8px;
  margin: 8px 0 4px;
  border-left: 3px solid var(--agent-color);
  background: color-mix(in srgb, var(--agent-color) 12%, transparent);
  border-radius: 0 6px 6px 0;
}

.agent-bracket-sub {
  font-weight: 400;
  color: rgba(255, 255, 255, 0.45);
  margin-left: 4px;
}

.timeline {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0;
  padding-bottom: var(--space-2);
}

.layer-spine-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  border: 2px solid;
  flex-shrink: 0;
  margin-top: 4px;
}

.layer-spine-dot.running { background: currentColor; }
.layer-spine-dot.done { background: var(--agent-color); border-color: var(--agent-color); }

.layer-extras {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
}

.extra-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: 4px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
  color: rgba(255, 255, 255, 0.65);
  font-size: 9px;
  cursor: pointer;
}

.extra-link:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
}

.extra-link.is-current {
  border-color: rgba(96, 165, 250, 0.55);
  background: rgba(96, 165, 250, 0.18);
  color: #fff;
}

.extra-badge {
  background: var(--color-danger, #ef4444);
  color: #fff;
  font-size: 8px;
  padding: 0 4px;
  border-radius: 8px;
  min-width: 14px;
  text-align: center;
}

/* ---- 层卡片 ---- */
.layer-card {
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-left: 3px solid var(--agent-color, var(--layer-accent));
  border-radius: 8px;
  padding: 10px;
  background: rgba(0, 0, 0, 0.18);
  transition: border-color 0.2s, box-shadow 0.2s;
}

.layer-card.is-active {
  border-color: color-mix(in srgb, var(--layer-accent) 55%, transparent);
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--layer-accent) 25%, transparent);
  background: rgba(0, 0, 0, 0.28);
}

.layer-card.is-done { opacity: 0.72; }

.layer-head {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 8px;
}

.layer-badge {
  flex-shrink: 0;
  font-size: var(--text-xs);
  font-weight: 800;
  color: #fff;
  background: var(--layer-accent);
  padding: 2px 6px;
  border-radius: 4px;
}

.layer-head-text { flex: 1; min-width: 0; }

.layer-name {
  margin: 0;
  font-size: var(--text-sm);
  font-weight: 700;
  color: rgba(255, 255, 255, 0.95);
  line-height: 1.2;
}

.layer-role-tag {
  display: inline-block;
  margin-right: 4px;
  font-size: 8px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.12);
  color: rgba(255, 255, 255, 0.75);
  vertical-align: middle;
}

.layer-agent {
  font-size: 9px;
  color: rgba(255, 255, 255, 0.45);
}

.layer-status {
  flex-shrink: 0;
  font-size: 8px;
  font-weight: 700;
  padding: 2px 5px;
  border-radius: 4px;
  text-transform: uppercase;
}

.layer-status.running { background: rgba(59, 130, 246, 0.35); color: #93c5fd; }
.layer-status.done { background: rgba(16, 185, 129, 0.25); color: #6ee7b7; }
.layer-status.blocked { background: rgba(239, 68, 68, 0.25); color: #fca5a5; }

.layer-important {
  font-size: 9px;
  line-height: 1.45;
  padding: 6px 8px;
  margin-bottom: 6px;
  border-radius: 6px;
  background: rgba(251, 191, 36, 0.12);
  border: 1px solid rgba(251, 191, 36, 0.28);
  color: #fde68a;
}

.layer-constraint {
  font-size: 8px;
  color: #fca5a5;
  margin-bottom: 6px;
  opacity: 0.9;
}

/* L1 内嵌并行 */
.layer-nested {
  margin-bottom: 8px;
  padding: 8px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px dashed rgba(96, 165, 250, 0.25);
}

.nested-label {
  font-size: 8px;
  font-weight: 700;
  color: #93c5fd;
  margin-bottom: 6px;
  letter-spacing: 0.04em;
}

.nested-grid {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.nested-item {
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding: 6px 8px;
  padding-left: 8px;
  border-left: 2px solid rgba(96, 165, 250, 0.35);
  text-align: left;
  background: transparent;
  border-top: none;
  border-right: none;
  border-bottom: none;
  width: 100%;
  font: inherit;
  color: inherit;
}

.nested-item--link {
  cursor: pointer;
  border-radius: 4px;
  transition: background 0.15s;
}

.nested-item--link:hover {
  background: rgba(96, 165, 250, 0.12);
}

.nested-item--primary {
  border-left-color: #34d399;
  background: rgba(52, 211, 153, 0.08);
}

.nested-en {
  margin-left: 4px;
  font-size: 8px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.35);
}

.nested-go {
  font-size: 8px;
  color: #93c5fd;
  margin-top: 2px;
}

.nested-title {
  font-size: 9px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.85);
}

.nested-desc {
  font-size: 8px;
  color: rgba(255, 255, 255, 0.45);
  line-height: 1.35;
}

.layer-tags {
  margin: 0 0 8px;
  padding: 0;
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.layer-tags li {
  font-size: 8px;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.55);
}

/* ---- 层间过渡 ---- */
.gate-connector {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  padding: 2px 0;
}

.connector-line {
  width: 2px;
  height: 10px;
  margin: 0 auto;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.08), rgba(255, 255, 255, 0.2));
}

.connector-only .connector-line {
  height: 14px;
}

.gate-card {
  padding: 8px 10px;
  border-radius: 6px;
  border: 1px dashed rgba(255, 255, 255, 0.18);
  background: rgba(255, 255, 255, 0.04);
}

.gate-card.is-active {
  border-color: rgba(255, 255, 255, 0.35);
  background: rgba(255, 255, 255, 0.07);
}

.gate-head {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}

.gate-icon-el { color: rgba(255, 255, 255, 0.5); }

.gate-title {
  font-size: var(--text-xs);
  font-weight: 600;
  color: rgba(255, 255, 255, 0.8);
}

.gate-desc {
  margin: 0 0 6px;
  font-size: 8px;
  color: rgba(255, 255, 255, 0.45);
}

.gate-live {
  font-size: 9px;
  padding: 4px 6px;
  margin-bottom: 6px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.2);
  color: rgba(255, 255, 255, 0.65);
}

/* ---- 折叠态 ---- */
.pipeline-mini {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: var(--space-2) 0;
  flex: 1;
  overflow-y: auto;
}

.mini-layer {
  width: 40px;
  height: 32px;
  border: 2px solid;
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.25);
  color: rgba(255, 255, 255, 0.85);
  font-size: 9px;
  font-weight: 800;
  font-family: var(--font-mono);
  cursor: pointer;
  padding: 0;
  transition: background 0.15s, transform 0.15s;
}

.mini-layer:hover {
  background: color-mix(in srgb, var(--mini-accent) 28%, rgba(0, 0, 0, 0.3));
  transform: scale(1.05);
}

.mini-layer.active {
  background: color-mix(in srgb, var(--mini-accent) 45%, rgba(0, 0, 0, 0.2));
  color: #fff;
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--mini-accent) 35%, transparent);
}

.mini-gate {
  width: 28px;
  height: 22px;
  border: 1px dashed rgba(251, 146, 60, 0.45);
  border-radius: 4px;
  background: rgba(251, 146, 60, 0.1);
  color: #fdba74;
  font-size: var(--text-sm);
  font-weight: 700;
  cursor: pointer;
  padding: 0;
  line-height: 1;
}

.mini-gate.unlocked {
  border-style: solid;
}

.mini-gate.active {
  background: rgba(251, 146, 60, 0.28);
  box-shadow: 0 0 0 1px rgba(251, 146, 60, 0.35);
}
</style>
