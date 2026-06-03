#!/bin/bash
# 创建受限用户 agent_ops 用于权限隔离
# 遵循A2赛题要求：核心操作在受限账户下运行

set -e

# 颜色输出
RED='[0;31m'
GREEN='[0;32m'
YELLOW='[1;33m'
NC='[0m' # No Color

echo -e "${GREEN}[INFO]${NC} 创建安全运维代理受限用户"

# 检查是否以root运行
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}[ERROR]${NC} 请以root权限运行此脚本"
    echo "使用: sudo $0"
    exit 1
fi

# 用户名和组名
USERNAME="agent_ops"
GROUPNAME="agent_ops"

# 1. 创建用户组（如果不存在）
if ! getent group "$GROUPNAME" > /dev/null 2>&1; then
    echo -e "${YELLOW}[STEP 1]${NC} 创建用户组: $GROUPNAME"
    groupadd "$GROUPNAME"
    echo -e "${GREEN}  ✓${NC} 组创建成功"
else
    echo -e "${GREEN}  ✓${NC} 组已存在"
fi

# 2. 创建用户（如果不存在）
if ! id "$USERNAME" > /dev/null 2>&1; then
    echo -e "${YELLOW}[STEP 2]${NC} 创建受限用户: $USERNAME"
    
    # 创建系统用户，无主目录，无登录shell
    useradd -r -g "$GROUPNAME" -s /bin/false -M "$USERNAME"
    
    echo -e "${GREEN}  ✓${NC} 用户创建成功"
else
    echo -e "${GREEN}  ✓${NC} 用户已存在"
fi

# 3. 设置用户权限
echo -e "${YELLOW}[STEP 3]${NC} 配置用户权限"

# 允许sudo执行特定命令（如果需要）
# 注意：A2赛题要求最小权限原则，尽量避免sudo
# 如果确实需要，可以添加特定命令的sudo权限
# echo "$USERNAME ALL=(ALL) NOPASSWD: /usr/bin/cat, /usr/bin/ls" >> /etc/sudoers.d/agent_ops

# 4. 设置目录权限
echo -e "${YELLOW}[STEP 4]${NC} 设置目录权限"

# 创建日志目录
LOG_DIR="/var/log/security_agent"
if [ ! -d "$LOG_DIR" ]; then
    mkdir -p "$LOG_DIR"
    echo -e "${GREEN}  ✓${NC} 创建日志目录: $LOG_DIR"
fi

# 设置日志目录权限
chown "$USERNAME:$GROUPNAME" "$LOG_DIR"
chmod 750 "$LOG_DIR"
echo -e "${GREEN}  ✓${NC} 设置日志目录权限"

# 创建临时目录
TEMP_DIR="/tmp/security_agent"
if [ ! -d "$TEMP_DIR" ]; then
    mkdir -p "$TEMP_DIR"
    echo -e "${GREEN}  ✓${NC} 创建临时目录: $TEMP_DIR"
fi

# 设置临时目录权限
chown "$USERNAME:$GROUPNAME" "$TEMP_DIR"
chmod 750 "$TEMP_DIR"
echo -e "${GREEN}  ✓${NC} 设置临时目录权限"

# 5. 创建配置目录
CONFIG_DIR="/etc/security_agent"
if [ ! -d "$CONFIG_DIR" ]; then
    mkdir -p "$CONFIG_DIR"
    echo -e "${GREEN}  ✓${NC} 创建配置目录: $CONFIG_DIR"
fi

# 设置配置目录权限（只读）
chown root:"$GROUPNAME" "$CONFIG_DIR"
chmod 750 "$CONFIG_DIR"
echo -e "${GREEN}  ✓${NC} 设置配置目录权限"

# 6. 显示用户信息
echo -e "${YELLOW}[STEP 5]${NC} 用户信息"
echo "用户名: $USERNAME"
echo "用户ID: $(id -u $USERNAME)"
echo "组ID: $(id -g $USERNAME)"
echo "主目录: $(eval echo ~$USERNAME)"
echo "Shell: $(getent passwd $USERNAME | cut -d: -f7)"

# 7. 验证权限
echo -e "${YELLOW}[STEP 6]${NC} 验证权限"

# 检查用户是否能访问日志目录
if sudo -u "$USERNAME" test -r "$LOG_DIR"; then
    echo -e "${GREEN}  ✓${NC} 用户可以读取日志目录"
else
    echo -e "${RED}  ✗${NC} 用户无法读取日志目录"
fi

# 检查用户是否能写入日志目录
if sudo -u "$USERNAME" test -w "$LOG_DIR"; then
    echo -e "${GREEN}  ✓${NC} 用户可以写入日志目录"
else
    echo -e "${RED}  ✗${NC} 用户无法写入日志目录"
fi

echo -e "${GREEN}[SUCCESS]${NC} 受限用户 $USERNAME 创建完成"
echo ""
echo "下一步操作:"
echo "1. 更新 security_agent/terminal/privilege.py 中的 DEFAULT_RESTRICTED_USER"
echo "2. 运行测试验证权限隔离: uv run python scripts/smoke_test.py"
echo "3. 查看系统状态: id $USERNAME"
