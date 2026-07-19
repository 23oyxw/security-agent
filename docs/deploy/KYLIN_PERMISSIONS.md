# 麒麟 V11 权限处理指南

> v0.9.0 · 麒麟高级服务器 V11 · LoongArch + KYSEC 安全策略

## 一、tar 解压后脚本权限修复

```bash
tar -xzf security-agent-v0.9.0-*.tar.gz
cd security-agent-v0.9.0-*

# ⚠️ 关键：tar 解压后 .sh 文件丢失执行权限
find . -name '*.sh' -exec chmod +x {} \;
```

## 二、启动方式选择

| 方式 | 命令 | 需要 root | 适用场景 |
|------|------|----------|---------|
| **普通启动**（推荐） | `bash boot_start.sh` | ❌ 不需要 | 日常运维、演示答辩 |
| 龙架构启动 | `bash scripts/boot_start_loongarch.sh` | ❌ 不需要 | LoongArch 专用 |
| 一键安装 | `bash scripts/bootstrap-kylin-loongarch.sh` | ⚠️ pip 安装可能需要 | 首次部署 |

> **用 `bash xxx.sh` 调用脚本**，不需要文件自身有 +x 权限。

## 三、boot_start.sh 在麒麟上的行为

```
boot_start.sh 执行流程:
  ├── [自动] uv sync / pip install ← 需要网络
  ├── [自动] 启动 LiteLLM Docker   ← 需要 docker 组，麒麟上自动跳过
  ├── [自动] 创建 agent_ops 用户   ← 需要 root，非 root 静默跳过
  ├── [自动] 启动 FastAPI :8900    ← 不需要 root ✅
  └── [自动] 构建/加载前端 dist    ← 不需要 root ✅
```

**非 root 用户启动的结果**：
- ✅ FastAPI 正常运行在 :8900
- ✅ 前端正常加载
- ⚠️ 沙箱降权功能降级（无 agent_ops，PrivilegeBroker 回退到当前用户）
- ⚠️ 告警桌面通知不可用（无 notify-send）

## 四、需要 root 的操作（按需执行）

### 4.1 创建受限用户（推荐）

```bash
sudo bash scripts/setup_restricted_user.sh
```

此脚本会：
- 创建 `agent_ops` 系统用户（无登录 shell）
- 创建 `/var/log/security_agent` 日志目录
- 创建 `/tmp/security_agent` 临时目录
- 创建 `/etc/security_agent` 配置目录

**如果不执行**：沙箱执行时会回退到当前用户，安全隔离降级但不影响功能。

### 4.2 放行 KYSEC 端口（如被拦截）

```bash
# 检查 KYSEC 状态
getenforce

# 如果 Enforcing 且 8900 被拦截：
sudo firewall-cmd --add-port=8900/tcp --permanent
sudo firewall-cmd --reload

# 如果 KYSEC 拦截进程：
sudo setenforce 0  # 临时放行（仅调试用，答辩时建议放行端口而非关闭）
```

### 4.3 安装系统服务（可选）

```bash
sudo bash scripts/install_systemd.sh
```

## 五、root 检查对照表

| 脚本 | 需要 root | 非 root 后果 |
|------|----------|-------------|
| `boot_start.sh` | ❌ | agent_ops 跳过，其余正常 |
| `boot_start_loongarch.sh` | ❌ | 正常启动 |
| `bootstrap-kylin-loongarch.sh` | ⚠️ | pip 安装可能失败（缺 gcc/python-dev） |
| `setup_restricted_user.sh` | ✅ 必须 | 直接退出，提示 `sudo` |
| `install_systemd.sh` | ✅ 必须 | systemd 服务无法注册 |
| `package-release.sh` | ❌ | 正常打包 |
| `boot_stop.sh` | ❌ | 正常停止（pkill 无需 root） |

## 六、麒麟 KYSEC 已知兼容问题

| 问题 | 现象 | 解决 |
|------|------|------|
| 端口 8900 无法绑定 | uvicorn 启动失败 | `firewall-cmd --add-port=8900/tcp` |
| OverlayFS 不可用 | 沙箱回退到目录复制模式 | 已内置 fallback，不影响功能 |
| mount namespace 被拦截 | 沙箱隔离降级 | 已内置优雅降级 |
| seccomp 被 KYSEC 覆盖 | 系统调用过滤失效 | 规则引擎 + 注入扫描仍有效 |
| `curl` 未安装 | 健康检查失败 | `dnf install -y curl` |

## 七、答辩演示建议

```
# 最简启动（无需 root，无需 Docker）：
bash boot_start.sh
# → http://<麒麟IP>:8900

# 如需完整安全隔离：
sudo bash scripts/setup_restricted_user.sh  # 仅一次
bash boot_start.sh                           # 日常启动
```
