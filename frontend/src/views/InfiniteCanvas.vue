<template>
  <div class="canvas-shell">
    <!-- 画布顶栏 -->
    <div class="canvas-topbar">
      <div class="canvas-topbar-left">
        <el-button size="small" text @click="$router.push('/agent')"><el-icon><ArrowLeft /></el-icon> 返回对话</el-button>
        <el-divider direction="vertical" />
        <span class="canvas-title">{{ canvasMeta.title }}</span>
        <el-tag size="small" type="info" effect="plain">{{ canvasMeta.formula }}</el-tag>
        <span class="canvas-hint">主线 Main · 左侧辅线 Rail · 点层标签跳转</span>
        <el-tag v-if="liveConnected" size="small" type="success" effect="dark">● 实时</el-tag>
      </div>
      <div class="canvas-topbar-right">
        <el-button size="small" @click="fitView"><el-icon><FullScreen /></el-icon> 适应</el-button>
        <el-button size="small" @click="autoLayout" type="primary"><el-icon><Grid /></el-icon> 自动布局</el-button>
        <span class="canvas-clock">{{ now }}</span>
      </div>
    </div>

    <!-- VueFlow 视口 -->
    <div class="canvas-viewport" ref="viewportRef">
      <!-- 五层分割带 + 跳转 -->
      <div class="canvas-layer-bands" aria-hidden="true">
        <div
          v-for="band in layerBands"
          :key="band.layer"
          class="canvas-band"
          :class="{ 'is-active': activeBand === band.layer }"
          :style="{ top: band.y + 'px', height: band.h + 'px', '--band-accent': band.accent }"
          @click="jumpToLayer(band.layer)"
        >
          <button type="button" class="canvas-band-btn" :title="`跳转 ${band.label}`">
            <span class="canvas-band-id">{{ band.layer }}</span>
            <span class="canvas-band-cn">{{ band.label }}</span>
            <span class="canvas-band-en">{{ band.labelEn }}</span>
          </button>
        </div>
        <div class="canvas-col-head canvas-col-rail">辅线 Left Rail</div>
        <div class="canvas-col-head canvas-col-spine">主线 Main Spine</div>
      </div>

      <!-- 层快捷导航 -->
      <nav class="canvas-layer-nav">
        <button
          v-for="band in layerBands"
          :key="'nav-' + band.layer"
          type="button"
          class="layer-nav-btn"
          :class="{ active: activeBand === band.layer }"
          :style="{ '--nav-accent': band.accent }"
          @click="jumpToLayer(band.layer)"
        >
          {{ band.layer }}
        </button>
      </nav>
      <VueFlow
        ref="vueFlowRef"
        v-model:nodes="nodes"
        v-model:edges="edges"
        :default-viewport="{ zoom: 0.45, x: 40, y: 20 }"
        :min-zoom="0.12" :max-zoom="4"
        :nodes-draggable="true" :nodes-connectable="false"
        fit-view-on-init
        @node-click="onNodeClick"
        @node-double-click="onNodeDblClick"
        @pane-click="selectedNode = null"
      >
        <Background :gap="30" :size="1" pattern-color="rgba(148,163,184,0.18)" />

        <!-- 监控节点 (Monitor) -->
        <template #node-monitor="props">
          <div
            class="cv-node cv-node--monitor"
            :class="nodeTierClass(props.data)"
            :style="{ borderColor: props.data.accent }"
          >
            <div class="cv-node-ring" :style="{ '--pct': props.data.percent || 0 }"></div>
            <div class="cv-node-body">
              <span class="cv-node-label">{{ props.data.label }}</span>
              <span v-if="props.data.labelEn" class="cv-node-label-en">{{ props.data.labelEn }}</span>
              <span class="cv-node-value" :class="{ 'is-danger': props.data.alert }">{{ props.data.value }}</span>
              <span class="cv-node-sub">{{ props.data.sub }}</span>
            </div>
            <div class="cv-node-bar">
              <div
                class="cv-node-bar-fill"
                :style="{
                  width: (props.data.percent || 0) + '%',
                  background: props.data.alert ? 'var(--color-danger)' : 'var(--color-success)'
                }"
              ></div>
            </div>
            <Handle type="source" :position="Position.Right" id="out" />
            <Handle type="target" :position="Position.Left" id="in" />
          </div>
        </template>

        <!-- 技能节点 (Skill) -->
        <template #node-skill="props">
          <div class="cv-node cv-node--skill" :class="nodeTierClass(props.data)" :style="{ borderColor: props.data.accent }">
            <div class="cv-node-icon"><el-icon :size="16"><Connection /></el-icon></div>
            <div class="cv-node-body">
              <span class="cv-node-label">{{ props.data.label }}</span>
              <span v-if="props.data.labelEn" class="cv-node-label-en">{{ props.data.labelEn }}</span>
              <span class="cv-node-sub">{{ props.data.toolsLabel || (props.data.tools + ' 工具') }}</span>
            </div>
            <Handle type="source" :position="Position.Right" id="out" />
            <Handle type="target" :position="Position.Left" id="in" />
          </div>
        </template>

        <!-- 快照节点 (Snapshot) -->
        <template #node-snapshot="props">
          <div
            class="cv-node cv-node--snapshot"
            :class="[nodeTierClass(props.data), { 'cv-node--alert': props.data.alert }]"
            :style="{ borderColor: props.data.accent }"
          >
            <div class="cv-node-dot" :class="props.data.restored ? 'dot-green' : 'dot-orange'"></div>
            <div class="cv-node-body">
              <span class="cv-node-label">{{ props.data.label }}</span>
              <span v-if="props.data.labelEn" class="cv-node-label-en">{{ props.data.labelEn }}</span>
              <span class="cv-node-sub">{{ props.data.time }}</span>
            </div>
            <el-tag v-if="props.data.restored" size="small" type="success">已回滚</el-tag>
            <el-tag v-else size="small" type="warning">{{ props.data.risk }}</el-tag>
            <Handle type="source" :position="Position.Right" id="out" />
            <Handle type="target" :position="Position.Left" id="in" />
          </div>
        </template>

        <!-- 追踪节点 (Trace) -->
        <template #node-trace="props">
          <div
            class="cv-node cv-node--trace"
            :class="[nodeTierClass(props.data), { 'cv-node--alert': !props.data.ok }]"
            :style="{ borderColor: props.data.accent }"
          >
            <div class="cv-node-body cv-node-body--trace-main">
              <span class="cv-node-label">{{ props.data.label }}</span>
              <span v-if="props.data.labelEn" class="cv-node-label-en">{{ props.data.labelEn }}</span>
              <span class="cv-node-sub">{{ props.data.stages }}</span>
            </div>
            <div class="cv-node-trace-stages">
              <span
                v-for="i in (props.data.stageCount || 6)"
                :key="i"
                class="trace-stage-dot"
                :class="i <= (props.data.okStages || 6) ? 'dot-green' : 'dot-gray'"
              ></span>
            </div>
            <Handle type="target" :position="Position.Left" id="in" />
            <Handle type="source" :position="Position.Right" id="out" />
          </div>
        </template>

        <!-- 执行器节点 (Executor) -->
        <template #node-executor="props">
          <div class="cv-node cv-node--executor" :class="nodeTierClass(props.data)" :style="{ borderColor: props.data.accent }">
            <div class="cv-node-icon cv-node-icon--warn"><el-icon :size="14"><CaretRight /></el-icon></div>
            <div class="cv-node-body">
              <span class="cv-node-label">{{ props.data.label }}</span>
              <span v-if="props.data.labelEn" class="cv-node-label-en">{{ props.data.labelEn }}</span>
              <code class="cv-node-cmd">{{ props.data.command }}</code>
            </div>
            <span class="cv-node-status" :class="props.data.status === 'success' ? 'is-success' : 'is-danger'">{{ props.data.statusText || props.data.status }}</span>
            <Handle type="target" :position="Position.Left" id="in" />
            <Handle type="source" :position="Position.Right" id="out" />
          </div>
        </template>

        <Controls position="bottom-right" />
        <MiniMap position="bottom-left" :pannable="true" :zoomable="true" />
      </VueFlow>
    </div>

    <!-- 节点详情抽屉 -->
    <el-drawer v-model="drawerOpen" :title="drawerTitle" size="520px" direction="rtl" class="canvas-drawer">
      <template v-if="drawerData">
        <div class="drawer-section" v-for="(s, si) in drawerSections" :key="si">
          <div class="drawer-section-title">{{ s.title }}</div>
          <div class="drawer-row" v-for="r in s.rows" :key="r.label">
            <span class="drawer-row-label">{{ r.label }}</span>
            <span class="drawer-row-value" :class="{ 'is-mono': r.mono }">{{ r.value }}</span>
          </div>
        </div>
        <div class="drawer-actions" v-if="drawerActions.length">
          <el-button v-for="a in drawerActions" :key="a.label" :type="a.type" size="small" @click="a.action">{{ a.label }}</el-button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { VueFlow, Handle, Position } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import api from '../api'
import {
  CANVAS_META,
  CANVAS_LAYER_BANDS,
  CANVAS_LAYER_META,
  buildCanvasNodes,
  buildCanvasEdges,
  getLayerNodeIds,
} from '../constants/canvas-topology'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import '@vue-flow/minimap/dist/style.css'

const router = useRouter()
const vueFlowRef = ref(null)
const viewportRef = ref(null)
const liveConnected = ref(false)
const now = ref('')
const selectedNode = ref(null)
const drawerOpen = ref(false)
const drawerTitle = ref('')
const drawerData = ref(null)
const drawerSections = ref([])
const drawerActions = ref([])

const canvasMeta = CANVAS_META
const layerBands = CANVAS_LAYER_BANDS
const layerMeta = CANVAS_LAYER_META
const activeBand = ref('L1')

function nodeTierClass(data) {
  const tier = data?.tier || 'rail'
  return {
    [`cv-node--${tier}`]: true,
    'cv-node--alert': data?.alert,
    'cv-node--pulse': data?.alert,
  }
}

async function jumpToLayer(layerId) {
  activeBand.value = layerId
  const ids = getLayerNodeIds(layerId)
  await nextTick()
  if (vueFlowRef.value && ids.length) {
    vueFlowRef.value.fitView({ nodes: ids, padding: 0.35, duration: 350, maxZoom: 0.9 })
  }
}

let pollTimer = null
let clockTimer = null

const nodes = ref([])
const edges = ref([])

function buildNodes() {
  return buildCanvasNodes()
}

function buildEdges() {
  return buildCanvasEdges()
}

function autoLayout() {
  nodes.value = buildNodes()
  edges.value = buildEdges()
  nextTick(() => {
    if (vueFlowRef.value) vueFlowRef.value.fitView({ padding: 0.15, maxZoom: 0.85 })
  })
}

function fitView() {
  if (vueFlowRef.value) vueFlowRef.value.fitView({ padding: 0.2 })
}

// ---- 实时数据轮询 ----
async function fetchLiveData() {
  try {
    const [metrics, mcp, evalRes] = await Promise.all([
      api.get('/perception/metrics').catch(() => null),
      api.get('/mcp/servers').catch(() => []),
      api.get('/eval/score').catch(() => null),
    ])
    liveConnected.value = Boolean(metrics)
    if (metrics) {
      const nd = nodes.value.find(n => n.id === 'rail-l1-static')
      if (nd) {
        const cpu = metrics.cpu_percent ?? 0
        nd.data = {
          ...nd.data,
          value: `${cpu}%`,
          sub: `内存 ${metrics.memory_percent ?? '—'}% · 磁盘 ${metrics.disk_percent ?? '—'}%`,
          percent: cpu,
          alert: cpu > 85,
        }
      }
    }
    if (evalRes?.dimension_scores) {
      const vals = Object.values(evalRes.dimension_scores).filter(v => typeof v === 'number')
      const avg = vals.length ? Math.round(vals.reduce((a, b) => a + b, 0) / vals.length) : 0
      const nd = nodes.value.find(n => n.id === 'spine-l5-analytics')
      if (nd) {
        nd.data = {
          ...nd.data,
          value: `${avg}%`,
          sub: 'L5 六维均值',
          percent: avg,
          alert: avg < 70,
        }
      }
    }
    const clusterIds = ['rail-l3-metrics', 'rail-l3-logs', 'rail-l3-repair', 'rail-l3-schedule']
    if (Array.isArray(mcp)) {
      mcp.slice(0, 4).forEach((s, i) => {
        const nd = nodes.value.find(n => n.id === clusterIds[i])
        if (nd) {
          nd.data = {
            ...nd.data,
            tools: s.tools_count || s.tool_count || s.tools || nd.data.tools,
          }
        }
      })
    }
  } catch {
    liveConnected.value = false
  }
}

const NODE_ROUTES = {
  'spine-l1-input': '/agent',
  'spine-l1-plan': '/agent',
  'spine-l2-verdict': '/safety',
  'spine-gate': '/agent',
  'spine-l3-exec': '/agent',
  'spine-l4-trace': '/trace',
  'spine-l5-analytics': '/l5',
  'rail-l1-boundary': '/l1/boundary',
  'rail-l1-knowledge': '/knowledge',
  'rail-l1-static': '/perception',
  'rail-l2-intent': '/safety',
  'rail-l2-sandbox': '/safety',
  'rail-l2-guard': '/safety',
  'rail-l3-mcp': '/mcp',
  'rail-l3-flow': '/flows',
  'rail-l3-metrics': '/mcp',
  'rail-l3-logs': '/mcp',
  'rail-l3-repair': '/mcp',
  'rail-l3-schedule': '/mcp',
  'rail-l4-chart': '/trace',
  'rail-l4-audit': '/trace',
  'rail-l4-wiki': '/knowledge',
  'rail-l5-scatter': '/l5',
  'rail-l5-heatmap': '/l5',
  'rail-l5-root': '/l5',
  'rail-l5-test': '/l5',
}

function onNodeClick({ node }) {
  if (!node) return
  selectedNode.value = node
  const en = node.data?.labelEn ? ` (${node.data.labelEn})` : ''
  drawerTitle.value = `${node.data?.layer || ''} · ${node.data?.label || node.id}${en}`
  drawerData.value = node.data
  const meta = CANVAS_LAYER_META[node.data?.layer]
  const rows = [
    { label: '节点 ID', value: node.id, mono: true },
    { label: '层级 Layer', value: `${node.data?.layer} · ${meta?.labelEn || ''}` },
    { label: '类型 Type', value: node.data?.tier === 'spine' ? '主线 Main' : '辅线 Rail' },
    { label: 'Agent', value: meta?.agent || '—' },
  ]
  if (node.data?.labelEn) rows.push({ label: 'English', value: node.data.labelEn })
  if (node.data?.command) rows.push({ label: '说明', value: node.data.command })
  if (node.data?.stages) rows.push({ label: '阶段', value: node.data.stages })
  if (node.data?.time) rows.push({ label: '详情', value: node.data.time })
  if (node.data?.value) rows.push({ label: '数值', value: node.data.value })
  drawerSections.value = [{ title: '节点信息 Node', rows }]
  const path = node.data?.route || NODE_ROUTES[node.id]
  const band = layerBands.find(b => b.layer === node.data?.layer)
  drawerActions.value = []
  if (path) drawerActions.value.push({ label: '打开页面 Open', type: 'primary', action: () => router.push(path) })
  if (band?.route) drawerActions.value.push({ label: `定位层 ${band.layer}`, type: 'default', action: () => jumpToLayer(band.layer) })
  drawerOpen.value = true
}

function onNodeDblClick({ node }) {
  const path = node?.data?.route || NODE_ROUTES[node?.id]
  if (path) router.push(path)
}

function updateClock() {
  now.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
}

onMounted(() => {
  autoLayout()
  updateClock()
  clockTimer = setInterval(updateClock, 1000)
  fetchLiveData()
  pollTimer = setInterval(fetchLiveData, 3000)
})

onUnmounted(() => {
  clearInterval(pollTimer)
  clearInterval(clockTimer)
})
</script>

<style scoped>
/* ============================================================
   InfiniteCanvas — 无限画布 (Professional Refinement)
   基于 design-tokens v4 的专业视觉规范
   ============================================================ */

/* ---- 画布外壳 ---- */
.canvas-shell {
  height: calc(100vh - var(--topbar-height, 56px));
  display: flex;
  flex-direction: column;
  background: transparent;
}

.canvas-topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 var(--space-4);
  height: 44px;
  background: rgba(15, 23, 42, 0.88);
  border-bottom: 1px solid var(--color-border-default);
  flex-shrink: 0;
  z-index: 10;
  backdrop-filter: blur(12px);
}

.canvas-topbar-left,
.canvas-topbar-right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.canvas-title {
  font-size: var(--text-sm);
  font-weight: var(--weight-semibold);
  color: var(--color-text-primary);
}

.canvas-hint {
  font-size: 11px;
  color: var(--color-text-muted);
  margin-left: 8px;
}

.canvas-clock {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--color-text-muted);
  min-width: 70px;
  text-align: right;
}

/* ---- 视口区域 ---- */
.canvas-viewport {
  flex: 1;
  min-height: 0;
  position: relative;
  background:
    radial-gradient(ellipse 70% 55% at 18% 78%, rgba(59, 130, 246, 0.45) 0%, transparent 58%),
    radial-gradient(ellipse 60% 48% at 82% 18%, rgba(168, 85, 247, 0.38) 0%, transparent 55%),
    radial-gradient(ellipse 45% 38% at 50% 50%, rgba(34, 211, 238, 0.18) 0%, transparent 60%),
    linear-gradient(160deg, #1e293b 0%, #1a2744 38%, #0f172a 100%);
}

.canvas-layer-bands {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
}

.canvas-band {
  position: absolute;
  left: 0;
  right: 0;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  border-bottom: 1px solid rgba(0, 0, 0, 0.2);
  background: linear-gradient(90deg, rgba(255, 255, 255, 0.04) 0%, transparent 35%, transparent 65%, rgba(255, 255, 255, 0.03) 100%);
  pointer-events: auto;
  cursor: pointer;
}

.canvas-band.is-active {
  background: linear-gradient(90deg, color-mix(in srgb, var(--band-accent) 18%, transparent), transparent 40%);
}

.canvas-band-btn {
  position: absolute;
  right: 12px;
  top: 8px;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  background: rgba(15, 23, 42, 0.75);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  padding: 6px 10px;
  cursor: pointer;
  color: inherit;
}

.canvas-band-id {
  font-size: 11px;
  font-weight: 800;
  color: var(--band-accent);
}

.canvas-band-cn { font-size: 10px; color: rgba(255, 255, 255, 0.9); }
.canvas-band-en { font-size: 9px; color: rgba(255, 255, 255, 0.45); }

.canvas-col-head {
  position: absolute;
  top: 8px;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: rgba(255, 255, 255, 0.35);
  pointer-events: none;
  z-index: 1;
}

.canvas-col-rail { left: 72px; }
.canvas-col-spine { left: 520px; }

.canvas-layer-nav {
  position: absolute;
  left: 8px;
  top: 50%;
  transform: translateY(-50%);
  z-index: 6;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.layer-nav-btn {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  border: 2px solid var(--nav-accent, #64748b);
  background: rgba(15, 23, 42, 0.85);
  color: #fff;
  font-size: 10px;
  font-weight: 800;
  cursor: pointer;
}

.layer-nav-btn.active,
.layer-nav-btn:hover {
  background: color-mix(in srgb, var(--nav-accent) 35%, #0f172a);
}

.canvas-viewport :deep(.vue-flow) {
  background: transparent !important;
  z-index: 2;
}

.cv-node-label-en {
  display: block;
  font-size: 9px;
  font-weight: 500;
  color: #64748b;
  margin-top: 1px;
}

/* 主线 Main Spine */
.cv-node--spine {
  min-width: 260px;
  max-width: 320px;
  border-width: 2.5px;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.28);
}

.cv-node--spine .cv-node-label { font-size: 14px; font-weight: 700; }
.cv-node--spine .cv-node-value { font-size: 26px; }

/* 左侧辅线 Left Rail */
.cv-node--rail {
  min-width: 130px;
  max-width: 168px;
  border-style: dashed;
  opacity: 0.94;
}

.cv-node--rail .cv-node-label { font-size: 11px; }
.cv-node--rail .cv-node-sub,
.cv-node--rail .cv-node-cmd { font-size: 9px; }

.cv-node {
  background: #ffffff;
  border: 1px solid var(--color-border-default);
  border-radius: var(--radius-lg);
  min-width: 160px;
  max-width: 220px;
  box-shadow: var(--shadow-sm);
  cursor: pointer;
  position: relative;
  overflow: hidden;
  transition:
    transform var(--duration-normal) var(--ease-out),
    box-shadow var(--duration-normal) var(--ease-out),
    border-color var(--duration-normal) var(--ease-out);
}

/* legacy tier aliases → spine/rail */
.cv-node--primary {
  min-width: 260px;
  max-width: 320px;
  border-width: 2.5px;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.28);
}

.cv-node--nested {
  min-width: 130px;
  max-width: 168px;
  border-style: dashed;
  opacity: 0.94;
}

/* 辅助节点 */
.cv-node--secondary {
  min-width: 140px;
  max-width: 180px;
}

.cv-node:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
  border-color: var(--color-primary-300);
}

/* Alert 状态 */
.cv-node--alert {
  border-color: var(--color-danger);
  background: var(--color-danger-bg);
}

/* Pulse 动画 */
.cv-node--pulse {
  animation: cv-pulse var(--duration-pulse) infinite;
}

@keyframes cv-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.3); }
  50%      { box-shadow: 0 0 0 6px rgba(239, 68, 68, 0); }
}

/* ---- 圆环进度条 (Monitor 节点专用) ---- */
.cv-node-ring {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: conic-gradient(
    var(--color-primary-500) calc(var(--pct, 0) * 3.6deg),
    var(--color-neutral-100) calc(var(--pct, 0) * 3.6deg)
  );
  mask: radial-gradient(circle, transparent 55%, #000 58%);
  -webkit-mask: radial-gradient(circle, transparent 55%, #000 58%);
  opacity: 0.7;
}

/* ---- 节点内容区 ---- */
.cv-node-body {
  padding: var(--space-3);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.cv-node-body--trace-main {
  flex: 1;
}

.cv-node-label {
  font-size: var(--text-xs);
  font-weight: var(--weight-semibold);
  color: #0f172a;
}

/* 指标数值 — 使用 --text-metric (22px) */
.cv-node-value {
  font-family: var(--font-mono);
  font-size: var(--text-metric);
  font-weight: var(--weight-bold);
  color: #0f172a;
  line-height: var(--leading-tight);
}

.cv-node-value.is-danger {
  color: var(--color-danger);
}

/* 辅助说明文字 — 使用 --text-2xs (11px) 替代原来的 10px */
.cv-node-sub {
  font-size: var(--text-2xs);
  color: #64748b;
}

/* 进度条 */
.cv-node-bar {
  height: 3px;
  background: var(--color-border-subtle);
  margin: 0;
}

.cv-node-bar-fill {
  height: 100%;
  border-radius: 0 var(--radius-xs) 0 0;
  transition: width var(--duration-slow) var(--ease-out);
}

/* ============================================================
   节点变体
   ============================================================ */

/* ---- Skill 节点 ---- */
.cv-node--skill {
  display: flex;
  align-items: center;
  padding: 0;
}

.cv-node-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 48px;
  background: var(--color-primary-50);
  border-radius: var(--radius-md) 0 0 var(--radius-md);
  flex-shrink: 0;
  color: var(--color-primary-500);
}

/* Executor 专用的警告色调 icon */
.cv-node-icon--warn {
  background: rgba(245, 158, 11, 0.08);
  color: var(--color-warning);
}

.cv-node--skill .cv-node-body {
  padding: var(--space-2) var(--space-3);
}

/* ---- Snapshot 节点 ---- */
.cv-node--snapshot {
  display: flex;
  align-items: center;
  padding: var(--space-2) var(--space-3);
}

.cv-node-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  margin-right: var(--space-2);
}

.dot-green { background: var(--color-success); }
.dot-orange { background: var(--color-warning); }
.dot-gray { background: var(--color-border-strong); }

.cv-node--snapshot .cv-node-body {
  padding: 0;
  flex: 1;
}

/* ---- Trace 节点 ---- */
.cv-node--trace {
  display: flex;
  flex-direction: column;
  min-width: 180px;
}

.cv-node--trace .cv-node-body {
  padding: var(--space-2) var(--space-3);
}

.cv-node-trace-stages {
  display: flex;
  gap: var(--space-1);
  padding: 0 var(--space-3) var(--space-2);
}

.trace-stage-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

/* ---- Executor 节点 ---- */
.cv-node--executor {
  display: flex;
  align-items: center;
  padding: var(--space-2);
}

.cv-node-cmd {
  font-family: var(--font-mono);
  font-size: var(--text-2xs);
  color: var(--color-primary-500);
  background: var(--color-primary-50);
  padding: 1px var(--space-1);
  border-radius: var(--radius-xs);
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cv-node-status {
  font-size: var(--text-2xs);
  font-weight: var(--weight-semibold);
  padding: 2px var(--space-2);
  border-radius: var(--radius-sm);
}

.cv-node-status.is-success { color: var(--color-success); background: var(--color-success-bg); }
.cv-node-status.is-danger { color: var(--color-danger); background: var(--color-danger-bg); }

/* ============================================================
   Drawer 详情抽屉
   ============================================================ */

.drawer-section {
  margin-bottom: var(--space-4);
}

.drawer-section-title {
  font-size: var(--text-xs);
  font-weight: var(--weight-bold);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-text-muted);
  margin-bottom: var(--space-2);
  padding-bottom: var(--space-1);
  border-bottom: 1px solid var(--color-border-subtle);
}

.drawer-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-1) 0;
  font-size: var(--text-sm);
}

.drawer-row-label {
  color: var(--color-text-secondary);
  font-weight: var(--weight-medium);
}

.drawer-row-value {
  color: var(--color-text-primary);
}

.drawer-row-value.is-mono {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
}

.drawer-actions {
  margin-top: var(--space-4);
  padding-top: var(--space-4);
  border-top: 1px solid var(--color-border-subtle);
  display: flex;
  gap: var(--space-2);
}

/* ============================================================
   滚动条统一样式
   ============================================================ */

.canvas-viewport ::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
.canvas-viewport ::-webkit-scrollbar-track {
  background: transparent;
}
.canvas-viewport ::-webkit-scrollbar-thumb {
  background-color: var(--color-border-default);
  border-radius: 3px;
}
</style>
