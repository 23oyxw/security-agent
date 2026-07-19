# 麒麟 LoongArch 依赖兼容性清单

> v0.9.0 · 目标: 麒麟高级服务器 V11 · LoongArch (loongarch64) · dnf 包管理

## 原则

- **优先 dnf 源**：龙架构预编译包从麒麟源安装，不编译 C 扩展
- **PyPI fallback**：纯 Python 包从 `pip install` 安装
- **禁用 LiteLLM Docker**：龙架构无对应镜像 → 直连 DeepSeek/OpenAI API

## 一、系统依赖 (dnf)

```bash
dnf install -y python3.10 python3.10-devel python3.10-pip
```

## 二、Python 依赖分级

### ✅ 纯 Python — pip 直接安装（无 C 扩展）

| 包 | 版本 | 用途 |
|----|------|------|
| httpx | >=0.28.1 | HTTP 客户端 |
| openai | >=2.37.0 | LLM API 调用 |
| python-dotenv | >=1.2.2 | 环境变量加载 |
| fastapi | >=0.115.0 | Web 框架 |
| uvicorn | >=0.34.0 | ASGI 服务器（纯 Python 模式） |
| python-multipart | >=0.0.18 | 文件上传 |
| PyJWT | >=2.10.0 | JWT 令牌 |
| passlib | >=1.7.4 | 密码哈希（不用 bcrypt，用纯 Python pbkdf2） |
| websockets | >=15.0 | WebSocket |
| pyyaml | >=6.0.3 | YAML 解析（龙架构源有预编译 wheel） |
| slowapi | >=0.1.9 | API 限流 |
| tenacity | >=8.2.0 | 重试策略 |

### ⚠️ 含 C 扩展 — dnf 优先或需编译

| 包 | 版本 | 龙架构方案 |
|----|------|-----------|
| numpy | >=1.26.0 | `pip install numpy`（PyPI 已有 loongarch64 wheel） |
| pandas | >=2.0.0 | `pip install pandas`（依赖 numpy） |
| matplotlib | >=3.8.0 | `pip install matplotlib`（依赖 numpy） |
| pillow | >=10.0.0 | `pip install pillow`（PyPI 有 loongarch64 wheel） |
| psutil | >=7.2.2 | `pip install psutil`（需编译，dnf 装 `gcc` + `python3-devel` 即可） |
| plotly | >=6.0.0 | 纯 Python（但体积大，~15MB），非必须可跳过 |

### ❌ 不建议在麒麟上安装

| 包 | 原因 | 替代方案 |
|----|------|---------|
| streamlit | 重依赖 + C 扩展多 + 非主 UI | Vue3 :8900 为主，Streamlit 仅在 x86 备用 |
| mcp | 依赖链复杂，部分子依赖无龙架构 wheel | 仅开发机使用，麒麟上不跑 MCP SDK 服务端 |
| bcrypt (passlib[bcrypt]) | 需编译 C 扩展 | 改用 passlib 纯 Python pbkdf2_sha256 |

## 三、麒麟一键安装命令

```bash
# 1. 系统依赖
dnf install -y python3.10 python3.10-devel python3.10-pip gcc

# 2. 核心运行时（纯 Python，秒装）
pip install httpx openai python-dotenv fastapi uvicorn \
  "python-multipart>=0.0.18" PyJWT "passlib>=1.7.4" \
  websockets pyyaml slowapi tenacity

# 3. 可选：数据可视化
pip install numpy pandas matplotlib pillow plotly psutil

# 4. 安装 security-agent 自身
pip install -e . --no-deps
```

## 四、验证命令

```bash
python -c "
from security_agent.config import *
from security_agent.api.app import app
print('OK: all imports work on LoongArch')
"
```
