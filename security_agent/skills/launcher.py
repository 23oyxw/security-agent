"""MCP Skill Launcher — 统一管理所有 Skill MCP 服务.

使用方式:
    # 启动单个 MCP 服务
    python -m security_agent.skills.launcher healthcheck
    python -m security_agent.skills.launcher log_analyzer --transport http --port 8082
    
    # 查看所有服务信息
    python -m security_agent.skills.launcher --list
    
    # 启动所有服务（HTTP模式）
    python -m security_agent.skills.launcher --all --transport http
    
    # 后台运行所有服务
    python -m security_agent.skills.launcher --all --daemon

支持的服务:
    - healthcheck    : 健康巡检 (默认端口 8081)
    - log_analyzer   : 日志分析 (默认端口 8082)
    - config_manager : 配置管理 (默认端口 8083)
    - security_hardening : 安全加固 (默认端口 8084)
    - incident_responder : 故障响应 (默认端口 8085)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# 服务注册表
SERVICES = {
    "healthcheck": {
        "name": "健康巡检",
        "module": "security_agent.skills.healthcheck.mcp_server",
        "default_port": 8081,
    },
    "log_analyzer": {
        "name": "日志分析",
        "module": "security_agent.skills.log_analyzer.mcp_server",
        "default_port": 8082,
    },
    "config_manager": {
        "name": "配置管理",
        "module": "security_agent.skills.config_manager.mcp_server",
        "default_port": 8083,
    },
    "security_hardening": {
        "name": "安全加固",
        "module": "security_agent.skills.security_hardening.mcp_server",
        "default_port": 8084,
    },
    "incident_responder": {
        "name": "故障响应",
        "module": "security_agent.skills.incident_responder.mcp_server",
        "default_port": 8085,
    },
}


def list_services():
    """列出所有可用的 MCP 服务."""
    print("\n可用 MCP 服务列表:")
    print("-" * 60)
    for key, info in SERVICES.items():
        print(f"  {key:20} : {info['name']} (默认端口 {info['default_port']})")
    print("-" * 60)
    print(f"\n共 {len(SERVICES)} 个服务")
    print("\n查看单个服务信息:")
    print(f"  python -m security_agent.skills.launcher healthcheck --info")


def start_service(
    name: str,
    transport: str = "stdio",
    host: str = "127.0.0.1",
    port: int | None = None,
) -> int:
    """启动单个 MCP 服务."""
    if name not in SERVICES:
        print(f"错误: 未知服务 '{name}'")
        print(f"可用服务: {', '.join(SERVICES.keys())}")
        return 1
    
    info = SERVICES[name]
    port = port or info["default_port"]
    
    # 构建启动命令
    cmd = [
        sys.executable,
        "-m",
        info["module"].replace(".", ".")[15:],  # 简化为 launcher.xxx 形式
    ]
    
    # 直接使用模块路径
    cmd = [sys.executable, "-m", info["module"]]
    
    if transport != "stdio":
        cmd.extend(["--transport", transport])
        cmd.extend(["--host", host])
        cmd.extend(["--port", str(port)])
    
    print(f"启动 {info['name']} ({transport} 模式)...")
    if transport == "http":
        print(f"  地址: http://{host}:{port}")
    
    try:
        result = subprocess.run(cmd)
        return result.returncode
    except KeyboardInterrupt:
        print(f"\n{info['name']} 已停止")
        return 0


def start_all(transport: str = "http", host: str = "127.0.0.1"):
    """后台启动所有服务（仅支持HTTP模式）."""
    if transport != "http":
        print("错误: --all 模式仅支持 HTTP 传输")
        return 1
    
    print("后台启动所有 MCP 服务...")
    processes = []
    
    for name, info in SERVICES.items():
        port = info["default_port"]
        cmd = [
            sys.executable,
            "-m",
            info["module"],
            "--transport", "http",
            "--host", host,
            "--port", str(port),
        ]
        
        print(f"  {info['name']}: http://{host}:{port}")
        
        # 后台启动
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        processes.append((name, proc))
    
    print(f"\n共启动 {len(processes)} 个服务")
    print("查看状态: curl http://127.0.0.1:8081/info")
    print("停止所有: pkill -f 'mcp_server'")
    
    return 0


def main():
    """命令行入口."""
    parser = argparse.ArgumentParser(
        description="MCP Skill Launcher - 统一管理 Skill MCP 服务",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s healthcheck                    # stdio 模式运行健康巡检
  %(prog)s healthcheck --info             # 查看服务信息
  %(prog)s healthcheck -t http -p 9001    # HTTP模式，自定义端口
  %(prog)s --list                         # 列出所有服务
  %(prog)s --all                          # 后台启动所有服务（HTTP）
        """,
    )
    
    parser.add_argument(
        "service",
        nargs="?",
        choices=list(SERVICES.keys()),
        help="要启动的服务名称",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="列出所有可用服务",
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="后台启动所有服务（HTTP模式）",
    )
    parser.add_argument(
        "--transport", "-t",
        choices=["stdio", "http"],
        default="stdio",
        help="传输模式 (默认: stdio)",
    )
    parser.add_argument(
        "--host", "-H",
        default="127.0.0.1",
        help="HTTP模式主机 (默认: 127.0.0.1)",
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=None,
        help="HTTP模式端口 (默认: 服务预设)",
    )
    parser.add_argument(
        "--info", "-i",
        action="store_true",
        help="查看服务信息（不启动服务）",
    )
    
    args = parser.parse_args()
    
    if args.list:
        list_services()
        return 0
    
    if args.all:
        return start_all(args.transport, args.host)
    
    if not args.service:
        parser.print_help()
        print("\n错误: 请指定服务名称或使用 --list/--all")
        return 1
    
    # 获取服务信息
    info = SERVICES[args.service]
    
    if args.info:
        # 查看服务信息
        cmd = [sys.executable, "-m", info["module"], "--info"]
        return subprocess.run(cmd).returncode
    
    # 启动服务
    return start_service(
        args.service,
        transport=args.transport,
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    sys.exit(main())
