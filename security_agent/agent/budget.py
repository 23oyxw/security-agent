"""Budget Agent — 批量/高频任务专用，使用性价比模型 (DeepSeek V4 Flash).

适用场景：
- 批量报告生成与总结
- 高频日志分析
- 大量数据的模式识别
- 测试用例生成
- 文档批量处理
"""

from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from security_agent import config


class BudgetAgent:
    """使用 BUDGET_MODEL (deepseek-v4-flash) 的轻量 Agent.

    特点：
    - 成本低廉，适合高频/批量任务
    - 响应速度快
    - 不支持复杂工具调用，主要用于总结、分析、格式化
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ):
        _key = api_key or config.BUDGET_API_KEY or config.LLM_API_KEY
        if not _key:
            raise ValueError("未配置 BUDGET_API_KEY 或 LLM_API_KEY")
        self.client = OpenAI(
            api_key=_key,
            base_url=base_url or config.BUDGET_BASE_URL or config.LLM_BASE_URL,
        )
        self.model = (model or config.BUDGET_MODEL or "deepseek-v4-flash").lower()
        self.max_tokens = 4000  # 预算模型默认限制

    def summarize_logs(
        self,
        matches: list[dict[str, Any]],
        max_entries: int = 100,
    ) -> dict[str, Any]:
        """批量总结日志匹配结果，生成结构化分析.

        Args:
            matches: 日志匹配记录列表
            max_entries: 最大处理条目数

        Returns:
            包含摘要、严重程度分布、建议的字典
        """
        if not matches:
            return {
                "summary": "未发现异常日志模式",
                "severity_distribution": {},
                "top_issues": [],
                "recommendations": [],
            }

        # 截取前 N 条避免超出上下文
        entries = matches[:max_entries]
        prompt = self._build_log_summary_prompt(entries)

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是安全日志分析助手，擅长从大量日志中识别关键模式并给出简洁总结。",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=self.max_tokens,
            )
            content = resp.choices[0].message.content or ""
            return self._parse_log_summary_response(content, matches)
        except Exception as exc:
            # 失败时回退到规则化总结
            return self._fallback_log_summary(matches)

    def _build_log_summary_prompt(self, matches: list[dict[str, Any]]) -> str:
        """构建日志总结提示词."""
        lines = []
        lines.append(f"共 {len(matches)} 条日志匹配记录，请分析并返回 JSON 格式结果：")
        lines.append("")
        lines.append("需要分析的维度：")
        lines.append("1. 整体摘要（1-2句话）")
        lines.append("2. 严重程度分布（统计各严重级别的数量）")
        lines.append("3. 前三类主要问题（按严重程度和时间集中度）")
        lines.append("4. 具体建议（3-5条可操作建议）")
        lines.append("")
        lines.append("日志数据：")
        for i, m in enumerate(matches[:50], 1):  # 限制输入长度
            lines.append(
                f"{i}. [{m.get('severity', '未知')}] {m.get('pattern_name', '未知')} "
                f"- {m.get('log_file', '')}:{m.get('line_number', 0)} "
                f"- {m.get('matched_text', '')[:80]}"
            )
        lines.append("")
        lines.append("返回格式（严格 JSON，不要 markdown）：")
        lines.append(json.dumps({
            "summary": "整体情况摘要",
            "severity_distribution": {"严重": 0, "高": 0, "中": 0, "低": 0},
            "top_issues": [
                {"pattern": "问题类型", "count": 0, "severity": "级别", "description": "说明"}
            ],
            "recommendations": ["建议1", "建议2"],
        }, ensure_ascii=False, indent=2))
        return "\n".join(lines)

    def _parse_log_summary_response(
        self,
        content: str,
        original_matches: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """解析 LLM 返回的总结内容."""
        # 尝试提取 JSON
        try:
            # 查找 JSON 块
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1:
                data = json.loads(content[start:end+1])
                return {
                    "summary": data.get("summary", ""),
                    "severity_distribution": data.get("severity_distribution", {}),
                    "top_issues": data.get("top_issues", []),
                    "recommendations": data.get("recommendations", []),
                    "model_used": self.model,
                    "processed_count": len(original_matches),
                }
        except (json.JSONDecodeError, ValueError):
            pass

        # 解析失败时回退
        return self._fallback_log_summary(original_matches)

    def _fallback_log_summary(self, matches: list[dict[str, Any]]) -> dict[str, Any]:
        """LLM 失败时的规则化回退总结."""
        from collections import Counter

        severity_dist = Counter(m.get("severity", "未知") for m in matches)
        pattern_dist = Counter(m.get("pattern_name", "未知") for m in matches)

        top_patterns = pattern_dist.most_common(3)
        top_issues = [
            {
                "pattern": name,
                "count": count,
                "severity": next(
                    (m.get("severity", "中") for m in matches if m.get("pattern_name") == name),
                    "中"
                ),
            }
            for name, count in top_patterns
        ]

        return {
            "summary": f"检测到 {len(matches)} 条异常日志，主要涉及 {len(pattern_dist)} 种模式",
            "severity_distribution": dict(severity_dist),
            "top_issues": top_issues,
            "recommendations": [
                f"关注最严重的 '{top_issues[0]['pattern']}' 模式" if top_issues else "暂无具体建议",
                "建议进一步分析相关日志源",
            ],
            "model_used": "fallback_rules",
            "processed_count": len(matches),
        }

    def generate_report_summary(
        self,
        scan_data: dict[str, Any],
        format_type: str = "executive",
    ) -> str:
        """为安全报告生成执行摘要.

        Args:
            scan_data: 安全扫描数据
            format_type: 摘要类型 (executive/technical/brief)

        Returns:
            生成的摘要文本
        """
        risks = scan_data.get("risks", [])
        system = scan_data.get("system", {})

        prompt_lines = [
            f"请根据以下安全扫描数据生成 {format_type} 格式的执行摘要：",
            "",
            "系统信息：",
            f"- 平台: {system.get('platform', '未知')}",
            f"- 是否 root: {'是' if system.get('is_root') else '否'}",
            f"- 扫描时间: {scan_data.get('timestamp', '未知')}",
            "",
            f"风险概况：共 {len(risks)} 项风险",
        ]

        # 按严重程度分组
        severity_groups: dict[str, list[dict]] = {}
        for r in risks[:20]:  # 限制数量
            sev = r.get("severity", "中")
            severity_groups.setdefault(sev, []).append(r)

        for sev, items in sorted(
            severity_groups.items(),
            key=lambda x: {"严重": 0, "高": 1, "中": 2, "低": 3}.get(x[0], 4)
        ):
            prompt_lines.append(f"\n[{sev}] 级别 ({len(items)} 项):")
            for item in items[:5]:
                prompt_lines.append(f"  - {item.get('title', '未知')}: {item.get('description', '')[:60]}")

        prompt_lines.append("\n\n请生成简洁的执行摘要（300字以内），包含：")
        prompt_lines.append("1. 整体安全态势评估")
        prompt_lines.append("2. 需要优先处理的关键风险")
        prompt_lines.append("3. 简要建议")

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是安全报告撰写专家，擅长生成简洁有力的执行摘要。",
                    },
                    {"role": "user", "content": "\n".join(prompt_lines)},
                ],
                temperature=0.3,
                max_tokens=800,
            )
            return resp.choices[0].message.content or self._fallback_report_summary(risks)
        except Exception:
            return self._fallback_report_summary(risks)

    def _fallback_report_summary(self, risks: list[dict]) -> str:
        """报告总结的回退实现."""
        critical = sum(1 for r in risks if r.get("severity") == "严重")
        high = sum(1 for r in risks if r.get("severity") == "高")

        if critical > 0:
            return f"【紧急】发现 {critical} 项严重风险，{high} 项高风险，建议立即处理严重级别问题。"
        elif high > 0:
            return f"【关注】发现 {high} 项高风险，建议优先排查。整体安全态势需要加强监控。"
        elif risks:
            return f"【提醒】发现 {len(risks)} 项风险，以中低级别为主，建议定期复查。"
        else:
            return "【良好】未发现明显安全风险，建议继续保持当前安全策略。"

    def batch_analyze(
        self,
        items: list[dict[str, Any]],
        analysis_type: str = "pattern",
    ) -> dict[str, Any]:
        """通用批量分析接口.

        Args:
            items: 待分析的数据项列表
            analysis_type: 分析类型 (pattern/anomaly/trend)

        Returns:
            分析结果字典
        """
        if not items:
            return {"result": "无数据", "count": 0}

        if analysis_type == "pattern":
            return self._analyze_patterns(items)
        elif analysis_type == "anomaly":
            return self._analyze_anomalies(items)
        else:
            return {"result": "未知的分析类型", "count": len(items)}

    def _analyze_patterns(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """识别数据中的模式."""
        # 提取关键字段进行分组统计
        from collections import Counter

        # 尝试识别常见字段
        field_counts: dict[str, Counter] = {}
        for item in items:
            for key, value in item.items():
                if isinstance(value, str) and len(value) < 50:
                    field_counts.setdefault(key, Counter())[value] += 1

        # 找出有明显集中趋势的字段
        significant_patterns = []
        for field, counter in field_counts.items():
            if len(counter) > 1 and counter.most_common(1)[0][1] > 1:
                top_values = counter.most_common(3)
                significant_patterns.append({
                    "field": field,
                    "distinct_values": len(counter),
                    "top_values": top_values,
                })

        return {
            "type": "pattern_analysis",
            "total_items": len(items),
            "patterns_found": len(significant_patterns),
            "significant_patterns": significant_patterns[:10],
            "model_used": self.model,
        }

    def _analyze_anomalies(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """识别异常数据点."""
        # 简单规则：数值字段中的离群值
        anomalies = []

        for item in items:
            # 检查是否有异常标记
            if item.get("severity") in ("严重", "高"):
                anomalies.append({
                    "item": item,
                    "reason": "高严重程度",
                })
            # 检查时间异常（如果有）
            if "timestamp" in item:
                # 可以添加时间序列异常检测
                pass

        return {
            "type": "anomaly_detection",
            "total_items": len(items),
            "anomalies_found": len(anomalies),
            "anomalies": anomalies[:20],
            "model_used": self.model,
        }


# 全局 Budget Agent 实例（延迟初始化）
_budget_agent: BudgetAgent | None = None


def get_budget_agent() -> BudgetAgent:
    """获取或创建 Budget Agent 单例."""
    global _budget_agent
    if _budget_agent is None:
        try:
            _budget_agent = BudgetAgent()
        except ValueError:
            # 配置未就绪时使用通用 LLM
            _budget_agent = BudgetAgent(
                api_key=config.LLM_API_KEY,
                base_url=config.LLM_BASE_URL,
                model=config.LLM_MODEL,
            )
    return _budget_agent


def reset_budget_agent() -> None:
    """重置 Budget Agent（配置变更后调用）."""
    global _budget_agent
    _budget_agent = None
