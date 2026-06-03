"""追踪可视化模块 - 提供交互式追踪链路分析"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TraceNode:
    """追踪节点"""
    node_id: str
    name: str
    type: str  # start, stage, tool, decision, end
    timestamp: str
    duration_ms: float = 0.0
    status: str = "success"  # success, error, pending
    details: Dict[str, Any] = field(default_factory=dict)
    parent_id: Optional[str] = None
    children_ids: List[str] = field(default_factory=list)


@dataclass
class TraceLink:
    """追踪连接"""
    from_node: str
    to_node: str
    label: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TraceVisualization:
    """追踪可视化数据"""
    trace_id: str
    nodes: List[TraceNode]
    links: List[TraceLink]
    summary: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "nodes": [
                {
                    "node_id": node.node_id,
                    "name": node.name,
                    "type": node.type,
                    "timestamp": node.timestamp,
                    "duration_ms": node.duration_ms,
                    "status": node.status,
                    "details": node.details,
                    "parent_id": node.parent_id,
                    "children_ids": node.children_ids
                }
                for node in self.nodes
            ],
            "links": [
                {
                    "from": link.from_node,
                    "to": link.to_node,
                    "label": link.label,
                    "details": link.details
                }
                for link in self.links
            ],
            "summary": self.summary,
            "metadata": self.metadata
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


class TraceVisualizer:
    """追踪可视化器"""
    
    def __init__(self, db_path: str = "data/traces.db"):
        """
        初始化追踪可视化器
        
        Args:
            db_path: SQLite数据库路径
        """
        self.db_path = Path(db_path)
    
    def get_trace_visualization(self, trace_id: str) -> Optional[TraceVisualization]:
        """获取追踪可视化数据"""
        if not self.db_path.exists():
            return None
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # 获取追踪信息
            cursor = conn.execute(
                "SELECT * FROM traces WHERE trace_id = ?",
                (trace_id,)
            )
            trace_row = cursor.fetchone()
            
            if not trace_row:
                return None
            
            # 构建节点和连接
            nodes = []
            links = []
            
            # 开始节点
            start_node = TraceNode(
                node_id=f"{trace_id}_start",
                name="开始",
                type="start",
                timestamp=trace_row[2],  # started_at
                status="success"
            )
            nodes.append(start_node)
            
            # 获取阶段信息
            cursor.execute(
                "SELECT * FROM stages WHERE trace_id = ? ORDER BY timestamp",
                (trace_id,)
            )
            stage_rows = cursor.fetchall()
            
            previous_node_id = start_node.node_id
            
            for stage_row in stage_rows:
                # 阶段节点
                stage_node = TraceNode(
                    node_id=f"{trace_id}_stage_{stage_row[1]}",
                    name=stage_row[2],  # stage_name
                    type="stage",
                    timestamp=stage_row[3],  # timestamp
                    duration_ms=stage_row[4] or 0.0,  # duration_ms
                    status="success" if stage_row[6] is None else "error",  # error
                    details=json.loads(stage_row[5]) if stage_row[5] else {}  # details
                )
                nodes.append(stage_node)
                
                # 添加连接
                link = TraceLink(
                    from_node=previous_node_id,
                    to_node=stage_node.node_id,
                    label=stage_node.name,
                    details={"duration_ms": stage_node.duration_ms}
                )
                links.append(link)
                
                previous_node_id = stage_node.node_id
            
            # 获取工具调用信息
            cursor.execute(
                "SELECT * FROM tool_calls WHERE trace_id = ? ORDER BY timestamp",
                (trace_id,)
            )
            tool_rows = cursor.fetchall()
            
            for tool_row in tool_rows:
                # 工具节点
                tool_node = TraceNode(
                    node_id=f"{trace_id}_tool_{tool_row[1]}",
                    name=tool_row[2],  # tool_name
                    type="tool",
                    timestamp=tool_row[3],  # timestamp
                    duration_ms=tool_row[4] or 0.0,  # duration_ms
                    status="success" if tool_row[6] == 0 else "error",  # error
                    details={
                        "arguments": json.loads(tool_row[5]) if tool_row[5] else {},
                        "result_preview": (tool_row[7][:100] + "...") if tool_row[7] and len(tool_row[7]) > 100 else tool_row[7]
                    }
                )
                nodes.append(tool_node)
                
                # 添加连接
                link = TraceLink(
                    from_node=previous_node_id,
                    to_node=tool_node.node_id,
                    label=f"执行: {tool_node.name}",
                    details={"duration_ms": tool_node.duration_ms}
                )
                links.append(link)
            
            # 结束节点
            end_node = TraceNode(
                node_id=f"{trace_id}_end",
                name="结束",
                type="end",
                timestamp=trace_row[3],  # completed_at or now
                status="success"
            )
            nodes.append(end_node)
            
            # 添加到结束节点的连接
            if previous_node_id != start_node.node_id:
                link = TraceLink(
                    from_node=previous_node_id,
                    to_node=end_node.node_id,
                    label="完成",
                    details={}
                )
                links.append(link)
            
            # 计算摘要
            total_duration = 0.0
            stage_count = 0
            tool_count = 0
            
            for node in nodes:
                if node.type == "stage":
                    total_duration += node.duration_ms
                    stage_count += 1
                elif node.type == "tool":
                    total_duration += node.duration_ms
                    tool_count += 1
            
            summary = {
                "total_duration_ms": total_duration,
                "stage_count": stage_count,
                "tool_count": tool_count,
                "node_count": len(nodes),
                "link_count": len(links),
                "start_time": start_node.timestamp,
                "end_time": end_node.timestamp,
                "status": "success" if all(n.status == "success" for n in nodes) else "partial_error"
            }
            
            metadata = {
                "user_message": trace_row[4],  # user_message
                "user": trace_row[5],  # user
                "created_at": trace_row[6]  # created_at
            }
            
            return TraceVisualization(
                trace_id=trace_id,
                nodes=nodes,
                links=links,
                summary=summary,
                metadata=metadata
            )
    
    def list_traces(self, limit: int = 50, status: str = None) -> List[Dict[str, Any]]:
        """列出追踪"""
        if not self.db_path.exists():
            return []
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            query = "SELECT * FROM traces"
            params = []
            
            if status:
                query += " WHERE status = ?"
                params.append(status)
            
            query += " ORDER BY started_at DESC LIMIT ?"
            params.append(limit)
            
            cursor = conn.execute(query, params)
            
            traces = []
            for row in cursor.fetchall():
                traces.append({
                    "trace_id": row[1],
                    "user_message": row[4],
                    "user": row[5],
                    "started_at": row[2],
                    "completed_at": row[3],
                    "status": row[7] if len(row) > 7 else "unknown"
                })
            
            return traces
    
    def get_trace_statistics(self, days: int = 7) -> Dict[str, Any]:
        """获取追踪统计"""
        if not self.db_path.exists():
            return {}
        
        with sqlite3.connect(self.db_path) as conn:
            # 总追踪数
            cursor = conn.execute("SELECT COUNT(*) FROM traces")
            total_traces = cursor.fetchone()[0]
            
            # 最近N天的追踪数
            cursor.execute(
                """SELECT COUNT(*) FROM traces 
                   WHERE started_at >= datetime('now', ?)""",
                (f'-{days} days',)
            )
            recent_traces = cursor.fetchone()[0]
            
            # 平均持续时间
            cursor.execute(
                """SELECT AVG(JULIANDAY(completed_at) - JULIANDAY(started_at)) * 24 * 60 * 60 * 1000 
                   FROM traces 
                   WHERE completed_at IS NOT NULL"""
            )
            avg_duration = cursor.fetchone()[0] or 0.0
            
            # 阶段统计
            cursor.execute("SELECT COUNT(*) FROM stages")
            total_stages = cursor.fetchone()[0]
            
            # 工具调用统计
            cursor.execute("SELECT COUNT(*) FROM tool_calls")
            total_tool_calls = cursor.fetchone()[0]
            
            return {
                "total_traces": total_traces,
                "recent_traces": recent_traces,
                "avg_duration_ms": round(avg_duration, 2),
                "total_stages": total_stages,
                "total_tool_calls": total_tool_calls,
                "period_days": days
            }
    
    def generate_mermaid_diagram(self, trace_id: str) -> str:
        """生成Mermaid图表"""
        visualization = self.get_trace_visualization(trace_id)
        if not visualization:
            return ""
        
        lines = ["graph TD"]
        
        # 添加节点
        for node in visualization.nodes:
            if node.type == "start":
                lines.append(f'    {node.node_id}["开始"]')
            elif node.type == "end":
                lines.append(f'    {node.node_id}["结束"]')
            elif node.type == "stage":
                color = "green" if node.status == "success" else "red"
                lines.append(f'    {node.node_id}["{node.name}<br/>{node.duration_ms:.1f}ms"]')
            elif node.type == "tool":
                color = "blue" if node.status == "success" else "red"
                lines.append(f'    {node.node_id}["{node.name}<br/>工具调用"]')
        
        lines.append("")
        
        # 添加连接
        for link in visualization.links:
            if link.label:
                lines.append(f'    {link.from_node} -->|{link.label}| {link.to_node}')
            else:
                lines.append(f'    {link.from_node} --> {link.to_node}')
        
        return "\n".join(lines)


# 全局单例
_trace_visualizer_instance: Optional[TraceVisualizer] = None


def get_trace_visualizer() -> TraceVisualizer:
    """获取全局追踪可视化器实例"""
    global _trace_visualizer_instance
    if _trace_visualizer_instance is None:
        _trace_visualizer_instance = TraceVisualizer()
    return _trace_visualizer_instance
