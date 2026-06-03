# LiteLLM 代理集成实战 — 项目功能应用指南

## 概述

本文档展示如何在安全运维 Agent 的各个功能模块中应用 LiteLLM 代理，实现企业级的多模型智能路由。

## 快速启用（3 分钟）

### 方式一：Docker 部署（推荐）

```bash
# 1. 启动 LiteLLM 代理
bash scripts/litellm.sh start

# 2. 启用代理模式
bash scripts/litellm.sh enable

# 3. 重启应用
bash boot_stop.sh && bash boot_start.sh
```

### 方式二：应用层 Fallback（备选）

如果 Docker 不可用，使用内置 Fallback 机制：

```bash
# .env 保持默认（USE_LITELLM_PROXY=false）
# 系统会自动使用应用层 Fallback
```

## 功能场景与模型路由

### 场景 1：日常安全问答（快速响应）

**功能**：用户询问"系统最近有异常吗？"

**路由策略**：
```
用户提问 → LiteLLM 代理 → MiMo v2.5 (快速模型)
                              ↓ 失败
                         → DeepSeek V3 (备用)
```

**配置**：
```yaml
# litellm_config.yaml
model_list:
  - model_name: mimo-fast      # UI 选择"快速轻量"时使用
    litellm_params:
      model: openai/mimo-v2.5
      api_base: https://token-plan-cn.xiaomimimo.com/v1
```

**代码实现**（已在 brain.py 自动处理）：
```python
# AgentBrain 自动根据配置选择路由
fallback_client = FallbackClient(
    primary_client=openai_client,
    primary_model="mimo-v2.5",      # 快速模型
    fallback_model="deepseek-chat" # 备用
)
```

**UI 显示**：
```
Token: 850 · 0.3分          ← 低成本快速响应
```

---

### 场景 2：深度安全分析（深度推理）

**功能**：用户要求"全面分析系统安全风险并给出加固建议"

**路由策略**：
```
复杂请求 → LiteLLM 代理 → DeepSeek R1 (推理模型)
                              ↓ 超时/限流
                         → MiMo Pro (回退)
```

**配置**：
```yaml
# litellm_config.yaml
model_list:
  - model_name: deepseek-reasoner
    litellm_params:
      model: deepseek/deepseek-reasoner
      api_base: https://api.deepseek.com/v1
```

**UI 切换**：
```python
# ui/state.py 中切换预设
MODEL_PRESETS = {
    "DeepSeek R1（深度推理）": {
        "api_key": AUTONOMOUS_API_KEY,
        "base_url": LITELLM_PROXY_URL,  # 通过代理
        "model": "deepseek-reasoner",
    }
}
```

**成本显示**：
```
Token: 3,200 · 1.2分          ← 深度推理成本较高但值得
```

---

### 场景 3：批量日志分析（高性价比）

**功能**：分析 1000 条系统日志，识别异常模式

**路由策略**：
```
批量任务 → LiteLLM 代理 → DeepSeek V3 (性价比模型)
```

**BudgetAgent 自动路由**（已集成）：
```python
# security_agent/agent/budget.py
class BudgetAgent:
    def __init__(self):
        self.client = OpenAI(
            api_key=config.BUDGET_API_KEY,
            base_url=config.BUDGET_BASE_URL,  # 指向 LiteLLM 代理
        )
        self.model = "deepseek-chat"  # 低成本模型
```

**日志分析示例**：
```python
# 当日志条目 > 10 条时，自动使用 Budget 模型
if len(matches) >= 10:
    budget_agent = get_budget_agent()
    ai_summary = budget_agent.summarize_logs(matches)
```

**成本对比**：
| 模型 | 成本 | 适用 |
|------|------|------|
| MiMo Pro | ¥0.8/次 | 对话交互 |
| DeepSeek V3 | ¥0.3/次 | 批量分析 ✓ |

---

### 场景 4：自动故障恢复（Fallback 演示）

**功能**：主模型故障时自动切换，用户无感知

**配置**（已内置）：
```yaml
# litellm_config.yaml
fallbacks:
  - mimo-chat:
      - deepseek-chat    # 自动回退链
```

**故障场景模拟**：
```bash
# 1. 正常对话（使用 MiMo）
用户: "查看系统状态"
响应: 正常（mimo-v2.5-pro）
Token: 1,200 · 0.6分

# 2. 模拟 MiMo 故障（临时改错 API Key）
# （实际故障如：超时、429限流、服务异常）

# 3. 自动回退（使用 DeepSeek）
用户: "查看系统状态"
响应: 正常（deepseek-chat）🔄
Token: 1,200 · 0.3分 · 已回退到 deepseek-chat

# 侧边栏统计：
🔄 自动回退 (Fallback)
✅ 已启用
主模型: mimo-v2.5-pro
备用: deepseek-chat
已触发 1 次自动回退
```

**答辩展示话术**：
> "各位评委老师，我现在演示一个**企业级容错场景**。假设 MiMo 服务突然不可用...（操作）... 可以看到系统**自动切换到 DeepSeek**，用户完全无感知，对话继续正常进行。这就是我们的 **Fallback 机制**。”

---

## 核心功能集成点

### 1. 智能助手对话（chat）

**文件**：`ui/pages.py:887`

**集成方式**：
```python
brain = state.get_brain()  # 自动使用 LiteLLM 配置

# 发送消息
result = await brain.chat(text)

# 显示 fallback 状态
if result.get("fallback_used"):
    st.caption(f"🔄 已回退到 {result['fallback_model']}")
```

**效果**：用户无感知切换，体验流畅

---

### 2. 安全报告生成（report）

**文件**：`security_agent/tools/registry.py:37`

**集成方式**（已自动）：
```python
async def tool_generate_report(use_budget_model: bool = True):
    if use_budget_model and config.BUDGET_API_KEY:
        budget_agent = get_budget_agent()  # 使用 LiteLLM 路由的 Budget 模型
        executive_summary = budget_agent.generate_report_summary(data)
```

**成本优化**：
- 报告生成使用 DeepSeek V3（便宜 60%）
- 总结质量相当

---

### 3. 批量日志分析（log_analyzer）

**文件**：`security_agent/skills/log_analyzer/skill.py`

**集成方式**（已自动）：
```python
# 当日志匹配较多时，自动使用 Budget 模型
if len(matches) >= 10 and config.BUDGET_API_KEY:
    budget_agent = get_budget_agent()
    ai_summary = budget_agent.summarize_logs([m.to_dict() for m in matches])
```

**批量处理优势**：
- 1000 条日志分析成本：¥0.5（MiMo 需 ¥2.0）
- 性价比提升 4 倍

---

### 4. 自主任务规划（autonomous）

**文件**：`security_agent/agent/autonomous.py`

**集成方式**：
```python
class AutonomousAgent:
    def __init__(self):
        # 使用 Reasoner 模型（通过 LiteLLM 路由）
        self.client = OpenAI(
            api_key=config.AUTONOMOUS_API_KEY,
            base_url=config.AUTONOMOUS_BASE_URL,  # 指向 LiteLLM
        )
        self.model = "deepseek-reasoner"  # 深度规划
```

**多步任务示例**：
```
用户: "全面检查系统安全并生成加固方案"

Step 1: [规划] 使用 DeepSeek R1 生成执行计划
Step 2: [扫描] 调用本地工具执行安全检查
Step 3: [分析] 使用 Budget 模型分析扫描结果
Step 4: [总结] 使用 R1 生成完整加固报告

成本分布：
- R1 规划: ¥0.8
- 工具执行: ¥0
- Budget 分析: ¥0.2
- R1 总结: ¥0.6
总计: ¥1.6（比全程用 MiMo 省 50%）
```

---

## 成本追踪与监控

### 实时成本显示

**侧边栏统计**（已集成）：
```
📊 本会话统计
调用: 15 次 | Token: 12,450
💰 预估成本: 4.8分

各模型详情 ▼
• mimo-v2.5-pro: 8次, 3.2分
• deepseek-chat: 5次, 1.2分  ← 备用模型节省成本
• deepseek-reasoner: 2次, 0.4分
```

**按功能统计**：
| 功能模块 | 调用次数 | 成本 | 主要模型 |
|---------|---------|------|---------|
| 智能对话 | 50 | ¥0.35 | MiMo |
| 安全报告 | 3 | ¥0.12 | Budget |
| 日志分析 | 10 | ¥0.08 | Budget |
| 深度分析 | 2 | ¥0.15 | Reasoner |
| **总计** | **65** | **¥0.70** | 混合策略 |

---

## 答辩演示脚本

### Demo 1：多模型智能路由（30 秒）

```
[操作] 打开侧边栏模型切换

"各位评委，我们的系统支持多模型智能路由：
- 日常对话用 MiMo（快速）
- 批量分析用 DeepSeek V3（便宜）
- 深度推理用 DeepSeek R1（精准）

更重要的是，通过 LiteLLM 代理统一管理。"

[操作] 切换不同模型提问同一问题，展示不同响应风格
```

### Demo 2：自动故障恢复（45 秒）

```
"企业级系统必须考虑容错。我现在模拟主模型故障："

[操作] 临时修改 litellm_config.yaml，把 MiMo Key 改错
[操作] 发起对话

"可以看到，系统**自动检测到 MiMo 不可用**，
**2秒内切换到 DeepSeek**，用户完全无感知。"

[操作] 展示侧边栏 fallback 统计
"这里显示已触发 1 次自动回退。"
```

### Demo 3：成本优化策略（30 秒）

```
"在企业场景中，成本控制很重要。看这组数据："

[操作] 生成一份安全报告
"这个报告使用了 Budget 模型（DeepSeek V3），
成本只有 MiMo 的 40%，但质量相当。"

[操作] 展示成本统计
"系统自动选择性价比最高的模型，
批量任务用 V3，对话用 MiMo，深度分析用 R1。"
```

---

## 故障排查

### 问题 1：LiteLLM 启动失败

**检查**：
```bash
bash scripts/litellm.sh status
```

**解决**：
```bash
# Docker 模式
bash scripts/litellm.sh stop
bash scripts/litellm.sh start

# 或切换到应用层 Fallback
# 保持 USE_LITELLM_PROXY=false，使用内置机制
```

### 问题 2：模型切换不生效

**检查**：
```bash
# 确认 .env 配置
grep USE_LITELLM_PROXY .env

# 重启应用
bash boot_stop.sh && bash boot_start.sh
```

### 问题 3：成本统计不显示

**检查**：
- 确认 token_usage 正常返回
- 检查 cost.py 中的模型价格配置

---

## 总结

**LiteLLM 集成为项目带来的企业级能力**：

1. ✅ **高可用**：自动 fallback，零中断服务
2. ✅ **成本优化**：智能路由，批量任务用便宜模型
3. ✅ **灵活扩展**：随时接入新模型（GPT-4、Claude 等）
4. ✅ **统一监控**：成本、日志、性能一站式管理

**答辩核心卖点**：
> "我们的系统不仅实现了**智能运维**，更具备**企业级架构**——多模型智能路由、自动故障恢复、成本精细化管理，符合大型企业的生产环境要求。"
