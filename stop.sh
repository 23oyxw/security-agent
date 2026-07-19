#!/bin/bash
# 一键停止所有服务
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "${ROOT}/boot_stop.sh"
