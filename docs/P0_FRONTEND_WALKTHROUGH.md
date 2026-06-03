# P0 浏览器联调签字清单

> API 自动化见 `scripts/p0_frontend_checklist.sh` · 启动：`bash boot_start.sh` 或 `bash boot_start.sh --dev`

**登录**：`admin` / `admin123`  
**基址**：`http://<主机>:8900/`（生产）或 `http://<主机>:5173/`（`--dev`）

在每行末打勾 `[x]`，失败时记录：页面、操作、Network 状态码、响应片段。

---

## 1. 登录 `/login`

- [ ] 输入账号密码可进入首页
- [ ] 错误密码有提示，不白屏
- [ ] F12 Console 无红色未捕获异常

## 2. 仪表盘 `/`

- [ ] 健康/指标区域有数据或合理空态
- [ ] 告警列表可加载（`GET /api/alerts/` 200）
- [ ] MCP 数量与后端一致

## 3. 智能助手 `/agent`（L3）

- [ ] 页头 **L3 编排**、WebSocket/REST、在线状态
- [ ] 点击「扫描报告」→ 消息带 **L2 · scan_report**（可无 LLM Key）
- [ ] 多工具问题 → **L3 · 编排** + **L1 · 工具名** 标签
- [ ] 右侧：架构说明、**Token/费用/上下文占比**
- [ ] **Trace 记录** 可点击跳转 `/trace`
- [ ] 断开后 **① REST** 仍能回复

## 4. 安全闸门 `/safety`

- [ ] `rm -rf /` 类命令（target=`rm -rf /`）→ **deny / confirm / escalate** 之一
- [ ] `ls -la` 类命令 → **allow** 或低风险 verdict
- [ ] 待审批列表可加载（S4）

## 5. 执行器 `/executor`

- [ ] 低风险命令执行成功
- [ ] 高危命令触发审批或拒绝（与配置一致）

## 6. 推理 Trace `/trace`

- [ ] 列表有记录
- [ ] 非 S0 行显示降级标签
- [ ] 「导出」可下载 JSON bundle

## 7. MCP `/mcp`（L1）

- [ ] 页头 **L1 原子能力**、架构说明高亮 L1
- [ ] 服务器列表 ≥ 1
- [ ] **全部健康检查** / **热插拔 Reload** 不 500

## 8. 告警 `/alerts`

- [ ] 列表加载；筛选/刷新正常

## 9. 知识库 `/knowledge`

- [ ] Playbooks 或搜索可用

## 10. 用户 `/users`、Skill Flows（L2）、工作流

- [ ] Skill 流程页见 **4 条** flow（含 block_process）、步骤条与文本报告
- [ ] 各页至少打开一次无 404/500

---

## 联调 FAQ（常见疑问）

### 1. 登录一次就自动登录？

正常。Token 存在 `localStorage`，刷新仍进系统。要测登录页：右上角 **退出登录**，或浏览器清除站点数据。

### 3. 安全助手模型 400 / 如何验 REST 回退？

- **400 / 熔断 mimo-v2.5-pro**：后端已自动降为 `mimo-v2.5`；若仍熔断可 `curl -X POST http://127.0.0.1:8900/api/resilience/circuits/reset -H "Authorization: Bearer <token>"` 后重启 API。
- **400 Invalid model**：`.env` 建议 `LLM_MODEL=mimo-v2.5`（或 LiteLLM：`USE_LITELLM_PROXY=true` + `LLM_MODEL=mimo-chat`）。
- **REST 回退（三步）**：
  1. 点 **「① 切 REST」** → 黄条提示 + 标签 **传输: REST**
  2. 点 **「扫描报告」** 或输入任意话点发送
  3. 出现标签 **「上条: REST」** 即有反应（与 WS 共用后端，仅传输不同）
  4. 点 **「② 重连 WS」** 可恢复 WebSocket
- **扫描仍可用**：点「扫描报告」走编排短路，不依赖 LLM；工具 Trace 为真数据。

### 4–5. 闸门/执行器与告警是否实时同步？

**不会自动同步到告警页**。闸门/执行器写审计与 trace；告警来自 `data/alerts` 与 monitor。顶栏与告警页均为 **30 秒轮询**（告警页切回标签也会刷新）。可从告警行点 **L2 处置** 跳转 Skill Flows。

### 6. Trace 是否假数据？

**真数据**（sqlite + `data/traces/*.jsonl`）。点 **「详情」** 拉 `/api/trace/{id}` 与 export 卷宗；新操作后点 **刷新**。

### 7. MCP 看不到上次检查 / Reload？

需点 **「全部健康检查」** 或行内 **「健康检查」** 才会填「上次检查」；**热插拔 Reload** 在表头右侧。

### 9. 知识库剧本少？

后端 `PLAYBOOKS` 30+ 条；UI 按接口分页展示，标签为 `threat_tags` 子集。

---

## 签字

| 项 | 结果 |
|----|------|
| 日期 | |
| 执行人 | |
| 通过页数 | /10 |
| 阻塞问题 | |

---

*完成后在 `docs/OPTIMIZATION_PLAN.md` 将 P0-7 标为 ✅。*
