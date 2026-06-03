# Fallback 自动回退机制

## 什么是 Fallback？

**Fallback** = 当主模型调用失败时，**自动切换到备用模型**，用户无感知。

```
正常情况：
你的提问 → MiMo API → 正常回答

MiMo 故障时：
你的提问 → MiMo API (超时) → 自动切换 → DeepSeek API → 正常回答
         ↓ 失败                ↓ Fallback 触发     ✓ 成功
```

## 为什么需要 Fallback？

| 场景 | 没有 Fallback | 有 Fallback |
|------|--------------|-------------|
| MiMo 服务超时 | ❌ 用户看到错误 | ✅ 自动用 DeepSeek 回答 |
| MiMo 限流 (429) | ❌ 请稍后再试 | ✅ 自动切换到 DeepSeek |
| MiMo 服务器错误 | ❌ 服务不可用 | ✅ 备用模型继续服务 |

## 如何启用

**无需安装 LiteLLM，应用层自动实现！**

只需要在 `.env` 中配置备用模型的 API Key：

```env
# MiMo 是主模型（必须配置）
LLM_API_KEY=your_mimo_key
LLM_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1
LLM_MODEL=mimo-v2.5-pro

# DeepSeek 作为备用模型（配置即启用 fallback）
BUDGET_API_KEY=your_deepseek_key
BUDGET_BASE_URL=https://api.deepseek.com/v1
BUDGET_MODEL=deepseek-chat
```

**自动识别规则**：
- 主模型是 MiMo 系列 → 备用自动选 DeepSeek V3
- 已配置 `BUDGET_API_KEY` → 启用 fallback

## 触发条件

当主模型出现以下错误时自动触发 fallback：

- ⏱️ **超时** (timeout)
- 🚫 **限流** (429 / rate limit)
- 💥 **服务器错误** (5xx / server error)
- 🔌 **连接失败** (connection error)
- ❌ **服务不可用** (unavailable)

**不会触发 fallback 的情况**：
- API Key 错误（配置问题）
- 模型不存在（配置问题）
- 请求格式错误（应用问题）

## UI 显示

### 侧边栏状态

```
🔄 自动回退 (Fallback)
✅ 已启用
主模型: mimo-v2.5-pro
备用: deepseek-chat
已触发 3 次自动回退      ← 显示累计次数
```

或

```
🔄 自动回退 (Fallback)
⚠️ 未配置备用模型
*配置 DeepSeek API Key 启用自动回退*
```

### 聊天记录中

正常调用：
```
📝 1,032 tokens · 💰 0.6 分
```

触发 fallback 后：
```
📝 1,032 tokens · 💰 0.3 分 · 🔄 已回退到 deepseek-chat
```

## 技术实现

```python
# 在 AgentBrain 中自动处理
fallback_client = FallbackClient(
    primary_client=openai_client,      # MiMo
    primary_model="mimo-v2.5-pro",
    fallback_config=FallbackConfig(     # DeepSeek
        fallback_model="deepseek-chat",
        fallback_api_key=...,
    )
)

# 调用时自动处理 fallback
response, metadata = fallback_client.chat_completion(
    messages=...,
    tools=...,
)

# metadata 包含：
# - fallback_used: bool  # 是否使用了备用
# - fallback_model: str  # 实际使用的模型
```

## 与 LiteLLM 的区别

| 特性 | 应用层 Fallback (当前) | LiteLLM 代理 |
|------|---------------------|-------------|
| **安装** | 无需安装 | 需要安装 litellm |
| **配置** | 配置 API Key 即可 | 需要配置代理 |
| **启动** | 随应用启动 | 需单独启动代理进程 |
| **fallback** | ✅ 应用层自动处理 | ✅ 代理层自动处理 |
| **日志** | 应用日志 | 统一代理日志 |
| **成本追踪** | 应用内统计 | 代理统一统计 |

**答辩推荐**：使用应用层 Fallback，更简单稳定！

## FAQ

### Q1: 回退后对话质量会变差吗？

**A**: DeepSeek V3 能力接近 MiMo，日常安全运维问答质量相当。深度推理任务建议直接使用 DeepSeek R1。

### Q2: 如何知道是否触发了 fallback？

**A**: 
1. 侧边栏显示累计触发次数
2. 聊天记录显示 "🔄 已回退到 xxx"
3. 返回的模型名称是备用模型

### Q3: 可以配置多个备用模型吗？

**A**: 当前只支持单级 fallback（1主 + 1备）。如需多级，建议使用 LiteLLM 代理。

### Q4: fallback 会增加成本吗？

**A**: 会，但不多。DeepSeek V3 价格比 MiMo 便宜，实际可能更省钱。

### Q5: 如何测试 fallback 是否工作？

**A**: 临时把主模型 API Key 改成错误的，发起对话，观察是否自动切换到备用。

```env
# 测试配置（把 MiMo Key 改错）
LLM_API_KEY=wrong_key_here
BUDGET_API_KEY=correct_deepseek_key
```

然后提问，应该看到 "🔄 已回退到 deepseek-chat"。

## 配置示例

### 最简配置（只用 MiMo，无 fallback）
```env
LLM_API_KEY=your_mimo_key
# BUDGET_API_KEY 不配置 = 无 fallback
```

### 推荐配置（MiMo + DeepSeek fallback）
```env
# 主模型
LLM_API_KEY=your_mimo_key
LLM_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1
LLM_MODEL=mimo-v2.5-pro

# 备用模型（自动启用 fallback）
BUDGET_API_KEY=your_deepseek_key
BUDGET_BASE_URL=https://api.deepseek.com/v1
BUDGET_MODEL=deepseek-chat
```

### 只用 DeepSeek（无 fallback）
```env
LLM_API_KEY=your_deepseek_key
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
# 没有配置 BUDGET，所以没有 fallback
```
