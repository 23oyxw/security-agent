<template>
  <div class="canvas-shell">
    <div class="canvas-topbar">
      <div class="canvas-topbar-left">
        <el-button size="small" text @click="$router.push('/')"><el-icon><ArrowLeft /></el-icon> 返回</el-button>
        <el-divider direction="vertical" />
        <span class="canvas-title">A2 赛题架构 · 五层闭环</span>
        <el-tag v-if="liveConnected" size="small" type="success" effect="dark">● 实时</el-tag>
      </div>
      <div class="canvas-topbar-right">
        <el-button size="small" @click="fitView"><el-icon><FullScreen /></el-icon> 适应</el-button>
        <el-button size="small" @click="autoLayout" type="primary"><el-icon><Grid /></el-icon> 自动布局</el-button>
        <span class="canvas-clock">{{ now }}</span>
      </div>
    </div>

    <div class="canvas-viewport" ref="viewportRef">
      <VueFlow
        ref="vueFlowRef"
        v-model:nodes="nodes"
        v-model:edges="edges"
        :default-viewport="{ zoom: 0.55, x: 60, y: 30 }"
        :min-zoom="0.12" :max-zoom="4"
        :nodes-draggable="true" :nodes-connectable="false"
        fit-view-on-init
        @node-double-click="onNodeDblClick"
        @pane-click="selectedNode = null"
      >
        <Background :gap="30" :size="1" pattern-color="rgba(148,163,184,0.06)" />

        <!-- 节点模板 (与之前一致) -->
        <template #node-monitor="props">
          <div class="cv-node cv-node--monitor" :class="{ 'cv-node--alert': props.data.alert, 'cv-node--pulse': props.data.alert }">
            <div class="cv-node-ring" :style="{ '--pct': props.data.percent || 0 }"></div>
            <div class="cv-node-body">
              <span class="cv-node-label">{{ props.data.label }}</span>
              <span class="cv-node-value" :class="{ 'text-danger': props.data.alert }">{{ props.data.value }}</span>
              <span class="cv-node-sub">{{ props.data.sub }}</span>
            </div>
            <div class="cv-node-bar">
              <div class="cv-node-bar-fill" :style="{ width: (props.data.percent||0)+'%', background: props.data.alert?'#ef4444':'#10b981' }"></div>
            </div>
            <Handle type="source" :position="Position.Right" id="out" />
            <Handle type="target" :position="Position.Left" id="in" />
          </div>
        </template>

        <template #node-skill="props">
          <div class="cv-node cv-node--skill">
            <div class="cv-node-icon"><el-icon :size="16"><Connection /></el-icon></div>
            <div class="cv-node-body">
              <span class="cv-node-label">{{ props.data.label }}</span>
              <span class="cv-node-sub">{{ props.data.toolsLabel || (props.data.tools + ' 工具') }}</span>
            </div>
            <Handle type="source" :position="Position.Right" id="out" />
            <Handle type="target" :position="Position.Left" id="in" />
          </div>
        </template>

        <template #node-snapshot="props">
          <div class="cv-node cv-node--snapshot" :class="{ 'cv-node--alert': props.data.alert }">
            <div class="cv-node-dot" :class="props.data.restored?'dot-green':'dot-orange'"></div>
            <div class="cv-node-body">
              <span class="cv-node-label">{{ props.data.label }}</span>
              <span class="cv-node-sub">{{ props.data.time }}</span>
            </div>
            <el-tag v-if="props.data.restored" size="small" type="success">已回滚</el-tag>
            <el-tag v-else size="small" type="warning">{{ props.data.risk }}</el-tag>
            <Handle type="source" :position="Position.Right" id="out" />
            <Handle type="target" :position="Position.Left" id="in" />
          </div>
        </template>

        <template #node-trace="props">
          <div class="cv-node cv-node--trace" :class="{ 'cv-node--alert': !props.data.ok }">
            <div class="cv-node-body" style="flex:1"><span class="cv-node-label">{{ props.data.label }}</span><span class="cv-node-sub">{{ props.data.stages }}</span></div>
            <div class="cv-node-trace-stages">
              <span v-for="i in (props.data.stageCount||6)" :key="i" class="trace-stage-dot" :class="i<=(props.data.okStages||6)?'dot-green':'dot-gray'"></span>
            </div>
            <Handle type="target" :position="Position.Left" id="in" />
            <Handle type="source" :position="Position.Right" id="out" />
          </div>
        </template>

        <template #node-executor="props">
          <div class="cv-node cv-node--executor">
            <div class="cv-node-icon" style="background:#f59e0b15"><el-icon :size="14" color="#f59e0b"><CaretRight /></el-icon></div>
            <div class="cv-node-body">
              <span class="cv-node-label">{{ props.data.label }}</span>
              <code class="cv-node-cmd">{{ props.data.command }}</code>
            </div>
            <span class="cv-node-status" :class="props.data.status==='success'?'text-success':'text-danger'">{{ props.data.status }}</span>
            <Handle type="target" :position="Position.Left" id="in" />
            <Handle type="source" :position="Position.Right" id="out" />
          </div>
        </template>

        <Controls position="bottom-right" />
        <MiniMap position="bottom-left" :pannable="true" :zoomable="true" />
      </VueFlow>
    </div>

    <el-drawer v-model="drawerOpen" :title="drawerTitle" size="520px" direction="rtl">
      <template v-if="drawerData">
        <div class="drawer-section" v-for="(s,si) in drawerSections" :key="si">
          <div class="drawer-section-title">{{ s.title }}</div>
          <div class="drawer-row" v-for="r in s.rows" :key="r.label">
            <span class="drawer-row-label">{{ r.label }}</span>
            <span class="drawer-row-value" :class="{ mono: r.mono }">{{ r.value }}</span>
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
import { ElMessage } from 'element-plus'
import api from '../api'
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

let pollTimer = null, clockTimer = null

// ---- 五层架构 ----
const LX = 100; const LG = 260
const NODES = {
  intent: [
    { id:'intent-input', type:'executor', y:20,  data:{layer:'intent',label:'自然语言输入',command:'用户: "查看系统状态"',status:'entry'} },
    { id:'intent-audit', type:'snapshot', y:120, data:{layer:'intent',label:'意图审计',time:'IntentAuditor 偏离检测',risk:'安全',alert:false} },
    { id:'safety-gate',  type:'executor', y:220, data:{layer:'intent',label:'安全门禁',command:'L1静态30%+L2意图35%+L3环境35%',status:'active'} },
  ],
  perception: [
    { id:'cpu', type:'monitor', y:20,  data:{layer:'perception',label:'CPU',value:'—%',sub:'负载 —',percent:0,alert:false} },
    { id:'mem', type:'monitor', y:150, data:{layer:'perception',label:'内存',value:'—%',sub:'已用 —GB',percent:0,alert:false} },
    { id:'disk',type:'monitor', y:280, data:{layer:'perception',label:'磁盘',value:'—%',sub:'剩余 —GB',percent:0,alert:false} },
    { id:'net', type:'monitor', y:410, data:{layer:'perception',label:'网络连接',value:'—',sub:'TCP/UDP',percent:0,alert:false} },
    { id:'proc',type:'skill',   y:540, data:{layer:'perception',label:'进程/日志扫描',toolsLabel:'ps / journalctl / lsof'} },
  ],
  control: [
    { id:'sk-health',type:'skill',y:20, data:{layer:'control',label:'健康巡检',tools:6} },
    { id:'sk-net',   type:'skill',y:100,data:{layer:'control',label:'网络运维',tools:5} },
    { id:'sk-disk',  type:'skill',y:180,data:{layer:'control',label:'磁盘管理',tools:6} },
    { id:'sk-sec',   type:'skill',y:260,data:{layer:'control',label:'安全加固',tools:5} },
    { id:'sk-mcp',   type:'skill',y:340,data:{layer:'control',label:'MCP 热插拔注册',tools:17} },
  ],
  execution: [
    { id:'exec-cmd',type:'executor',y:20, data:{layer:'execution',label:'沙箱执行',command:'PrivilegeBroker 降权 + Sandbox',status:'ready'} },
    { id:'snap',    type:'snapshot', y:130,data:{layer:'execution',label:'快照备份',time:'操作前自动创建',risk:'—',alert:false} },
    { id:'rollback',type:'executor',y:240,data:{layer:'execution',label:'自动回滚',command:'exit≠0 → restore_snapshot',status:'standby'} },
  ],
  audit: [
    { id:'trace',    type:'trace', y:20, data:{layer:'audit',label:'事件脊柱 Trace',stages:'六阶段追踪',ok:true,stageCount:6,okStages:6} },
    { id:'jsonl',    type:'trace', y:200,data:{layer:'audit',label:'审计 JSONL',stages:'append-only 合规',ok:true,stageCount:6,okStages:6} },
    { id:'export-s', type:'snapshot',y:380,data:{layer:'audit',label:'纪要导出',time:'HTML / JSON / TXT',risk:'只读',alert:false} },
    { id:'feedback', type:'executor',y:500,data:{layer:'audit',label:'知识回流',command:'审计→规则库更新→闭环',status:'cycle'} },
  ],
}

const LAYERS = ['intent','perception','control','execution','audit']
const nodes = ref([])
const edges = ref([])

function buildNodes() {
  const out = []
  LAYERS.forEach((layer, li) => {
    (NODES[layer] || []).forEach(n => {
      out.push({ id:n.id, type:n.type, position:{x:LX+li*LG, y:n.y}, data:n.data })
    })
  })
  return out
}

function buildEdges() {
  return [
    // intent 内部
    { id:'e-in-audit',source:'intent-input',target:'intent-audit',type:'smoothstep',animated:true,style:{stroke:'#6366f1',strokeWidth:2},label:'解析意图' },
    { id:'e-audit-gate',source:'intent-audit',target:'safety-gate',type:'smoothstep',animated:true,style:{stroke:'#6366f1',strokeWidth:2},label:'安全校验' },
    // intent→perception
    { id:'e-gate-cpu',source:'safety-gate',target:'cpu',type:'smoothstep',animated:true,style:{stroke:'#3b82f6',strokeWidth:2.5},label:'触发感知' },
    { id:'e-gate-mem',source:'safety-gate',target:'mem',type:'smoothstep',animated:true,style:{stroke:'#3b82f6',strokeWidth:1.5,strokeDasharray:'4 2'} },
    { id:'e-gate-disk',source:'safety-gate',target:'disk',type:'smoothstep',animated:true,style:{stroke:'#3b82f6',strokeWidth:1.5,strokeDasharray:'4 2'} },
    { id:'e-gate-net',source:'safety-gate',target:'net',type:'smoothstep',animated:true,style:{stroke:'#3b82f6',strokeWidth:1.5,strokeDasharray:'4 2'} },
    { id:'e-gate-proc',source:'intent-audit',target:'proc',type:'smoothstep',animated:true,style:{stroke:'#3b82f6',strokeWidth:1.5,strokeDasharray:'4 2'} },
    // perception→control
    { id:'e-cpu-health',source:'cpu',target:'sk-health',type:'smoothstep',animated:true,style:{stroke:'#10b981',strokeWidth:2} },
    { id:'e-mem-health',source:'mem',target:'sk-health',type:'smoothstep',animated:true,style:{stroke:'#10b981',strokeWidth:1.5,strokeDasharray:'4 2'} },
    { id:'e-disk-sk',source:'disk',target:'sk-disk',type:'smoothstep',animated:true,style:{stroke:'#10b981',strokeWidth:1.5,strokeDasharray:'4 2'} },
    { id:'e-net-sk',source:'net',target:'sk-net',type:'smoothstep',animated:true,style:{stroke:'#10b981',strokeWidth:1.5,strokeDasharray:'4 2'} },
    { id:'e-proc-mcp',source:'proc',target:'sk-mcp',type:'smoothstep',animated:true,style:{stroke:'#10b981',strokeWidth:1.5,strokeDasharray:'4 2'} },
    // control→execution
    { id:'e-mcp-exec',source:'sk-mcp',target:'exec-cmd',type:'smoothstep',animated:true,style:{stroke:'#f59e0b',strokeWidth:2.5},label:'分发执行' },
    { id:'e-sec-exec',source:'sk-sec',target:'exec-cmd',type:'smoothstep',animated:true,style:{stroke:'#f59e0b',strokeWidth:2},label:'安全策略' },
    // execution 内部
    { id:'e-exec-snap',source:'exec-cmd',target:'snap',type:'smoothstep',animated:true,style:{stroke:'#ef4444',strokeWidth:2},label:'执行前备份' },
    { id:'e-snap-roll',source:'snap',target:'rollback',type:'smoothstep',style:{stroke:'#ef4444',strokeWidth:1.5,strokeDasharray:'4 2'},label:'失败→恢复' },
    // execution→audit
    { id:'e-exec-trace',source:'exec-cmd',target:'trace',type:'smoothstep',animated:true,style:{stroke:'#8b5cf6',strokeWidth:2.5} },
    { id:'e-snap-jsonl',source:'snap',target:'jsonl',type:'smoothstep',style:{stroke:'#8b5cf6',strokeWidth:1.5,strokeDasharray:'4 2'} },
    // audit 内部
    { id:'e-trace-export',source:'trace',target:'export-s',type:'smoothstep',animated:true,style:{stroke:'#8b5cf6',strokeWidth:1.5} },
    { id:'e-export-fb',source:'export-s',target:'feedback',type:'smoothstep',animated:true,style:{stroke:'#8b5cf6',strokeWidth:1.5} },
    // audit→intent (闭环)
    { id:'e-fb-intent',source:'feedback',target:'intent-input',type:'smoothstep',animated:true,style:{stroke:'#8b5cf6',strokeWidth:1.5,strokeDasharray:'8 4'},label:'知识回流·闭环' },
  ]
}

function autoLayout() {
  nodes.value = buildNodes()
  edges.value = buildEdges()
  nextTick(() => { if (vueFlowRef.value) vueFlowRef.value.fitView({padding:0.3}) })
}

function fitView() { if (vueFlowRef.value) vueFlowRef.value.fitView({padding:0.2}) }

// ---- 实时数据 ----
async function fetchLiveData() {
  try {
    const [flow, mcp] = await Promise.all([
      api.get('/workflow/flow-status').catch(()=>null),
      api.get('/mcp/servers').catch(()=>[]),
    ])
    if (!flow?.layers) { liveConnected.value = false; return }
    liveConnected.value = true
    const c = flow.layers.collection
    if (c?.nodes) {
      const m = {}; c.nodes.forEach(n => m[n.id] = n)
      ;['cpu','mem','disk','net'].forEach(id => {
        const nd = nodes.value.find(n=>n.id===id)
        const src = m[id]
        if (nd && src) nd.data = {...nd.data,value:src.value,sub:src.subtitle,percent:parseFloat(src.value)||0,alert:src.alert}
      })
    }
    if (Array.isArray(mcp)) {
      const names = ['sk-health','sk-net','sk-disk','sk-sec','sk-mcp']
      mcp.slice(0,5).forEach((s,i) => {
        const nd = nodes.value.find(n=>n.id===names[i])
        if (nd) nd.data = {...nd.data,label:s.display_name||s.name,tools:s.tools_count||s.tool_count||0}
      })
    }
  } catch { liveConnected.value = false }
}

function updateClock() { now.value = new Date().toLocaleTimeString('zh-CN',{hour12:false}) }

function onNodeDblClick({node}) { /* drawDetail(node) */ }

onMounted(() => {
  autoLayout()
  updateClock()
  clockTimer = setInterval(updateClock,1000)
  fetchLiveData()
  pollTimer = setInterval(fetchLiveData,3000)
})
onUnmounted(() => { clearInterval(pollTimer); clearInterval(clockTimer) })
</script>

<style scoped>
.canvas-shell { height: calc(100vh - var(--topbar-height, 56px)); display: flex; flex-direction: column; background: #f8fafc; }
.canvas-topbar { display:flex; justify-content:space-between; align-items:center; padding:0 var(--space-4); height:44px; background:#fff; border-bottom:1px solid var(--color-neutral-200); flex-shrink:0; z-index:10; }
.canvas-topbar-left,.canvas-topbar-right { display:flex; align-items:center; gap:var(--space-2); }
.canvas-title { font-size:var(--text-sm); font-weight:600; color:var(--color-neutral-700); }
.canvas-clock { font-family:var(--font-mono); font-size:var(--text-xs); color:var(--color-neutral-400); min-width:70px; text-align:right; }
.canvas-viewport { flex:1; min-height:0; position:relative; }

.cv-node { background:#fff; border:2px solid var(--color-neutral-200); border-radius:var(--radius-lg); min-width:160px; max-width:220px; box-shadow:var(--shadow-sm); cursor:pointer; transition:all .2s; position:relative; overflow:hidden; }
.cv-node:hover { border-color:var(--color-primary-300); box-shadow:var(--shadow-md); transform:scale(1.03); }
.cv-node--alert { border-color:var(--color-danger-300); background:#fef2f2; }
.cv-node--pulse { animation:cv-pulse 2s infinite; }
@keyframes cv-pulse { 0%,100%{box-shadow:0 0 0 0 rgba(239,68,68,.3)} 50%{box-shadow:0 0 0 6px rgba(239,68,68,0)} }
.cv-node-ring { position:absolute; top:6px; right:6px; width:38px; height:38px; border-radius:50%; background:conic-gradient(var(--color-primary-500) calc(var(--pct,0)*3.6deg),var(--color-neutral-100) calc(var(--pct,0)*3.6deg)); mask:radial-gradient(circle,transparent 55%,#000 58%); -webkit-mask:radial-gradient(circle,transparent 55%,#000 58%); opacity:.7; }
.cv-node-body { padding:var(--space-3); display:flex; flex-direction:column; gap:2px; }
.cv-node-label { font-size:var(--text-xs); font-weight:600; color:var(--color-neutral-700); }
.cv-node-value { font-family:var(--font-mono); font-size:20px; font-weight:700; color:var(--color-neutral-800); line-height:1.2; }
.text-danger{color:var(--color-danger-600)} .text-success{color:#10b981}
.cv-node-sub { font-size:10px; color:var(--color-neutral-400); }
.cv-node-bar { height:3px; background:var(--color-neutral-100); margin:0; }
.cv-node-bar-fill { height:100%; border-radius:0 2px 0 0; transition:width .6s; }
.cv-node--skill { display:flex; align-items:center; padding:0; }
.cv-node-icon { display:flex; align-items:center; justify-content:center; width:40px; height:48px; background:var(--color-primary-50); border-radius:var(--radius-md) 0 0 var(--radius-md); flex-shrink:0; color:var(--color-primary-500); }
.cv-node--skill .cv-node-body { padding:var(--space-2) var(--space-3); }
.cv-node--snapshot { display:flex; align-items:center; padding:var(--space-2) var(--space-3); }
.cv-node-dot { width:8px; height:8px; border-radius:50%; flex-shrink:0; margin-right:var(--space-2); }
.dot-green{background:#10b981} .dot-orange{background:#f59e0b} .dot-gray{background:#d1d5db}
.cv-node--snapshot .cv-node-body { padding:0; flex:1; }
.cv-node--trace { display:flex; flex-direction:column; min-width:180px; }
.cv-node--trace .cv-node-body { padding:var(--space-2) var(--space-3); }
.cv-node-trace-stages { display:flex; gap:3px; padding:0 var(--space-3) var(--space-2); }
.trace-stage-dot { width:6px; height:6px; border-radius:50%; }
.cv-node--executor { display:flex; align-items:center; padding:var(--space-2); }
.cv-node-cmd { font-family:var(--font-mono); font-size:10px; color:var(--color-primary-500); background:var(--color-primary-50); padding:1px 4px; border-radius:2px; max-width:150px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.cv-node-status { font-size:10px; font-weight:600; padding:2px 6px; border-radius:var(--radius-sm); }
.drawer-section { margin-bottom:var(--space-4); }
.drawer-section-title { font-size:var(--text-xs); font-weight:700; text-transform:uppercase; letter-spacing:.05em; color:var(--color-neutral-400); margin-bottom:var(--space-2); padding-bottom:var(--space-1); border-bottom:1px solid var(--color-neutral-100); }
.drawer-row { display:flex; justify-content:space-between; align-items:center; padding:var(--space-1) 0; font-size:var(--text-sm); }
.drawer-row-label { color:var(--color-neutral-500); font-weight:500; }
.drawer-row-value { color:var(--color-neutral-800); }
.drawer-row-value.mono { font-family:var(--font-mono); font-size:var(--text-xs); }
.drawer-actions { margin-top:var(--space-4); padding-top:var(--space-4); border-top:1px solid var(--color-neutral-100); display:flex; gap:var(--space-2); }
</style>
