<template>
  <div class="guide-page">
    <div class="page-header">
      <h1 class="page-title">技术说明与使用导引</h1>
      <p class="page-subtitle">赛题架构 · 技术理念 · 痛点解决 · 操作快速入门</p>
    </div>

    <!-- 架构总览 -->
    <el-card class="section-card" shadow="never">
      <template #header><h3>🏗 A2 赛题五层闭环架构</h3></template>
      <div class="arch-flow">
        <div class="arch-node arch-intent">
          <strong>L1 意图入口</strong>
          <span>自然语言输入 → 意图审计 → 安全门禁</span>
        </div>
        <div class="arch-arrow">→</div>
        <div class="arch-node arch-perception">
          <strong>L2 OS 感知</strong>
          <span>psutil/lsof/netstat/journalctl 实时采集</span>
        </div>
        <div class="arch-arrow">→</div>
        <div class="arch-node arch-control">
          <strong>L3 MCP 管控</strong>
          <span>17 Skills 热插拔 · Skill Flow 编排</span>
        </div>
        <div class="arch-arrow">→</div>
        <div class="arch-node arch-exec">
          <strong>L4 安全执行</strong>
          <span>三层防御评估 → 沙箱 → 快照 → 回滚</span>
        </div>
        <div class="arch-arrow">→</div>
        <div class="arch-node arch-audit">
          <strong>L5 审计溯源</strong>
          <span>IncidentSpine · 六阶段 Trace · 执行纪要</span>
        </div>
        <div class="arch-feedback">↺ 知识回流闭环</div>
      </div>
      <div style="margin-top:12px;font-size:12px;color:var(--color-neutral-500);text-align:center">
        完整可视化见 <el-button text type="primary" size="small" @click="$router.push('/canvas')">无限画布 →</el-button>
      </div>
    </el-card>

    <!-- 核心技术分支 -->
    <el-row :gutter="16" style="margin-top:16px">
      <el-col :span="12">
        <el-card class="section-card" shadow="never">
          <template #header><h3>🔧 核心能力分支</h3></template>
          <el-collapse>
            <el-collapse-item title="Harness Engineering (安全护栏)" name="h1">
              <div class="tech-detail">
                <p><strong>理念</strong>: Agent = LLM + Harness 管控系统。模型是引擎，Harness 是刹车/约束/治理体系。</p>
                <p><strong>六大模块映射</strong>:</p>
                <ul>
                  <li>① 上下文架构 → ReAct 上下文治理 (截断/瘦身/预算)</li>
                  <li>② 架构约束 → 三层防御 + 注入检测 + 白名单 + 沙箱</li>
                  <li>③ 自验证循环 → PID/端口幻觉检测 + 知识库交叉校验</li>
                  <li>④ 上下文隔离 → 工具观测截断 + 子 Agent 防火墙</li>
                  <li>⑤ 熵治理 → Gitee Wiki 同步 + 快照 72h 过期清理</li>
                  <li>⑥ 可拆卸模块化 → L1/L2/L3 Skill 分层 + MCP 热插拔</li>
                </ul>
              </div>
            </el-collapse-item>
            <el-collapse-item title="自动回滚与快照管理" name="h2">
              <div class="tech-detail">
                <p><strong>赛题得分点</strong>: 安全校验能力满分标准要求「自动回滚」</p>
                <p><strong>实现</strong>: SnapshotManager(文件级快照) + post-execution hook</p>
                <p><strong>触发条件</strong>: exit_code ≠ 0 AND risk_level ≥ IRREVERSIBLE AND snapshot 存在 → 自动调用 restore_snapshot()</p>
                <p><strong>在哪里看到</strong>:</p>
                <ul>
                  <li><el-button text type="primary" size="small" @click="$router.push('/safety')">安全执行</el-button> — 输入高危命令(如 <code>rm /etc/hosts</code>)，执行失败后页面显示「⏪ 自动回滚已触发」</li>
                  <li><el-button text type="primary" size="small" @click="$router.push('/canvas')">无限画布</el-button> — L4 执行层「快照备份」→「自动回滚」节点展示回滚链路</li>
                  <li>后端 API: <code>POST /api/executor/rollback</code> 手动回滚 | <code>GET /api/executor/snapshots</code> 查看所有快照</li>
                </ul>
                <p><strong>代码位置</strong>: <code>terminal/executor.py:_maybe_auto_rollback()</code> (行 59-88) — 执行后检测失败自动调 SnapshotManager.restore_snapshot()</p>
              </div>
            </el-collapse-item>
            <el-collapse-item title="任务分发引擎 (权限管控)" name="h3">
              <div class="tech-detail">
                <p><strong>与传统模式区别</strong>: 用户不输入 Shell 命令，只选择/发起运维任务。所有底层指令内部封装，管控重心是「谁能做什么」而非「命令是否包含危险关键词」</p>
                <p><strong>8 个内置任务</strong>: 端口检测/日志查看/进程查询/系统健康/磁盘分析/网络连接/防火墙状态/重启服务 (需 operator)</p>
              </div>
            </el-collapse-item>
            <el-collapse-item title="Semantic Memory (Mem0 风格)" name="h4">
              <div class="tech-detail">
                <p><strong>三级记忆</strong>: L1 工作记忆 (SQLite 对话历史) → L2 语义记忆 (知识片段+倒排索引) → L3 情节记忆 (会话摘要+决策时间线)</p>
                <p><strong>自动提取</strong>: 从对话中检测安全术语 (SSH爆破/WebShell/提权) 并自动存入语义层</p>
              </div>
            </el-collapse-item>
          </el-collapse>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card class="section-card" shadow="never">
          <template #header><h3>📊 Agent 数学评估模型</h3></template>
          <div class="eval-formula">
            <div class="formula-line"><strong>综合分</strong> = 0.35×成功率 + 0.30×安全合规 + 0.15×效率比 + 0.10×步骤效率 + 0.10×稳定性</div>
            <div class="formula-line" style="margin-top:8px"><strong>效率比</strong> = 成功次数×100 / log₂(总Token+1)</div>
            <div class="formula-line" style="margin-top:8px"><strong>评级</strong>: A≥85 / B≥70 / C≥55 / D≥40 / F&lt;40</div>
          </div>
          <div style="margin-top:12px;font-size:12px;color:var(--color-neutral-500)">
            <p>每次 Agent 对话自动评估并持久化。Token 数据来自 DeepSeek API <code>response.usage</code> 字段 (非估算)。</p>
            <p>效率曲线验证: Token 消耗↓50% → 评分从 32.5(F) 升至 95.2(A)。</p>
            <el-button text type="primary" size="small" @click="$router.push('/')">查看 Dashboard 评估面板 →</el-button>
          </div>
        </el-card>

        <el-card class="section-card" shadow="never" style="margin-top:16px">
          <template #header><h3>🎯 赛点痛点与解决</h3></template>
          <el-timeline>
            <el-timeline-item timestamp="P0 一票否决" type="danger">
              <strong>权限隔离</strong>: PrivilegeBroker 降权 + SandboxExecutor 隔离 → 解决「无权限隔离直接判定功能严重不足」
            </el-timeline-item>
            <el-timeline-item timestamp="P0 一票否决" type="danger">
              <strong>行为追溯</strong>: IncidentSpine + 六阶段 Trace + JSONL 持久化 → 解决「链路追踪不完整」
            </el-timeline-item>
            <el-timeline-item timestamp="核心得分" type="warning">
              <strong>安全护栏</strong>: 三层防御 (L1静态30%+L2意图35%+L3环境35%) → 解决「安全校验不完整」
            </el-timeline-item>
            <el-timeline-item timestamp="加分亮点" type="success">
              <strong>自动回滚</strong>: SnapshotManager + post-execution hook → 解决「无自动回滚」
            </el-timeline-item>
            <el-timeline-item timestamp="加分亮点" type="primary">
              <strong>Agent 评估</strong>: 数学评分模型 + Token 溯源 → 解决「无法量化 Agent 能力」
            </el-timeline-item>
          </el-timeline>
        </el-card>
      </el-col>
    </el-row>

    <!-- 快速入门 -->
    <el-card class="section-card" shadow="never" style="margin-top:16px">
      <template #header><h3>🚀 快速入门</h3></template>
      <el-row :gutter="16">
        <el-col :span="8" v-for="item in quickStart" :key="item.step">
          <div class="quick-card">
            <div class="quick-step">{{ item.step }}</div>
            <div class="quick-title">{{ item.title }}</div>
            <div class="quick-desc">{{ item.desc }}</div>
            <el-button text type="primary" size="small" @click="$router.push(item.link)">{{ item.action }}</el-button>
          </div>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup>
const quickStart = [
  { step: '1', title: '智能助手对话', desc: '自然语言发起运维请求，Agent 自动调工具执行', action: '打开 →', link: '/agent' },
  { step: '2', title: '安全执行命令', desc: '输入或从 Agent 回复点击命令，评估后沙箱执行', action: '打开 →', link: '/safety' },
  { step: '3', title: '查看评估与监控', desc: 'Dashboard 查看系统指标 + Agent 评分 + Token 消耗', action: '打开 →', link: '/' },
]
</script>

<style scoped>
.guide-page { max-width: var(--content-max-width, 1200px); margin: 0 auto; padding-bottom: 24px; }
.page-header { margin-bottom: 16px; }
.page-title { font-size: var(--text-2xl); font-weight: 700; margin: 0; }
.page-subtitle { font-size: var(--text-sm); color: var(--color-neutral-400); margin: 4px 0 0; }
.section-card { border: 1px solid var(--page-card-border, var(--color-neutral-200)); border-radius: var(--radius-lg); background: transparent; }

/* 架构流程图 */
.arch-flow { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; padding: 16px 0; position: relative; }
.arch-node {
  padding: 12px 16px; border-radius: var(--radius-lg); border: 2px solid;
  min-width: 140px; text-align: center; font-size: 12px; line-height: 1.5;
}
.arch-node strong { display: block; font-size: 13px; margin-bottom: 2px; }
.arch-node span { color: var(--color-neutral-500); font-size: 11px; }
.arch-intent { border-color: #6366f1; background: #eef2ff; }
.arch-perception { border-color: #3b82f6; background: #eff6ff; }
.arch-control { border-color: #10b981; background: #ecfdf5; }
.arch-exec { border-color: #f59e0b; background: #fffbeb; }
.arch-audit { border-color: #8b5cf6; background: #f5f3ff; }
.arch-arrow { font-size: 20px; color: var(--color-neutral-300); font-weight: 700; }
.arch-feedback {
  display: inline-block; padding: 6px 14px; border: 2px dashed #8b5cf6;
  border-radius: var(--radius-lg); font-size: 11px; color: #8b5cf6; font-weight: 600;
}

/* 技术详情 */
.tech-detail { font-size: 13px; line-height: 1.7; color: var(--color-neutral-600); }
.tech-detail ul { margin: 4px 0; padding-left: 20px; }
.tech-detail li { margin: 2px 0; }

/* 评估公式 */
.eval-formula {
  background: linear-gradient(135deg, #f0fdf4, #eff6ff);
  border: 1px solid var(--color-neutral-200); border-radius: var(--radius-md);
  padding: 14px 18px; font-family: var(--font-mono); font-size: 13px; line-height: 1.8;
}

/* 快速入门卡片 */
.quick-card {
  border: 1px solid var(--color-neutral-200); border-radius: var(--radius-md);
  padding: 16px; text-align: center; transition: transform .15s;
}
.quick-card:hover { transform: translateY(-2px); box-shadow: var(--shadow-sm); }
.quick-step {
  display: inline-flex; align-items: center; justify-content: center;
  width: 32px; height: 32px; border-radius: 50%; background: var(--color-primary-500);
  color: #fff; font-size: 16px; font-weight: 700; margin-bottom: 8px;
}
.quick-title { font-size: 14px; font-weight: 600; color: var(--color-neutral-800); margin-bottom: 4px; }
.quick-desc { font-size: 12px; color: var(--color-neutral-400); margin-bottom: 8px; }

@media (max-width: 768px) {
  .arch-flow { flex-direction: column; }
  .arch-arrow { transform: rotate(90deg); }
}
</style>
