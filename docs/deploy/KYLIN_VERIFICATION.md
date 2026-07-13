# 麒麟 LoongArch 实机验证报告

> **赛题硬性要求**: 安全校验(30%) + 系统创新(20%) 维度需实机验证证据  
> **目标平台**: 麒麟高级服务器 V11 · LoongArch (Swan25)  
> **执行人**: ________ · **日期**: ________

---

## 一、实机环境信息

```bash
uname -a
# 输出: ________

cat /etc/os-release
# 输出: ________

getenforce
# 输出: ________ (KYSEC 状态)

python3 --version
# 输出: ________

node --version
# 输出: ________

df -h /
# 输出: ________
```

---

## 二、启动验证

### 2.1 依赖安装

```bash
# dnf 包安装
sudo dnf install -y python3 python3-pip python3-devel gcc gcc-c++ make git curl

# uv 安装
pip3 install uv

# 项目依赖
cd ~/security-agent
uv sync
```

- [ ] dnf 依赖安装成功
- [ ] uv sync 无错误
- [ ] `.env` 已配置

### 2.2 启动系统

```bash
cp .env.example .env
# 编辑 .env（填入 LLM_API_KEY）
bash scripts/boot_start_loongarch.sh
```

- [ ] 启动成功，输出 `Uvicorn running on http://0.0.0.0:8900`
- [ ] 浏览器访问 `http://<麒麟IP>:8900/` → 显示登录页
- [ ] 登录 `admin / admin123` → 进入 Dashboard

### 2.3 截图留存

- [ ] 登录页截图 → `screenshots/login.png`
- [ ] Dashboard 截图 → `screenshots/dashboard.png`

---

## 三、核心功能验证

### 3.1 安全闸门（三层防御）

```bash
# 单测
python tests/test_three_layer_defense.py
```

预期输出: `全部测试通过! 三层防御体系运行正常`

- [ ] 6/6 测试通过
- [ ] 前端 SafetyGate 页面可评估+执行

### 3.2 MAC/KYSEC 检查

```bash
python -c "
from security_agent.safety_gate.mac_checker import get_mac_checker
c = get_mac_checker(enforce=True)
print(c.status())
"
```

- [ ] MAC checker 正常检测到 KYSEC/SELinux
- [ ] 截图留存 → `screenshots/mac_check.png`

### 3.3 全域沙箱

```bash
python tests/test_sandbox_overlay.py
```

预期输出: `ALL PASS - SandboxSession end-to-end verified!`

- [ ] 19/19 测试通过
- [ ] OverlayFS 在麒麟上实际隔离生效

### 3.4 告警降噪

```bash
python tests/test_alert_throttle.py
```

- [ ] 24/24 测试通过

### 3.5 终端智能

```bash
python tests/test_terminal_context.py
```

- [ ] 28/28 测试通过

### 3.6 文档智能

```bash
python tests/test_document_pipeline.py
```

- [ ] 23/23 测试通过

### 3.7 边界探针

```bash
python tests/test_boundary_fuzzer.py
```

- [ ] 16/16 测试通过
- [ ] 12 探针在麒麟上都能运行（部分 Linux 专用探针应有输出）

### 3.8 知识自愈

```bash
python tests/test_knowledge_guard.py
```

- [ ] 15/15 测试通过

### 3.9 能力装箱

```bash
python tests/test_capability_boxing.py
```

- [ ] 12/12 测试通过

---

## 四、麒麟特有功能验证

### 4.1 龙架构 Python 依赖

```bash
# 确认所有依赖在 LoongArch 上可用
pip list | grep -E "fastapi|uvicorn|httpx|mcp|psutil"
```

- [ ] 无编译错误（特别注意 uvloop/httptools 在龙架构上可能无预编译包）

### 4.2 LiteLLM 禁用确认

```bash
grep USE_LITELLM_PROXY .env
# 应为: USE_LITELLM_PROXY=false
```

- [ ] LiteLLM 已禁用（龙架构无 Docker 镜像）

### 4.3 麒麟安全策略兼容

```bash
# 确认 8900 端口未被 KYSEC 拦截
ss -tlnp | grep 8900

# 确认受限用户可创建
sudo useradd -r -s /sbin/nologin -M agent_ops
```

- [ ] 端口 8900 正常监听
- [ ] agent_ops 用户创建成功

---

## 五、验证结论

| 验证项 | 状态 | 备注 |
|--------|------|------|
| 环境安装 | ⬜ | |
| 系统启动 | ⬜ | |
| 安全闸门 | ⬜ | |
| MAC 检查 | ⬜ | |
| 全域沙箱 | ⬜ | |
| 告警降噪 | ⬜ | |
| 终端智能 | ⬜ | |
| 文档智能 | ⬜ | |
| 边界探针 | ⬜ | |
| 知识自愈 | ⬜ | |
| 能力装箱 | ⬜ | |
| 龙架构兼容 | ⬜ | |
| KYSEC 兼容 | ⬜ | |

**总评**: ________

---

*模板生成: 2026-07-13 · 请在实机上执行并勾选*
