#!/usr/bin/env bash
#==============================================================================
# 安装/更新桌面快捷方式 — 统一入口
# 用法: bash scripts/install_desktop_shortcuts.sh
#==============================================================================
set -eu

SEC_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DESKTOP_DIR="${HOME}/桌面"

# 如果桌面目录不存在（英文环境），尝试常见路径
if [[ ! -d "${DESKTOP_DIR}" ]]; then
  DESKTOP_DIR="${HOME}/Desktop"
fi
if [[ ! -d "${DESKTOP_DIR}" ]]; then
  echo "[install] 桌面目录不存在: ${HOME}/桌面 或 ${HOME}/Desktop" >&2
  exit 1
fi

echo ""
echo "  🛡️  安装桌面快捷方式"
echo "  ================================="
echo "  项目目录: ${SEC_ROOT}"
echo "  桌面目录: ${DESKTOP_DIR}"
echo ""

# 1. 复制 .desktop 文件
for f in "${SEC_ROOT}"/configs/*.desktop; do
  [[ -f "$f" ]] || continue
  name="$(basename "$f")"
  cp "$f" "${DESKTOP_DIR}/${name}"
  chmod +x "${DESKTOP_DIR}/${name}"
  echo "  ✅ 已安装: ${name}"
done

# 2. 移除旧的安全运维控制台.sh（已被 打开应用.sh 取代）
if [[ -f "${DESKTOP_DIR}/安全运维控制台.sh" ]]; then
  rm -f "${DESKTOP_DIR}/安全运维控制台.sh"
  echo "  🗑️  已移除旧入口: 安全运维控制台.sh（统一为 打开应用.sh）"
fi

# 3. 确保 .desktop 文件可执行（麒麟桌面需要）
if command -v gio &>/dev/null; then
  for f in "${DESKTOP_DIR}"/*.desktop; do
    [[ -f "$f" ]] && gio set "$f" metadata::trusted true 2>/dev/null || true
  done
fi

echo ""
echo "  ================================="
echo "  ✅ 桌面快捷方式已更新"
echo "  双击桌面上的「安全运维控制台」即可启动"
echo "  ================================="
echo ""