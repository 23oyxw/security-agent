#!/bin/bash
#===============================================================================
# 安装 LiteLLM + Streamlit systemd 服务（企业级守护进程）
# 用法: sudo bash scripts/install_systemd.sh
#===============================================================================

set -eu

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SYSTEMD_DIR="/etc/systemd/system"

echo "============================================"
echo "  安全运维控制台 — systemd 服务安装"
echo "============================================"
echo "项目路径: ${ROOT}"
echo ""

# 检查 root
if [[ $EUID -ne 0 ]]; then
    echo "❌ 请用 sudo 运行: sudo bash scripts/install_systemd.sh"
    exit 1
fi

# 获取普通用户名（sudo 调用者）
REAL_USER="${SUDO_USER:-$(who am i | awk '{print $1}')}"
REAL_HOME="$(eval echo "~${REAL_USER}" 2>/dev/null || echo "${ROOT}")"

echo "运行用户: ${REAL_USER}"
echo ""

#==============================================================================
# 1. LiteLLM 代理 systemd 服务
#==============================================================================
echo "[1/3] 安装 LiteLLM 代理服务..."

cat > "${SYSTEMD_DIR}/security-litellm.service" << 'SERVICE'
[Unit]
Description=Security Agent — LiteLLM Proxy (模型统一路由网关)
Documentation=https://litellm.vercel.app
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=REAL_USER_PLACEHOLDER
Group=REAL_USER_PLACEHOLDER

# 工作目录
WorkingDirectory=ROOT_PLACEHOLDER

# 启动命令（使用 uv 运行 litellm 代理）
ExecStartPre=/usr/bin/env bash -c 'test -f ROOT_PLACEHOLDER/.venv/bin/python3'
ExecStart=ROOT_PLACEHOLDER/.venv/bin/python3 -m litellm.proxy.proxy_cli \
    --config ROOT_PLACEHOLDER/configs/litellm_config.yaml \
    --port 4000

# 重启策略：总是重启（开机、崩溃、OOM 均自动拉起）
Restart=always
RestartSec=5

# 优雅关闭：SIGTERM → 等待 30s → SIGKILL
TimeoutStopSec=30
KillMode=process
KillSignal=SIGTERM

# 资源限制（防止 OOM 波及系统）
LimitNOFILE=65536
LimitNPROC=1024

# 环境变量
Environment=PYTHONUNBUFFERED=1
Environment=LITELLM_LOG_LEVEL=INFO

# 日志
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SERVICE

sed -i "s|REAL_USER_PLACEHOLDER|${REAL_USER}|g; s|ROOT_PLACEHOLDER|${ROOT}|g" \
    "${SYSTEMD_DIR}/security-litellm.service"

echo "  ✅ security-litellm.service"

#==============================================================================
# 2. 加载并启用服务
#==============================================================================
echo "[2/3] 加载 systemd 配置..."

systemctl daemon-reload
systemctl enable security-litellm.service 2>/dev/null || true

echo "  ✅ systemd 配置已加载"

#==============================================================================
# 3. 日志轮转配置
#==============================================================================
echo "[3/3] 安装日志轮转规则..."

cat > /etc/logrotate.d/security-agent << 'LOGROTATE'
# 安全运维控制台 — 日志轮转
# 按天轮转，保留 30 天，压缩归档

ROOT_PLACEHOLDER/data/logs/litellm.log
ROOT_PLACEHOLDER/data/logs/streamlit.log
{
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
    dateext
    dateformat -%Y%m%d
    maxsize 100M
}
LOGROTATE

sed -i "s|ROOT_PLACEHOLDER|${ROOT}|g" /etc/logrotate.d/security-agent

echo "  ✅ /etc/logrotate.d/security-agent"
echo ""

#==============================================================================
# 完成
#==============================================================================
echo "============================================"
echo "  🎉 安装完成！"
echo "============================================"
echo ""
echo "常用命令："
echo "  启动代理: sudo systemctl start security-litellm"
echo "  停止代理: sudo systemctl stop security-litellm"
echo "  查看状态: sudo systemctl status security-litellm"
echo "  查看日志: sudo journalctl -u security-litellm -f"
echo "  开机自启: sudo systemctl enable security-litellm"
echo ""
echo "  启动控制台: bash ${ROOT}/boot_start.sh"
echo "  停止控制台: bash ${ROOT}/boot_stop.sh"
echo ""

# 询问是否现在启动
read -r -p "是否现在启动 LiteLLM 代理？(Y/n) " answer
if [[ "${answer}" =~ ^[Yy]?$ ]]; then
    echo ""
    systemctl start security-litellm.service
    echo "等待启动..."
    sleep 3
    systemctl status security-litellm.service --no-pager | head -15
    echo ""
    echo "健康检查: curl -s http://localhost:4000/health/readiness"
fi