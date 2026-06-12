# L5 链路追踪可视化 · 统计迭代

> **版本**：v1.0 · **更新**：2026-06-11  
> **前端页面**：`/l5` · **后端**：`security_agent/l5/` · `GET/POST /api/l5/*`  
> **权威上位**：[FINAL_ARCHITECTURE.md](./FINAL_ARCHITECTURE.md) §2.3 · §三 L5

---

## 1. 核心一句话（答辩/报告）

运维智能体依托统计模型识别链路异常，通过散点图定位单点偶发故障、热力图锁定批量区域故障，联动链路追踪拆解调用栈，精准定位故障位置、自动追溯链路根源。

---

## 2. 三能力矩阵

| 能力 | 数据 | 数学模型 | 开源工具 | 智能体行为 |
|------|------|----------|----------|------------|
| **散点图** | 每条 trace：耗时、错误率、延迟抖动 | **3σ** + **IQR** 离群 | Python `statistics` · ECharts scatter | 离群红点 → 绑定 path/trace ID |
| **热力图** | 时间桶 × 服务接口 | 加权密度风险 | ECharts heatmap | 深色连片区 → 批量聚合异常 |
| **溯源闭环** | Trace stages / Span | 最慢节点 + 报错节点优先 | `build_root_cause()` | 网关→服务→中间件→DB 拆解 |

---

## 3. 溯源闭环五步

1. 可视化异常点位/区域（散点 + 热力）
2. 自动提取 Trace/Span 标识
3. 逐级拆解调用链（瀑布图）
4. 对比正常基线，锁定最慢/报错/中断节点
5. 输出根因：慢 SQL、连接池耗尽、依赖故障、网络抖动、代码异常

---

## 4. L5 六维量化 + 各层对照

见 `frontend/src/constants/l5-metrics.js`：

- 意图准确率 · 边界召回 · 修复成功率 · 调度利用率 · 批量合规率 · 工具命中率
- 各层数据共享对照表（L1–L5 → L5 指标馈入）

数据来源：`GET /api/eval/score` 的 `dimension_scores`。

---

## 5. 集成测试（模块链路）

**方法**：分层集成测试 + 层间链路矩阵（参考 pytest integration / GitHub Actions matrix）。

| ID | 名称 | 层 |
|----|------|-----|
| `l1_plan` | L1 计划感知 | L1 |
| `l2_precheck` | L2 安全预检 | L2 |
| `link_l1_l2` | 链路 L1→L2 | L1-L2 |
| `l3_execute` | L3 执行分发 | L3 |
| `l4_audit` | L4 审计卷宗 | L4 |
| `link_l2_l3` | 链路 L2→L3→L4 | L2-L4 |
| `l5_metrics` | L5 指标模型 | L5 |

- `GET /api/l5/integration/catalog` — 测试目录  
- `POST /api/l5/integration/run` — 运行（可选 `test_ids`）

实现：`security_agent/l5/integration_tests.py`

---

## 6. API 一览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/l5/scatter` | 散点 + 3σ/IQR 离群 |
| GET | `/api/l5/heatmap` | 时间×服务热力矩阵 |
| GET | `/api/l5/root-cause/{trace_id}` | Span 拆解 + 根因 |
| GET | `/api/l5/integration/catalog` | 集成测试目录 |
| POST | `/api/l5/integration/run` | 运行集成测试 |

Trace 数据源：`storage/trace_storage.py` · `list_traces` / `get_trace`

---

## 7. 前端与流水线衔接

```text
侧栏 GATE/L3「切换执行模式」
  → /agent?autorun=1&toL5=1
  → runExecute()（L3 + L4 audit）
  → /l5?trace={trace_id}
```

| 页面 | 路径 | 职责 |
|------|------|------|
| L5 链路分析 | `/l5` | 散点/热力/溯源/六维/集成测试 |
| 运维概览 | `/` | 系统健康（非 L5 专属） |
| 五层画布 | `/canvas` | L5 节点：散点/热力/溯源/集成测试 |
| 架构导引 | `/guide` | 终版五层 + L5 方案说明 |

---

## 8. 代码映射

| 模块 | 路径 |
|------|------|
| 分析模型 | `security_agent/l5/analytics.py` |
| 集成测试 | `security_agent/l5/integration_tests.py` |
| API 路由 | `security_agent/api/routes/l5_routes.py` |
| 前端页面 | `frontend/src/views/L5Analytics.vue` |
| 前端 API | `frontend/src/api/l5.js` |
| 指标常量 | `frontend/src/constants/l5-metrics.js` |
