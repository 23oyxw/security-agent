"""蓝队开源项目自动爬取与学习模块.

从 GitHub / Gitee 拉取蓝队安全开源项目，提取知识要点，
输出蓝队知识点 + 适配项目的优化建议。

使用方式:
    from security_agent.knowledge.blue_team_crawler import BlueTeamCrawler
    crawler = BlueTeamCrawler()
    report = crawler.run()
"""

from __future__ import annotations

import json
import logging
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 蓝队开源项目清单（GitHub / Gitee 镜像）
# ---------------------------------------------------------------------------
BLUE_TEAM_REPOS: list[dict[str, str]] = [
    # --- 应急响应 & 入侵排查 ---
    {
        "name": "ThreatHunter",
        "url": "https://gitee.com/mirrors/ThreatHunter.git",
        "github": "https://github.com/EndlessIvar/ThreatHunter",
        "category": "入侵排查",
        "description": "Linux 入侵排查脚本集合：异常进程、隐藏文件、Rootkit 检测",
    },
    {
        "name": "Sigma",
        "url": "https://gitee.com/mirrors/sigma.git",
        "github": "https://github.com/Neo23x0/sigma",
        "category": "威胁检测规则",
        "description": "通用 SIEM 检测规则集，覆盖 Web 攻击、提权、横向移动等场景",
    },
    {
        "name": "xunfeng",
        "url": "https://gitee.com/mirrors/xunfeng.git",
        "github": "https://github.com/ysrc/xunfeng",
        "category": "资产扫描",
        "description": "巡风——资产安全扫描系统，端口+漏洞+弱口令",
    },
    {
        "name": "Security-Awesome",
        "url": "https://gitee.com/mirrors/Security-Awesome.git",
        "github": "https://github.com/rabbitmask/Security-Awesome",
        "category": "蓝队知识库",
        "description": "蓝队知识库：应急响应、日志分析、溯源工具汇总",
    },
    # --- API 安全 & 限流 ---
    {
        "name": "slowapi",
        "url": "https://gitee.com/mirrors/slowapi.git",
        "github": "https://github.com/laurentS/slowapi",
        "category": "API限流",
        "description": "FastAPI/Starlette 速率限制中间件，防止接口被暴力请求打崩",
    },
    {
        "name": "pybreaker",
        "url": "https://gitee.com/mirrors/pybreaker.git",
        "github": "https://github.com/danielfm/pybreaker",
        "category": "熔断机制",
        "description": "Python 熔断器模式实现，API 挂了直接停止请求避免雪崩",
    },
    # --- 日志分析 ---
    {
        "name": "logdetective",
        "url": "https://gitee.com/mirrors/logdetective.git",
        "github": "https://github.com/kevoreilly/logdetective",
        "category": "日志分析",
        "description": "日志异常检测，发现可疑登录/越权操作",
    },
]

# 用于 GitHub 加速拉取的镜像
GHPROXY_PREFIX = "https://mirror.ghproxy.com/"


@dataclass
class ProjectAnalysis:
    """单个开源项目的分析结果."""
    name: str
    category: str
    description: str
    repo_url: str
    cloned: bool = False
    blue_team_skills: list[str] = field(default_factory=list)
    optimization_patches: list[str] = field(default_factory=list)
    training_scenarios: list[dict[str, str]] = field(default_factory=list)
    error: str = ""


@dataclass
class CrawlerReport:
    """爬取分析总报告."""
    timestamp: float = 0.0
    projects: list[ProjectAnalysis] = field(default_factory=list)
    total_skills: int = 0
    total_patches: int = 0
    total_scenarios: int = 0


# ---------------------------------------------------------------------------
# 知识提取模板（让 LLM 学习后输出结构化内容）
# ---------------------------------------------------------------------------
SKILL_EXTRACTION_PROMPT = """你现在读取下面蓝队开源项目的源码与文档：

项目名称：{name}
项目说明：{description}
项目分类：{category}

请从以下维度拆解蓝队技能：

1. **日志溯源**：项目中有哪些日志分析方法？可以检测哪些攻击？
2. **异常进程排查**：哪些脚本/规则用于发现异常进程、后门、Rootkit？
3. **API 攻击检测**：是否有接口限流、恶意请求识别、CC 攻击防御的实现？
4. **后门排查**：项目中有哪些后门检测规则/脚本？
5. **应急响应流程**：项目提供了哪些自动化应急响应能力？

输出 JSON 格式：
{{
  "blue_team_skills": ["技能1", "技能2", ...],
  "optimization_patches": ["针对安全运维 API 项目的优化建议1", ...],
  "training_scenarios": [
    {{"title": "场景名", "description": "实操描述", "difficulty": "初级/中级/高级"}}
  ]
}}"""


class BlueTeamCrawler:
    """蓝队开源项目自动爬取器."""

    def __init__(
        self,
        data_dir: Path | None = None,
        max_clone_time: int = 60,
        enable_clone: bool = False,
    ):
        self.data_dir = data_dir or Path(__file__).resolve().parents[2] / "data" / "blue_team"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.max_clone_time = max_clone_time
        self.enable_clone = enable_clone  # 默认不 clone，只用 LLM 分析

    def list_repos(self) -> list[dict[str, str]]:
        """返回蓝队开源项目清单."""
        return BLUE_TEAM_REPOS.copy()

    def _clone_repo(self, repo: dict[str, str]) -> Path | None:
        """Clone 单个仓库（带超时和镜像加速）."""
        if not self.enable_clone:
            return None

        name = repo["name"]
        clone_dir = self.data_dir / "repos" / name
        if clone_dir.exists():
            logger.info("仓库已存在，跳过 clone: %s", name)
            return clone_dir

        url = repo["url"]
        # 尝试 GitHub 加速镜像
        if "github.com" in url and not url.startswith(GHPROXY_PREFIX):
            url = GHPROXY_PREFIX + url

        try:
            result = subprocess.run(
                ["git", "clone", "--depth=1", "--single-branch", url, str(clone_dir)],
                capture_output=True,
                text=True,
                timeout=self.max_clone_time,
            )
            if result.returncode == 0:
                logger.info("Clone 成功: %s", name)
                return clone_dir
            else:
                logger.warning("Clone 失败 %s: %s", name, result.stderr[:200])
                return None
        except subprocess.TimeoutExpired:
            logger.warning("Clone 超时: %s (%ds)", name, self.max_clone_time)
            return None
        except Exception as e:
            logger.warning("Clone 异常 %s: %s", name, e)
            return None

    def _analyze_with_llm(self, repo: dict[str, str]) -> dict[str, Any]:
        """用 LLM 分析项目蓝队技能（不需 clone，直接用项目描述）."""
        from security_agent.agent.fallback import FallbackClient
        from security_agent import config

        if not config.llm_configured():
            return {
                "blue_team_skills": [f"[离线模式] {repo['description']}"],
                "optimization_patches": ["配置 LLM_API_KEY 后可获取详细分析"],
                "training_scenarios": [],
            }

        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=config.LLM_API_KEY or config.BUDGET_API_KEY,
                base_url=config.LLM_BASE_URL or config.BUDGET_BASE_URL,
            )
            fb = FallbackClient(primary_client=client, primary_model=config.resolve_agent_model())

            prompt = SKILL_EXTRACTION_PROMPT.format(**repo)
            response, _ = fb.chat_completion(
                messages=[
                    {"role": "system", "content": "你是安全运维专家，专注蓝队攻防技术分析。只输出 JSON。"},
                    {"role": "user", "content": prompt},
                ],
                tools=None,
            )
            text = (response.choices[0].message.content or "").strip()
            # 尝试提取 JSON
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            return json.loads(text)
        except Exception as e:
            logger.warning("LLM 分析 %s 失败: %s", repo["name"], e)
            return {
                "blue_team_skills": [repo["description"]],
                "optimization_patches": [],
                "training_scenarios": [],
            }

    def analyze_repo(self, repo: dict[str, str]) -> ProjectAnalysis:
        """分析单个项目."""
        analysis = ProjectAnalysis(
            name=repo["name"],
            category=repo["category"],
            description=repo["description"],
            repo_url=repo.get("github", repo["url"]),
        )

        # 可选 clone
        clone_dir = self._clone_repo(repo)
        analysis.cloned = clone_dir is not None

        # LLM 分析
        result = self._analyze_with_llm(repo)
        analysis.blue_team_skills = result.get("blue_team_skills", [])
        analysis.optimization_patches = result.get("optimization_patches", [])
        analysis.training_scenarios = result.get("training_scenarios", [])

        return analysis

    def run(self, repos: list[dict[str, str]] | None = None) -> CrawlerReport:
        """执行全量爬取分析."""
        report = CrawlerReport(timestamp=time.time())

        target_repos = repos or BLUE_TEAM_REPOS
        for repo in target_repos:
            logger.info("分析项目: %s (%s)", repo["name"], repo["category"])
            try:
                analysis = self.analyze_repo(repo)
                report.projects.append(analysis)
                report.total_skills += len(analysis.blue_team_skills)
                report.total_patches += len(analysis.optimization_patches)
                report.total_scenarios += len(analysis.training_scenarios)
            except Exception as e:
                logger.error("分析 %s 失败: %s", repo["name"], e)
                report.projects.append(ProjectAnalysis(
                    name=repo["name"],
                    category=repo["category"],
                    description=repo["description"],
                    repo_url=repo.get("github", repo["url"]),
                    error=str(e),
                ))

        # 保存报告
        self._save_report(report)
        return report

    def _save_report(self, report: CrawlerReport) -> None:
        """保存爬取报告到文件."""
        report_path = self.data_dir / "blue_team_report.json"
        data = {
            "timestamp": report.timestamp,
            "total_skills": report.total_skills,
            "total_patches": report.total_patches,
            "total_scenarios": report.total_scenarios,
            "projects": [
                {
                    "name": p.name,
                    "category": p.category,
                    "description": p.description,
                    "repo_url": p.repo_url,
                    "cloned": p.cloned,
                    "blue_team_skills": p.blue_team_skills,
                    "optimization_patches": p.optimization_patches,
                    "training_scenarios": p.training_scenarios,
                    "error": p.error,
                }
                for p in report.projects
            ],
        }
        report_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("报告已保存: %s", report_path)

    def get_daily_training(self) -> dict[str, Any]:
        """获取今日蓝队训练场景（轮转）."""
        report_path = self.data_dir / "blue_team_report.json"
        if not report_path.exists():
            return {"error": "请先运行蓝队项目分析（POST /api/knowledge/blue-team/scan）"}

        data = json.loads(report_path.read_text(encoding="utf-8"))
        all_scenarios = []
        for proj in data.get("projects", []):
            for s in proj.get("training_scenarios", []):
                s["source_project"] = proj["name"]
                s["category"] = proj["category"]
                all_scenarios.append(s)

        if not all_scenarios:
            return {"error": "暂无训练场景，请先完成蓝队项目分析"}

        # 按日期轮转
        day_index = int(time.time() / 86400) % len(all_scenarios)
        return {
            "day_index": day_index,
            "total_scenarios": len(all_scenarios),
            "today": all_scenarios[day_index],
            "all_scenarios": all_scenarios[:10],  # 返回前 10 个
        }