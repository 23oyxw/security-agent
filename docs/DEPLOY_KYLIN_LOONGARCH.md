# 麒麟 V11 LoongArch 部署指南

> 适用：麒麟高级服务器 V11 Swan25 · LoongArch (loongarch64)  
> 读者：项目组成员、评审老师  
> 版本：v0.9.0

---

## 方式一：Git 拉取（推荐，网络畅通用这个）

```bash
# 1. 安装 git
sudo dnf install -y git

# 2. 克隆项目
git clone https://gitee.com/swok/security-agent.git
cd security-agent

# 3. 继续「环境初始化」步骤
```

## 方式二：压缩包部署（离线/无 git）

把 `dist/security-agent-v0.9.0-*.tar.gz` 拷贝到麒麟机，然后：

```bash
tar -xzf security-agent-v0.9.0-*.tar.gz
cd security-agent-v0.9.0-*
```

---

## 环境初始化

### 第一步：安装系统依赖

```bash
sudo dnf install -y \
  python3 python3-pip python3-devel \
  gcc gcc-c++ make \
  git curl
```

### 第二步：一键初始化

```bash
bash scripts/bootstrap-kylin-loongarch.sh
```

这个脚本会自动：
- 安装系统依赖（dnf）
- 尝试安装 uv，**如果 loongarch64 无预编译包则自动降级到 pip**
- 安装 Python 依赖（uv sync 或 pip install）
- 生成 `.env`（自动关闭 LiteLLM 代理）

### 第三步：配置 API Key

```bash
vi .env
```

必须修改的 2 行：

```env
LLM_API_KEY=sk-你的DeepSeek或OpenAI密钥
USE_LITELLM_PROXY=false
```

可选修改：

```env
SEC_API_PORT=8900        # 服务端口
SEC_API_HOST=0.0.0.0     # 监听地址（0.0.0.0 允许局域网访问）
```

### 第四步：检查前端文件

```bash
ls frontend/dist/index.html
```

如果文件不存在（`No such file or directory`）：

```bash
# 方式A：本机构建（需 nodejs，较慢）
sudo dnf install -y nodejs npm
cd frontend && npm install && npm run build && cd ..

# 方式B：从 x86 开发机拷贝 dist 目录
# 在开发机上：scp -r frontend/dist 用户名@麒麟机:~/security-agent/frontend/
```

### 第五步：创建受限用户（可选，需 root 权限）

```bash
sudo bash scripts/setup_restricted_user.sh
```

> 非 root 启动也可以正常使用，只是安全沙箱的权限隔离会降级（自动回退到当前用户）。

### 第六步：放行防火墙端口

```bash
# 如果开启了防火墙
sudo firewall-cmd --add-port=8900/tcp --permanent 2>/dev/null
sudo firewall-cmd --reload 2>/dev/null

# KYSEC 如果拦截（检查命令）
getenforce 2>/dev/null
```

### 第七步：启动服务

```bash
bash boot_start.sh
```

成功标志：

```
[boot_start] ✅ FastAPI 已启动 PID 12345 → http://0.0.0.0:8900
[boot_start] 前端 dist 已是最新，跳过构建
[boot_start] =========================================
[boot_start]   银河麒麟智能安全运维 Agent 已启动
[boot_start]   Web 控制台: http://0.0.0.0:8900
```

### 第八步：浏览器验证

打开麒麟机浏览器，访问：

```
http://<麒麟机IP>:8900
```

登录：`admin` / `admin123`

---

## 常见错误处理

| 报错 | 原因 | 解决 |
|------|------|------|
| `$'\r': 未找到命令` | Windows 换行符污染 | 用 git clone 拉取，或用 `sed -i 's/\r$//' scripts/*.sh` |
| `set: 无效的选项 -` | shell 不兼容 pipefail | git clone 最新版，或 `sed -i 's/set -euo pipefail/set -eu/' *.sh scripts/*.sh` |
| `uv: 未找到命令` | uv 未安装或不在 PATH | `export PATH="$HOME/.local/bin:$PATH"` 或重启终端 |
| `ModuleNotFoundError: fastapi` | 虚拟环境未创建 | 先执行 `bash scripts/bootstrap-kylin-loongarch.sh` |
| `端口 8900 被占用` | 旧进程未退出 | `bash boot_stop.sh` 后再启动 |
| `KYSEC 拦截` | 麒麟安全策略 | `sudo setenforce 0`（临时），正式部署放行端口 |

## 停止服务

```bash
bash boot_stop.sh
```

## 服务重启

```bash
bash boot_stop.sh
bash boot_start.sh
```

## 详细参考

- [麒麟依赖兼容性清单](deploy/KYLIN_DEPENDENCIES.md) — Python 包分级
- [麒麟权限处理指南](deploy/KYLIN_PERMISSIONS.md) — KYSEC / root 权限
- [麒麟实机验收清单](deploy/KYLIN_VERIFICATION.md) — 功能验证
