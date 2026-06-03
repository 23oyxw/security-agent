"""HealthCheck MCP Server — 独立运行的健康巡检服务.

使用方式:
    # stdio 模式（默认，适合本地 Agent 调用）
    python -m security_agent.skills.healthcheck.mcp_server
    
    # HTTP 模式（适合远程部署）
    python -m security_agent.skills.healthcheck.mcp_server --transport http --port 8081
    
    # 查看服务信息
    python -m security_agent.skills.healthcheck.mcp_server --info

工具列表:
    - health_full_check: 全面健康巡检
    - health_trend: 趋势分析
    - health_threshold_check: 阈值检查
    - health_disk_analysis: 磁盘分析
    - health_network_analysis: 网络分析
    - health_get_history: 获取历史数据
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# 确保项目根目录在路径中
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from security_agent.skills.mcp_base import MCPSkillServer, MCPTool
from security_agent.skills.healthcheck.skill import HealthCheckSkill


class HealthCheckMCPServer(MCPSkillServer):
    """健康巡检 MCP 服务.
    
    独立进程运行，通过 MCP 协议暴露 healthcheck 工具集。
    支持 stdio 和 HTTP 两种传输模式。
    """
    
    name = "healthcheck"
    display_name = "健康巡检"
    description = "CPU/内存/磁盘/网络监控，异常告警，趋势分析，定期巡检报告"
    version = "1.0.0"
    port = 8081  # HTTP 模式默认端口
    
    def __init__(self):
        super().__init__()
        # 复用原有 Skill 实例
        self._skill = HealthCheckSkill()
    
    def get_tools(self) -> list[MCPTool]:
        """返回健康巡检工具集."""
        return [
            MCPTool(
                name="health_full_check",
                description="全面健康巡检：CPU/内存/磁盘/网络/负载/运行时间，返回结构化结果与告警",
                parameters={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
                handler=self._tool_full_check,
                requires_confirmation=False,
            ),
            MCPTool(
                name="health_trend",
                description="获取最近健康趋势（CPU/内存/磁盘变化），含趋势方向与预测",
                parameters={
                    "type": "object",
                    "properties": {
                        "metric": {
                            "type": "string",
                            "description": "指标名: cpu|memory|disk|load|all",
                            "default": "all",
                            "enum": ["cpu", "memory", "disk", "load", "all"],
                        },
                        "last_n": {
                            "type": "integer",
                            "description": "取最近 N 个快照（范围：2-120）",
                            "default": 20,
                            "minimum": 2,
                            "maximum": 120,
                        },
                    },
                    "required": [],
                },
                handler=self._tool_trend,
                requires_confirmation=False,
            ),
            MCPTool(
                name="health_threshold_check",
                description="检查当前系统资源是否超过告警阈值，返回超限项列表",
                parameters={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
                handler=self._tool_threshold_check,
                requires_confirmation=False,
            ),
            MCPTool(
                name="health_disk_analysis",
                description="磁盘使用分析：各分区使用率、增长预测、大目录扫描",
                parameters={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
                handler=self._tool_disk_analysis,
                requires_confirmation=False,
            ),
            MCPTool(
                name="health_network_analysis",
                description="网络连接分析：连接数、状态分布、异常外连检测、高危暴露端口检查",
                parameters={
                    "type": "object",
                    "properties": {
                        "check_exposed": {
                            "type": "boolean",
                            "description": "是否检查高危暴露端口（0.0.0.0绑定的风险端口）",
                            "default": True,
                        }
                    },
                    "required": [],
                },
                handler=self._tool_network_analysis,
                requires_confirmation=False,
            ),
            MCPTool(
                name="health_get_history",
                description="获取历史健康快照数据（用于趋势图和报表）",
                parameters={
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "返回最近 N 条记录（范围：1-120）",
                            "default": 60,
                            "minimum": 1,
                            "maximum": 120,
                        }
                    },
                    "required": [],
                },
                handler=self._tool_get_history,
                requires_confirmation=False,
            ),
        ]
    
    # ---- 工具处理器（包装 Skill 方法）----
    
    async def _tool_full_check(self, **kwargs) -> str:
        """全面健康巡检."""
        snap = self._skill.take_snapshot()
        result: dict = {
            "snapshot": snap.to_dict(),
            "status": "告警" if snap.alerts else "正常",
            "alert_count": len(snap.alerts),
        }
        # 附加趋势摘要
        if len(self._skill._history) >= 3:
            for metric in ("cpu", "memory", "disk"):
                trend = self._skill.analyze_trend(metric, last_n=min(20, len(self._skill._history)))
                result[f"{metric}_trend"] = trend.get("trend", "unknown")
        return json.dumps(result, ensure_ascii=False, indent=2)
    
    async def _tool_trend(self, metric: str = "all", last_n: int = 20, **kwargs) -> str:
        """趋势分析."""
        if metric == "all":
            result = {}
            for m in ("cpu", "memory", "disk", "load"):
                result[m] = self._skill.analyze_trend(m, last_n)
            return json.dumps(result, ensure_ascii=False, indent=2)
        return json.dumps(
            self._skill.analyze_trend(metric, last_n),
            ensure_ascii=False, indent=2
        )
    
    async def _tool_threshold_check(self, **kwargs) -> str:
        """阈值检查."""
        snap = self._skill.take_snapshot()
        result = {
            "thresholds": self._skill._thresholds,
            "current": {
                "cpu": snap.cpu_percent,
                "memory": snap.memory_percent,
                "disk": snap.disk_percent,
                "swap": snap.swap_percent,
                "load_ratio": round(snap.load_ratio, 2),
            },
            "alerts": snap.alerts,
            "all_ok": len(snap.alerts) == 0,
        }
        return json.dumps(result, ensure_ascii=False, indent=2)
    
    async def _tool_disk_analysis(self, **kwargs) -> str:
        """磁盘分析."""
        return json.dumps(
            self._skill.disk_analysis(),
            ensure_ascii=False, indent=2
        )
    
    async def _tool_network_analysis(self, check_exposed: bool = True, **kwargs) -> str:
        """网络分析."""
        return json.dumps(
            self._skill.network_analysis(check_exposed),
            ensure_ascii=False, indent=2
        )
    
    async def _tool_get_history(self, limit: int = 60, **kwargs) -> str:
        """获取历史数据."""
        history = list(self._skill._history)[-limit:]
        return json.dumps(
            {
                "count": len(history),
                "snapshots": [s.to_dict() for s in history],
            },
            ensure_ascii=False, indent=2
        )


# ---- 命令行入口 ----

if __name__ == "__main__":
    HealthCheckMCPServer.main()
