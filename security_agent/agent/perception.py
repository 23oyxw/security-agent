"""环境感知层 - 自动采集系统上下文"""

from __future__ import annotations

import json
import os
import subprocess
import time
import psutil
from datetime import datetime
from typing import Any, Dict, List, Optional


class EnvironmentProbe:
    """自动采集OS状态摘要，注入到LLM上下文"""
    
    def __init__(self, include_kylin_specific: bool = True):
        """
        初始化环境探测器
        
        Args:
            include_kylin_specific: 是否包含银河麒麟特有工具信息
        """
        self.include_kylin = include_kylin_specific
        
    def probe(self) -> str:
        """采集并格式化为LLM可读的上下文"""
        try:
            context = {
                "timestamp": datetime.now().isoformat(),
                "system": self._get_system_summary(),
                "resources": self._get_resource_usage(),
                "processes": self._get_top_processes(),
                "network": self._get_network_info(),
                "security": self._get_security_info(),
            }
            
            # 转换为可读的markdown格式
            return self._format_context(context)
        except Exception as e:
            return f"## 环境感知错误\n无法采集系统信息: {str(e)}"
    
    def _get_system_summary(self) -> Dict[str, Any]:
        """获取系统基本信息"""
        try:
            uname = os.uname()
            return {
                "hostname": uname.nodename,
                "os": uname.sysname,
                "kernel": uname.release,
                "arch": uname.machine,
                "python_version": subprocess.check_output(
                    ["python3", "--version"], text=True
                ).strip(),
            }
        except Exception:
            return {"error": "无法获取系统信息"}
    
    def _get_resource_usage(self) -> Dict[str, Any]:
        """获取资源使用情况"""
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            cpu_logical = psutil.cpu_count(logical=True)
            
            # 内存使用情况
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            # 磁盘使用情况
            disk_usage = {}
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    disk_usage[partition.mountpoint] = {
                        "total_gb": round(usage.total / (1024**3), 1),
                        "used_gb": round(usage.used / (1024**3), 1),
                        "free_gb": round(usage.free / (1024**3), 1),
                        "percent": usage.percent,
                    }
                except (PermissionError, OSError):
                    continue
            
            return {
                "cpu": {
                    "percent": cpu_percent,
                    "cores_physical": cpu_count,
                    "cores_logical": cpu_logical,
                },
                "memory": {
                    "total_gb": round(memory.total / (1024**3), 1),
                    "used_gb": round(memory.used / (1024**3), 1),
                    "available_gb": round(memory.available / (1024**3), 1),
                    "percent": memory.percent,
                },
                "swap": {
                    "total_gb": round(swap.total / (1024**3), 1),
                    "used_gb": round(swap.used / (1024**3), 1),
                    "percent": swap.percent,
                },
                "disk": disk_usage,
            }
        except Exception as e:
            return {"error": f"资源信息采集失败: {str(e)}"}
    
    def _get_top_processes(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取占用CPU最高的进程"""
        try:
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'username', 'status']):
                try:
                    pinfo = proc.info
                    if pinfo['cpu_percent'] is None:
                        continue
                    processes.append({
                        "pid": pinfo['pid'],
                        "name": pinfo['name'],
                        "cpu_percent": pinfo['cpu_percent'],
                        "memory_percent": pinfo['memory_percent'] or 0.0,
                        "username": pinfo['username'] or "unknown",
                        "status": pinfo['status'],
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # 按CPU使用率排序
            processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
            return processes[:limit]
        except Exception as e:
            return [{"error": f"进程信息采集失败: {str(e)}"}]
    
    def _get_network_info(self) -> Dict[str, Any]:
        """获取网络信息"""
        try:
            # 监听端口
            listening_ports = []
            connections = psutil.net_connections(kind='inet')
            for conn in connections:
                if conn.status == 'LISTEN':
                    listening_ports.append({
                        "port": conn.laddr.port,
                        "ip": conn.laddr.ip,
                        "pid": conn.pid,
                        "status": conn.status,
                    })
            
            # 网络接口
            interfaces = {}
            net_if_addrs = psutil.net_if_addrs()
            net_if_stats = psutil.net_if_stats()
            
            for iface, addrs in net_if_addrs.items():
                if iface in net_if_stats:
                    stats = net_if_stats[iface]
                    interfaces[iface] = {
                        "is_up": stats.isup,
                        "speed_mbps": stats.speed,
                        "mtu": stats.mtu,
                    }
            
            return {
                "listening_ports": listening_ports,
                "interfaces": interfaces,
                "connections_count": len(connections),
            }
        except Exception as e:
            return {"error": f"网络信息采集失败: {str(e)}"}
    
    def _get_security_info(self) -> Dict[str, Any]:
        """获取安全相关信息"""
        security_info = {
            "users": [],
            "ssh_sessions": 0,
            "kylin_security": None,
        }
        
        try:
            # 获取登录用户
            users = psutil.users()
            security_info["users"] = [
                {"name": u.name, "terminal": u.terminal, "host": u.host, "started": u.started}
                for u in users
            ]
            
            # 尝试获取SSH会话数量
            try:
                result = subprocess.run(
                    ["who", "-q"],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    if len(lines) > 1:
                        # 第二行是用户计数
                        count_line = lines[1].strip()
                        if '#' in count_line:
                            security_info["ssh_sessions"] = int(count_line.split('#')[1].strip())
            except Exception:
                pass
            
            # 麒麟特有安全工具
            if self.include_kylin:
                try:
                    # 检查kysec是否存在
                    kysec_result = subprocess.run(
                        ["which", "kysec"],
                        capture_output=True,
                        text=True,
                        timeout=2
                    )
                    if kysec_result.returncode == 0:
                        # 尝试获取kysec状态
                        kysec_status = subprocess.run(
                            ["kysec", "status"],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        if kysec_status.returncode == 0:
                            security_info["kylin_security"] = {
                                "kysec_available": True,
                                "status_output": kysec_status.stdout[:500],  # 限制长度
                            }
                except Exception:
                    security_info["kylin_security"] = {"kysec_available": False}
            
        except Exception as e:
            security_info["error"] = f"安全信息采集失败: {str(e)}"
        
        return security_info
    
    def _format_context(self, context: Dict[str, Any]) -> str:
        """将上下文格式化为可读的markdown格式"""
        try:
            lines = []
            lines.append(f"## 系统状态（自动采集 {context['timestamp']}）")
            
            # 系统信息
            system = context.get('system', {})
            if 'error' not in system:
                lines.append(f"### 系统信息")
                lines.append(f"- 主机名: {system.get('hostname', 'N/A')}")
                lines.append(f"- 操作系统: {system.get('os', 'N/A')}")
                lines.append(f"- 内核版本: {system.get('kernel', 'N/A')}")
                lines.append(f"- 架构: {system.get('arch', 'N/A')}")
            
            # 资源使用
            resources = context.get('resources', {})
            if 'error' not in resources:
                lines.append(f"### 资源使用")
                
                cpu = resources.get('cpu', {})
                lines.append(f"**CPU**: {cpu.get('percent', 0)}% ({cpu.get('cores_physical', 0)}物理核, {cpu.get('cores_logical', 0)}逻辑核)")
                
                memory = resources.get('memory', {})
                lines.append(f"**内存**: {memory.get('used_gb', 0)}/{memory.get('total_gb', 0)} GB ({memory.get('percent', 0)}%)")
                
                swap = resources.get('swap', {})
                if swap.get('total_gb', 0) > 0:
                    lines.append(f"**交换空间**: {swap.get('used_gb', 0)}/{swap.get('total_gb', 0)} GB ({swap.get('percent', 0)}%)")
                
                # 磁盘使用
                disk = resources.get('disk', {})
                if disk:
                    lines.append("**磁盘使用**:")
                    for mount, info in disk.items():
                        if mount in ['/', '/home', '/var', '/tmp']:  # 只显示重要挂载点
                            lines.append(f"  - {mount}: {info.get('used_gb', 0)}/{info.get('total_gb', 0)} GB ({info.get('percent', 0)}%)")
            
            # 关键进程
            processes = context.get('processes', [])
            if processes and 'error' not in processes[0]:
                lines.append(f"### 关键进程 (Top 5 by CPU)")
                for i, proc in enumerate(processes[:5], 1):
                    if 'error' not in proc:
                        lines.append(f"{i}. **{proc['name']}** (PID: {proc['pid']}): CPU {proc['cpu_percent']}%, 内存 {proc['memory_percent']:.1f}%")
            
            # 网络信息
            network = context.get('network', {})
            if 'error' not in network:
                lines.append(f"### 网络信息")
                listening_ports = network.get('listening_ports', [])
                if listening_ports:
                    lines.append("**监听端口**:")
                    for port_info in listening_ports[:10]:  # 只显示前10个
                        lines.append(f"  - 端口 {port_info['port']} ({port_info['ip']})")
                
                lines.append(f"总连接数: {network.get('connections_count', 0)}")
            
            # 安全信息
            security = context.get('security', {})
            if 'error' not in security:
                lines.append(f"### 安全信息")
                users = security.get('users', [])
                if users:
                    lines.append("**当前登录用户**:")
                    for user in users:
                        lines.append(f"  - {user['name']} (终端: {user['terminal']})")
                
                ssh_sessions = security.get('ssh_sessions', 0)
                if ssh_sessions > 0:
                    lines.append(f"SSH会话数: {ssh_sessions}")
                
                # 麒麟安全
                kylin_sec = security.get('kylin_security')
                if kylin_sec and kylin_sec.get('kysec_available'):
                    lines.append(f"**麒麟安全框架**: kysec可用")
            
            return "\n".join(lines)
            
        except Exception as e:
            return f"## 系统状态（格式化错误）\n{str(e)}"


# 单例实例
_probe_instance: Optional[EnvironmentProbe] = None


def get_environment_probe() -> EnvironmentProbe:
    """获取全局环境探测器单例"""
    global _probe_instance
    if _probe_instance is None:
        _probe_instance = EnvironmentProbe()
    return _probe_instance


def get_system_context() -> str:
    """获取系统上下文的便捷函数"""
    probe = get_environment_probe()
    return probe.probe()


def get_proactive_snapshot() -> Dict[str, Any]:
    """主动感知快照（结构化 JSON，供 API / Agent 注入）."""
    probe = get_environment_probe()
    try:
        ctx = {
            "timestamp": time.time(),
            "hostname": os.uname().nodename,
            "resources": probe._get_resource_usage(),
            "top_processes": probe._get_top_processes()[:5],
            "security": probe._get_security_info(),
        }
        resources = ctx.get("resources") or {}
        cpu = (resources.get("cpu") or {}).get("percent", 0)
        mem = (resources.get("memory") or {}).get("percent", 0)
        ctx["summary"] = {
            "cpu_percent": cpu,
            "memory_percent": mem,
            "alert_hint": "high_load" if cpu > 85 or mem > 90 else "normal",
        }
        return ctx
    except Exception as exc:
        return {"timestamp": time.time(), "error": str(exc), "summary": {"alert_hint": "unknown"}}
