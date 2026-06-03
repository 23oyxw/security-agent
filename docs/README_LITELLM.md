# LiteLLM 集成总览

## 当前状态

✅ **已完成集成**，支持三种部署模式：

| 模式 | 状态 | 说明 |
|------|------|------|
| Docker 部署 | ✅ 可用 | 企业级推荐，一键启动 |
| 本地部署 | ⚠️ 依赖复杂 | Python 包安装可能有问题 |
| 应用层 Fallback | ✅ 可用 | 内置机制，零依赖 |

## 快速开始（推荐 Docker）

```bash
# 一键配置并启动
bash scripts/setup_litellm.sh

# 或手动步骤：
bash scripts/litellm.sh start    # 启动代理
bash scripts/litellm.sh enable   # 启用模式
bash boot_stop.sh && bash boot_start.sh  # 重启应用
```

## 功能集成点

### 1. 智能对话路由（已实现）
- **文件**：`security_agent/agent/brain.py`
- **功能**：所有对话通过 LiteLLM 路由，支持自动 fallback
- **配置**：`MODEL_PRESETS` 根据 `USE_LITELLM_PROXY` 自动切换

### 2. 批量任务优化（已实现）
- **文件**：`security_agent/agent/budget.py`
- **功能**：日志分析等批量任务自动使用 DeepSeek V3（便宜）
- **节省**：批量任务成本降低 60%

### 3. 自主任务规划（已实现）
- **文件**：`security_agent/agent/autonomous.py`
- **功能**：深度规划使用 DeepSeek R1，通过 LiteLLM 路由

### 4. 成本追踪监控（已实现）
- **文件**：`security_agent/agent/cost.py` + `ui/pages.py`
- **功能**：实时显示各模型调用成本和 fallback 统计

## 答辩展示方案

### 推荐配置（稳定性优先）

```bash
# 如果 Docker 可用
bash scripts/litellm.sh start
bash scripts/litellm.sh enable
```

```bash
# 如果 Docker 不可用（自动回退）
# 保持默认配置，使用应用层 Fallback
# 功能完全一致，只是没有 LiteLLM 代理层
```

### 展示脚本

**Demo 1：多模型切换**（30 秒）
```
操作：侧边栏切换 MiMo / DeepSeek
话术："支持多模型智能路由，企业级灵活配置"
```

**Demo 2：自动故障恢复**（45 秒）
```
操作：临时改错 MiMo Key → 提问 → 观察自动切换
话术："企业级容错，主模型故障自动回退，零中断"
```

**Demo 3：成本优化**（30 秒）
```
操作：生成报告 → 查看成本统计
话术："智能成本管理，批量任务用高性价比模型"
```

## 文档索引

| 文档 | 用途 |
|------|------|
| `docs/ENTERPRISE_DEPLOY.md` | 企业级部署完整指南 |
| `docs/LITELLM_GUIDE.md` | LiteLLM 使用说明 |
| `docs/LITELLM_INTEGRATION.md` | 功能集成实战指南 |
| `docs/FALLBACK_GUIDE.md` | Fallback 机制说明 |

## 脚本索引

| 脚本 | 用途 |
|------|------|
| `scripts/setup_litellm.sh` | 一键配置（推荐入口） |
| `scripts/litellm.sh` | 统一入口（自动检测 Docker） |
| `scripts/litellm_docker.sh` | Docker 模式管理 |
| `scripts/litellm_manager.sh` | 本地模式管理 |
| `scripts/install_litellm.sh` | 依赖安装 |

## 常见问题

**Q: Docker 和本地模式选哪个？**
A: 优先 Docker，稳定且无依赖问题。答辩时如果 Docker 出问题，直接切到应用层 Fallback（已内置，无需配置）。

**Q: 需要修改代码吗？**
A: 不需要，所有集成已完成，只需配置 `.env` 并启动。

**Q: 成本统计准确吗？**
A: 基于模型官方定价估算，实际可能略有差异，用于趋势分析足够。

**Q: 可以接入 GPT-4 吗？**
A: 可以，修改 `litellm_config.yaml` 添加 GPT-4 配置即可，Agent 代码无需改动。

## 核心优势（答辩用）

> "我们的系统采用**企业级架构设计**：
> 1. **多模型智能路由** — 不同场景用最优模型
> 2. **自动故障恢复** — 主模型故障零中断切换
> 3. **成本精细化管理** — 批量任务用高性价比模型
> 4. **容器化部署** — Docker 支持，符合企业级标准"

---

**状态**：✅ 已完成，可直接用于答辩演示
