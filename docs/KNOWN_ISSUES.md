# 已知小问题与状态（2026-05-30）

> 答辩/联调时快速对照；权威计划见 [OPTIMIZATION_PLAN.md](OPTIMIZATION_PLAN.md)。

## 已修复

| 问题 | 修复 |
|------|------|
| Trace 阶段耗时 / 8h 时差 / 告警时间混淆 | 见上轮：`trace.py`、`trace_report.py`、`alert_routes.py` |
| 告警页需手动刷新 | `Alerts.vue` 30s 自动刷新 + 切回标签页立即拉取 |
| L2 与 Incident `trace_id` 不一致 | 对话 L2 使用 `spine.trace_id`；独立 flow 统一 `trace-` 前缀 |
| Trace 列表重复子 trace | `list_traces` 过滤 `skill_flow_end` 内嵌短 ID |
| 告警 RCA 展示弱 | `incident_responder` 的 `root_cause` / `recommendation` 写入回复与纪要 |
| 顶栏角标与 recent 不一致 | `fetchRecent` 后同步 `fetchUnreadCount` |
| 告警 → L2 处置路径长 | 告警页/顶栏 **L2 处置** → Skill Flows 预填 `alert_response` |

## 仍待处理

| # | 问题 | 说明 |
|---|------|------|
| 1 | 浏览器 P0 十页人工签字 | [P0_FRONTEND_WALKTHROUGH.md](P0_FRONTEND_WALKTHROUGH.md) |
| 2 | 麒麟实机 mac_checker | 见 [DEPLOY_KYLIN_LOONGARCH.md](DEPLOY_KYLIN_LOONGARCH.md) · `bootstrap-kylin-loongarch.sh` |
| 3 | 告警真·WebSocket 推送 | 当前为轮询（已够用）；WS 属 P2 |
| 4 | 历史 Trace 累计耗时 | 导出时自动换算；新数据已为增量 |
| 5 | 全自动 RCA pipeline | 严重/高告警才有 `incident_responder` 方案，非全场景 |

## 文档归并

重复 optimization 报告已删除，见上轮说明。保留 `FILE_STRUCTURE_OPTIMIZATION.md`、`LIGHTWEIGHT_REFACTOR.md`、`FINAL_IMPLEMENTATION_GUIDE.md`。
