# 已知小问题与状态（2026-07-15）

> 答辩/联调时快速对照；权威计划见 [MASTER_PLAN.md](architecture/MASTER_PLAN.md)。

## 已修复（v0.9.0）

| 问题 | 修复 |
|------|------|
| Trace 阶段耗时 / 8h 时差 / 告警时间混淆 | `trace.py`、`trace_report.py`、`alert_routes.py` |
| 告警页需手动刷新 | `Alerts.vue` 30s 自动刷新 + 切回标签页立即拉取 |
| L2 与 Incident `trace_id` 不一致 | 对话 L2 使用 `spine.trace_id`；独立 flow 统一 `trace-` 前缀 |
| Trace 列表重复子 trace | `list_traces` 过滤 `skill_flow_end` 内嵌短 ID |
| 告警 RCA 展示弱 | `incident_responder` 的 `root_cause` / `recommendation` 写入回复与纪要 |
| 顶栏角标与 recent 不一致 | `fetchRecent` 后同步 `fetchUnreadCount` |
| 告警 → L2 处置路径长 | 告警页/顶栏 **L2 处置** → Skill Flows 预填 `alert_response` |
| P0 浏览器十页签字 | ✅ P0 已通过验收 |
| 沙箱 / MCP 热插拔 / Trace 缺失 | ✅ v0.9.0 全部补齐 |

## 仍待处理

| # | 问题 | 说明 |
|---|------|------|
| 1 | 麒麟实机 mac_checker | 见 [DEPLOY_KYLIN_LOONGARCH.md](DEPLOY_KYLIN_LOONGARCH.md) · `bootstrap-kylin-loongarch.sh` |
| 2 | 告警真·WebSocket 推送 | 当前为轮询（已够用）；WS 属 P2 |
| 3 | 全自动 RCA pipeline | 严重/高告警才有 `incident_responder` 方案，非全场景 |
| 4 | Gitee Wiki 双向同步 | push 已通，POST API 仍 405，暂用 git 方案 |

## 文档归并

v0.9.0 已清理 16 份过时/重复文档，当前保留 32 个 `.md` 文件。归档存根：`FILE_STRUCTURE_OPTIMIZATION.md`、`FINAL_IMPLEMENTATION_GUIDE.md`。
