"""演练场景定义与合成风险样本."""

from __future__ import annotations

from typing import Any

from security_agent.timeutil import now_iso


LEVEL_SCORE = {"低": 1, "中": 2, "高": 3, "严重": 4, "critical": 4}

SCENARIO_META: dict[str, dict[str, str]] = {
    "synthetic_mixed": {
        "title": "合成多维风险",
        "desc": "不依赖本机进程，注入进程/路径/网络/配置四类样本，用于报告与图表演练",
    },
    "live_decoy_process": {
        "title": "活体诱饵进程",
        "desc": "启动仅 sleep 的 Python 进程，命令行含 nmap/nc 等名称以触发真实扫描",
    },
    "terminal_boundary": {
        "title": "终端规则边界",
        "desc": "批量校验允许/拒绝/需确认/非白名单命令，不执行危险 shell",
    },
    "full_drill": {
        "title": "综合演练",
        "desc": "合成数据 + 边界测试 + 可选诱饵 + 一次真实扫描合并",
    },
    "cpu_stress": {
        "title": "CPU 压测告警演练",
        "desc": "后台 dd 压高 CPU →采集监控告警→自动停止（60s 超时兜底）；需先「启动监控」",
    },
    "fixture_calibration": {
        "title": "检测规则校准（66 用例）",
        "desc": "日常开发/易误报/攻击样本批量校验，输出准确率/误报/漏报",
    },
}


def synthetic_risks() -> list[dict[str, Any]]:
    ts = now_iso()
    return [
        {
            "type": "高危进程",
            "pid": 90001,
            "name": "demo-nmap",
            "username": "demo",
            "cmdline": "python decoy.py --hold --simulate-tool nmap",
            "message": "[演练] 命令行包含高危工具: nmap",
            "level": "严重",
            "source": "synthetic",
            "layer": "检测",
            "scenario": "synthetic_mixed",
            "scored_at": ts,
        },
        {
            "type": "权限异常",
            "path": "/data/demo/mock_shadow",
            "message": "[演练] 敏感路径可写（模拟）",
            "level": "高",
            "source": "synthetic",
            "layer": "检测",
            "scenario": "synthetic_mixed",
            "scored_at": ts,
        },
        {
            "type": "异常连接",
            "local": "10.0.0.5:4444",
            "remote": "203.0.113.9:443",
            "message": "[演练] 非常规外连端口",
            "level": "中",
            "source": "synthetic",
            "layer": "检测",
            "scenario": "synthetic_mixed",
            "scored_at": ts,
        },
        {
            "type": "配置风险",
            "path": "/etc/demo-weak-perm",
            "message": "[演练] 弱权限配置项",
            "level": "中",
            "source": "synthetic",
            "layer": "规则",
            "scenario": "synthetic_mixed",
            "scored_at": ts,
        },
        {
            "type": "策略告警",
            "message": "[演练] 自动拦截已禁用，需人工确认",
            "level": "低",
            "source": "synthetic",
            "layer": "响应",
            "scenario": "synthetic_mixed",
            "scored_at": ts,
        },
        # CPU 压测相关告警（仅 cpu_stress 场景注入，这里作为合成数据补充）
        {
            "type": "CPU 告警",
            "pid": 0,
            "name": "dd-stress",
            "message": "[演练] CPU 占用过高 94% (阈值 80%)",
            "level": "高",
            "source": "synthetic",
            "layer": "监控",
            "scenario": "cpu_stress",
            "scored_at": ts,
        },
        {
            "type": "CPU 告警",
            "pid": 0,
            "name": "dd-stress",
            "message": "[演练] CPU 持续高于阈值: 91% (已持续 15s)",
            "level": "中",
            "source": "synthetic",
            "layer": "监控",
            "scenario": "cpu_stress",
            "scored_at": ts,
        },
    ]


def risks_to_cube_points(risks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """将风险转为可视化用的三维点（类型轴 / 等级轴 / 来源轴）."""
    type_map = {"高危进程": 0, "权限异常": 1, "异常连接": 2, "配置风险": 3, "策略告警": 4}
    source_map = {"live": 0, "synthetic": 1, "decoy": 2}
    layer_map = {"检测": 0, "规则": 1, "响应": 2}
    points: list[dict[str, Any]] = []
    for i, r in enumerate(risks):
        lvl = r.get("level", "中")
        points.append(
            {
                "id": i,
                "label": r.get("name") or r.get("path") or r.get("type", "?"),
                "type": r.get("type", ""),
                "level": lvl,
                "severity": LEVEL_SCORE.get(lvl, 2),
                "x_type": type_map.get(r.get("type", ""), 2),
                "y_severity": LEVEL_SCORE.get(lvl, 2),
                "z_source": source_map.get(r.get("source", "live"), 0),
                "layer": r.get("layer", "检测"),
                "z_layer": layer_map.get(r.get("layer", "检测"), 0),
                "source": r.get("source", "live"),
            }
        )
    return points
