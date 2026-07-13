<template>
  <div class="guide-page page-theme-learn">
    <div class="page-header">
      <h1 class="page-title">架构导引 · 技术说明</h1>
      <p class="page-subtitle">
        {{ PIPELINE_FORMULA }} · 五层刚性流程 · 三 Agent 协同 · 先分析后防护再执行终审计迭代
      </p>
    </div>

    <!-- 三 Agent -->
    <el-card class="section-card" shadow="never">
      <template #header><h3>三 Agent 体系（终版固定）</h3></template>
      <div class="agent-row">
        <div v-for="a in agents" :key="a.id" class="agent-card" :style="{ '--c': a.color }">
          <strong>{{ a.label }}</strong>
          <span class="agent-bracket">{{ a.bracket }}</span>
          <p>{{ a.desc }}</p>
        </div>
      </div>
    </el-card>

    <!-- 定义封装栈 -->
    <el-card class="section-card" shadow="never">
      <template #header><h3>定义封装 → 五层 → 数学模型</h3></template>
      <el-row :gutter="16">
        <el-col :span="8" v-for="block in encapsulationStack" :key="block.id">
          <div class="l5-block">
            <h4>{{ block.title }}</h4>
            <p>{{ block.desc }}</p>
            <ul class="encap-list">
              <li v-for="(item, i) in block.items" :key="i">{{ item }}</li>
            </ul>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 五层流程 -->
    <el-card class="section-card" shadow="never">
      <template #header><h3>五层刚性流水线</h3></template>
      <div class="layer-flow">
        <div v-for="(l, i) in layers" :key="l.id" class="layer-block">
          <div class="layer-badge" :style="{ borderColor: l.accent }">{{ l.id }}</div>
          <strong>{{ l.name }}</strong>
          <span>{{ l.agent }}</span>
          <p>{{ l.summary }}</p>
          <el-button v-if="l.route" text type="primary" size="small" @click="$router.push(l.route)">
            打开 →
          </el-button>
          <div v-if="i === 1" class="gate-chip">层间门禁 · plan + L2 → execute</div>
        </div>
      </div>
      <p class="flow-note">
        L3 切换执行模式后，若 L2 已通过将<strong>自动跑完 L3→L4→L5</strong>并进入
        <el-button text type="primary" size="small" @click="$router.push('/l5')">/l5 链路分析</el-button>
      </p>
    </el-card>

    <!-- L5 链路方案 -->
    <el-card class="section-card" shadow="never">
      <template #header><h3>L5 链路追踪可视化（精简精确版）</h3></template>
      <el-row :gutter="16">
        <el-col :span="8">
          <div class="l5-block">
            <h4>散点图 · 单点/偶发</h4>
            <p>每条 trace 为散点（耗时×错误率×抖动）；<strong>3σ + IQR</strong> 标红离群；绑定 path/trace ID。</p>
            <el-tag size="small">Python statistics</el-tag>
            <el-tag size="small" type="success">ECharts scatter</el-tag>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="l5-block">
            <h4>热力图 · 批量/时段</h4>
            <p>时间×服务接口二维矩阵；加权密度风险；识别成片、集群级故障区。</p>
            <el-tag size="small">weighted_density</el-tag>
            <el-tag size="small" type="success">ECharts heatmap</el-tag>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="l5-block">
            <h4>溯源闭环 + 集成测试</h4>
            <p>异常点 → Trace/Span → 网关→服务→中间件→DB 拆解 → 根因输出；模块链路集成测试矩阵。</p>
            <el-button type="primary" size="small" @click="$router.push('/l5')">进入 L5 页面</el-button>
          </div>
        </el-col>
      </el-row>
      <blockquote class="core-quote">
        运维智能体依托统计模型识别链路异常，通过散点图定位单点偶发故障、热力图锁定批量区域故障，联动链路追踪拆解调用栈，精准定位故障位置、自动追溯链路根源。
      </blockquote>
    </el-card>

    <!-- 快速入门 -->
    <el-card class="section-card" shadow="never">
      <template #header><h3>快速入门</h3></template>
      <el-row :gutter="16">
        <el-col :span="6" v-for="item in quickStart" :key="item.step">
          <div class="quick-card">
            <div class="quick-step">{{ item.step }}</div>
            <div class="quick-title">{{ item.title }}</div>
            <div class="quick-desc">{{ item.desc }}</div>
            <el-button text type="primary" size="small" @click="$router.push(item.link)">{{ item.action }}</el-button>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 文档链接 -->
    <el-card class="section-card" shadow="never">
      <template #header><h3>权威文档</h3></template>
      <ul class="doc-list">
        <li><code>docs/architecture/ENCAPSULATION_TO_L5_ROADMAP.md</code> — 定义封装到 L5 落地路线</li>
        <li><code>docs/architecture/FINAL_ARCHITECTURE.md</code> — 终版唯一权威</li>
        <li><code>docs/architecture/FIVE_LAYER_PIPELINE.md</code> — 五层流程细节</li>
        <li><code>docs/architecture/L5_ANALYTICS.md</code> — L5 散点/热力/集成测试</li>
        <li><code>docs/architecture/FRONTEND_SIDEBAR.md</code> — 侧栏与页面映射</li>
      </ul>
    </el-card>
  </div>
</template>

<script setup>
import { PIPELINE_FORMULA, ENCAPSULATION_STACK } from '../constants/pipeline-architecture'
import { AGENT_VISUAL } from '../constants/agent-visual'

const encapsulationStack = ENCAPSULATION_STACK

const agents = Object.values(AGENT_VISUAL).map(a => ({
  id: a.id,
  label: a.shortLabel,
  bracket: a.bracket,
  color: a.color,
  desc: a.layers?.join(' · ') || '',
}))

const layers = [
  { id: 'L1', name: '分析计划', agent: 'core_dispatch · analyze', accent: '#3b82f6', summary: '三感知并行 · 零工具零执行', route: '/agent' },
  { id: 'L2', name: '安全防护', agent: 'safety_sandbox', accent: '#10b981', summary: '唯一闸门 pass/confirm/deny', route: '/safety' },
  { id: 'L3', name: '推理执行', agent: 'core_dispatch · execute', accent: '#f59e0b', summary: 'MCP 四工具簇 · 需 L2 解锁', route: '/agent' },
  { id: 'L4', name: 'Trace 卷宗', agent: 'audit_iteration · 追溯', accent: '#8b5cf6', summary: 'append-only 卷宗 · Wiki 回流', route: '/trace' },
  { id: 'L5', name: '链路量化分析', agent: 'audit_iteration · 分析', accent: '#0ea5e9', summary: '散点/热力/溯源 · 集成测试', route: '/l5' },
]

const quickStart = [
  { step: '1', title: '登录', desc: 'admin / admin123 · 开发用 npm run dev:mock', action: '登录页', link: '/login' },
  { step: '2', title: 'L1 计划对话', desc: '输入运维指令，完成三感知分析与 L2 预检', action: '对话 →', link: '/agent' },
  { step: '3', title: 'L3 执行到底', desc: '侧栏切换执行模式，自动 L3→L4→L5', action: 'L5 分析 →', link: '/l5' },
  { step: '4', title: '五层画布', desc: '三 Agent 拓扑 · 单击详情 · 双击跳转', action: '画布 →', link: '/canvas' },
]
</script>

<style scoped>
.guide-page { max-width: var(--content-max-width, 1200px); margin: 0 auto; padding-bottom: 24px; }
.page-header { margin-bottom: 16px; }
.page-title { font-size: var(--text-2xl); font-weight: 700; margin: 0; color: var(--color-text-primary); }
.page-subtitle { font-size: var(--text-sm); color: var(--color-text-secondary); margin: 4px 0 0; }
.section-card {
  margin-bottom: 16px;
  border: 1px solid var(--color-border-default);
  border-radius: var(--radius-lg);
  background: rgba(15, 23, 42, 0.35);
}
.section-card h3 { margin: 0; font-size: var(--text-base); }

.agent-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.agent-card {
  padding: 14px; border-radius: var(--radius-md);
  border-left: 4px solid var(--c);
  background: rgba(255, 255, 255, 0.04);
  font-size: 13px;
}
.agent-card strong { display: block; margin-bottom: 4px; }
.agent-bracket { font-size: var(--text-sm); color: var(--color-text-muted); }
.agent-card p { margin: 8px 0 0; color: var(--color-text-secondary); font-size: var(--text-sm); }

.layer-flow { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; }
.layer-block {
  padding: 12px; border-radius: var(--radius-md);
  border: 1px solid var(--color-border-default);
  background: rgba(255, 255, 255, 0.03);
  font-size: var(--text-sm); position: relative;
}
.layer-badge {
  display: inline-block; padding: 2px 8px; border: 2px solid;
  border-radius: 4px; font-weight: 700; margin-bottom: 6px;
}
.layer-block strong { display: block; font-size: 13px; }
.layer-block span { color: var(--color-text-muted); font-size: var(--text-sm); }
.layer-block p { margin: 6px 0; color: var(--color-text-secondary); line-height: 1.5; }
.gate-chip {
  margin-top: 8px; padding: 4px 8px; font-size: var(--text-xs);
  border: 1px dashed #f59e0b; border-radius: 4px; color: #f59e0b;
}
.flow-note { margin: 12px 0 0; font-size: 13px; color: var(--color-text-secondary); }

.l5-block { padding: 12px; border-radius: var(--radius-md); background: rgba(14, 165, 233, 0.08); height: 100%; }
.l5-block h4 { margin: 0 0 8px; font-size: 14px; }
.l5-block p { font-size: var(--text-sm); line-height: 1.6; color: var(--color-text-secondary); margin: 0 0 8px; }
.encap-list { margin: 0; padding-left: 18px; font-size: var(--text-sm); color: var(--color-text-secondary); }
.encap-list li { margin-bottom: 4px; }
.l5-block .el-tag { margin-right: 4px; }

.core-quote {
  margin: 16px 0 0; padding: 12px 16px;
  border-left: 4px solid #0ea5e9;
  background: rgba(14, 165, 233, 0.06);
  font-size: 13px; line-height: 1.6; color: var(--color-text-secondary);
}

.quick-card {
  border: 1px solid var(--color-border-default); border-radius: var(--radius-md);
  padding: 16px; text-align: center; height: 100%;
}
.quick-step {
  display: inline-flex; width: 32px; height: 32px; align-items: center; justify-content: center;
  border-radius: 50%; background: var(--color-primary-500); color: #fff; font-weight: 700; margin-bottom: 8px;
}
.quick-title { font-size: 14px; font-weight: 600; margin-bottom: 4px; }
.quick-desc { font-size: var(--text-sm); color: var(--color-text-muted); margin-bottom: 8px; min-height: 48px; }

.doc-list { margin: 0; padding-left: 20px; font-size: 13px; line-height: 1.8; color: var(--color-text-secondary); }

@media (max-width: 960px) {
  .agent-row, .layer-flow { grid-template-columns: 1fr; }
}
</style>
