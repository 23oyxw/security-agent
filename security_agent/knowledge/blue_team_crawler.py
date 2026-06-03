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

    # 离线预设数据：每个蓝队项目的技能/优化/训练场景
    _OFFLINE_KNOWLEDGE: dict[str, dict[str, Any]] = {
        "ThreatHunter": {
            "blue_team_skills": [
                "Linux 异常进程排查：检测隐藏进程、无对应二进制文件的可疑进程",
                "Rootkit 检测：通过 rkhunter/chkrootkit 扫描内核级后门",
                "异常登录分析：解析 /var/log/auth.log 发现暴力破解与异常登录",
                "隐藏文件发现：扫描 /tmp /dev/shm 等非常规目录下的可执行文件",
                "网络连接排查：关联进程与网络连接，发现反向 Shell 与 C2 通信",
                "定时任务审计：检查 crontab / systemd timer 中的持久化后门",
                "SSH 后门检测：对比 sshd 二进制哈希，检测 SSH wrapper 后门",
                "用户权限审计：扫描 /etc/passwd /etc/shadow 异常 UID/GID 用户",
            ],
            "optimization_patches": [
                "集成 ThreatHunter 扫描结果到安全报告中，自动生成处置建议",
                "将 ThreatHunter 检测规则转化为系统监控告警规则",
                "添加定时自动巡检模式，每日凌晨执行一次全面排查",
            ],
            "training_scenarios": [
                {"title": "SSH暴力破解应急", "description": "模拟场景：发现 /var/log/auth.log 中同一 IP 连续失败 200+ 次。实操步骤：1) 使用 fail2ban 即时封禁 IP 2) 检查是否有成功登录 3) 审计 authorized_keys 4) 检查用户是否被创建后门账号 5) 生成事件报告", "difficulty": "初级"},
                {"title": "Rootkit 后门排查", "description": "模拟场景：系统出现异常网络流量但 ps/top 看不到可疑进程。实操：1) rkhunter --check 2) chkrootkit 3) 对比 RPM/DPKG 数据库 4) 检查 /proc 异常项 5) 使用 unhide 发藏匿进程", "difficulty": "高级"},
                {"title": "Webshell 清理演练", "description": "模拟场景：在 /var/www/html 下发现可疑 PHP 文件。实操：1) 使用 find 查找近期修改文件 2) 分析文件内容特征(eval/base64) 3) 检查访问日志定位攻击者 IP 4) 清除恶意文件 5) 修复文件权限", "difficulty": "中级"},
            ],
        },
        "Sigma": {
            "blue_team_skills": [
                "SIEM 规则编写：使用 Sigma 语法编写跨平台检测规则",
                "Web 攻击检测：SQL 注入、XSS、文件包含等 Web 攻击规则覆盖",
                "横向移动检测：Pass-the-Hash、PsExec、WMI 远程执行等检测",
                "提权攻击检测：UAC 绕过、Token 窃取、服务权限滥用等规则",
                "恶意软件检测：PowerShell 混淆执行、CobaltStrike Beacon 通信特征",
                "日志关联分析：跨源日志(Windows/Linux/Network)关联检测攻击链",
                "规则转换引擎：将 Sigma 规则转为 Splunk/ES/KQL 等目标平台格式",
            ],
            "optimization_patches": [
                "将 Sigma 规则集成到安全告警管道中，实现自动匹配与告警",
                "按项目场景定制 Sigma 规则，聚焦实际威胁面",
                "建立规则测试框架，确保规则质量与降低误报",
            ],
            "training_scenarios": [
                {"title": "Sigma 规则编写实战", "description": "实操：为以下场景编写 Sigma 规则 1) PowerShell 下载并执行远程脚本 2) 异常时间的 SSH 登录 3) /etc/passwd 文件修改 4) 大量 DNS 查询(隧道检测)。转换为目标 SIEM 并验证", "difficulty": "中级"},
                {"title": "攻击链检测串联", "description": "模拟完整攻击链：侦察→漏洞利用→提权→横向移动→数据窃取。使用 Sigma 规则在各阶段触发告警，验证检测覆盖率。分析告警时间线，找出检测盲区", "difficulty": "高级"},
                {"title": "误报优化实战", "description": "给定 50 条 Sigma 规则和一周告警数据。实操：1) 统计各规则触发频率 2) 分析 FP 原因 3) 添加白名单条件 4) 重新测试确认 FN 率不增加", "difficulty": "中级"},
            ],
        },
        "xunfeng": {
            "blue_team_skills": [
                "资产发现：自动化扫描内网存活主机与开放端口",
                "漏洞扫描：识别常见 CVE 漏洞 (Web 中间件/数据库/OS)",
                "弱口令检测：对 SSH/FTP/MySQL/Redis 等服务进行弱密码审计",
                "Web 指纹识别：识别 CMS/框架/组件版本，发现已知漏洞组件",
                "资产变更监控：定期扫描对比，发现新增/消失的资产与端口",
                "扫描任务管理：支持分批扫描、定时任务、扫描速率控制",
            ],
            "optimization_patches": [
                "将巡风扫描结果导入资产数据库，建立完整资产清单",
                "设置周期性扫描任务，及时发现新暴露的攻击面",
                "集成漏洞库更新，确保检测规则覆盖最新漏洞",
            ],
            "training_scenarios": [
                {"title": "内网资产全面排查", "description": "模拟场景：新接手一个内网环境，需要摸清资产状况。实操：1) 配置 xunfeng 扫描全网段 2) 整理资产清单 3) 识别高风险资产(暴露端口/弱口令) 4) 生成资产安全报告", "difficulty": "初级"},
                {"title": "弱口令批量审计", "description": "模拟场景：对生产环境所有服务进行弱口令审计。实操：1) 配置字典(常见弱口令+行业特征) 2) 目标：SSH/MySQL/Redis/FTP/MongoDB 3) 分析结果 4) 生成加固建议", "difficulty": "中级"},
                {"title": "漏洞利用与修复验证", "description": "实操：1) 使用巡风发现目标漏洞 2) 手动验证漏洞真实性 3) 提供修复方案 4) 修复后重新扫描验证", "difficulty": "高级"},
            ],
        },
        "Security-Awesome": {
            "blue_team_skills": [
                "应急响应知识库：Windows/Linux 入侵排查标准操作流程(SOP)",
                "日志分析方法论：Web/系统/网络日志分析技巧与关键字段",
                "溯源工具链：IP 定位、域名反查、样本分析工具集",
                "常见攻击手法识别：APT/勒索/挖矿/蠕虫等攻击特征与应对",
                "取证流程规范：数字证据保全链、内存取证、磁盘取证标准流程",
                "安全报告模板：标准化安全事件报告、分析报告模板",
            ],
            "optimization_patches": [
                "将安全知识库条目导入系统 grounding 检索库，增强 Agent 知识",
                "参考应急 SOP 建立自动化应急响应流程",
                "将溯源工具链集成到自动化调查模块中",
            ],
            "training_scenarios": [
                {"title": "完整应急响应演练", "description": "模拟场景：服务器被入侵，黑客已获取 root 权限。演练完整流程：1) 接收报警 2) 隔离主机 3) 证据保全(内存/日志/进程/连接) 4) 入侵分析 5) 清除后门 6) 恢复业务 7) 事后报告", "difficulty": "高级"},
                {"title": "日志关联分析实战", "description": "给定 Web 访问日志、系统认证日志、防火墙日志各一份。实操：1) 提取关键字段 2) 按时间线排序 3) 关联分析攻击路径 4) 确定入侵入口 5) 评估影响范围", "difficulty": "中级"},
                {"title": "勒索病毒应急处置", "description": "模拟场景：文件服务器感染勒索病毒。实操：1) 立即断网隔离 2) 检查感染范围 3) 识别病毒家族 4) 寻找解密工具 5) 从备份恢复 6) 加固防御措施", "difficulty": "中级"},
            ],
        },
        "slowapi": {
            "blue_team_skills": [
                "API 速率限制：基于 IP/用户/端点的请求频率控制",
                "CC 攻击防御：识别并阻止高频恶意请求",
                "接口熔断：当请求异常率过高时自动降级保护",
                "请求队列管理：突发流量缓冲与排队机制",
                "自定义限流策略：按业务场景配置不同限流规则",
            ],
            "optimization_patches": [
                "在安全运维 API 的关键接口(执行/扫描/配置变更)添加限流",
                "对 IP 维度限流防止单点暴力攻击",
                "添加 API 请求日志审计，记录异常频率请求",
            ],
            "training_scenarios": [
                {"title": "API 限流配置实战", "description": "实操：1) 分析 API 流量模式 2) 设计限流策略(全局/单接口/单IP) 3) 配置 slowapi 4) 使用 ab/wrk 压测验证 5) 调整参数找到最佳阈值", "difficulty": "初级"},
                {"title": "CC 攻击模拟与防御", "description": "模拟场景：API 接口被大量恶意请求。实操：1) 使用工具模拟 CC 攻击 2) 观察服务响应 3) 配置限流规则 4) 验证防御效果 5) 确保正常请求不受影响", "difficulty": "中级"},
            ],
        },
        "pybreaker": {
            "blue_team_skills": [
                "熔断器模式：当下游服务故障率超阈值时自动断开调用",
                "故障隔离：防止单个服务故障引发级联雪崩",
                "自动恢复探测：熔断后定期尝试半开状态恢复",
                "状态监控：实时监控熔断器状态(关闭/打开/半开)",
                "降级策略：熔断时返回默认值或缓存数据",
            ],
            "optimization_patches": [
                "在 LLM API 调用处添加熔断器，API 不可用时直接使用离线知识",
                "对外部 MCP 工具调用添加熔断保护",
                "监控熔断事件并记录告警日志",
            ],
            "training_scenarios": [
                {"title": "熔断器集成实战", "description": "实操：1) 分析系统中所有外部依赖调用 2) 为每个调用配置熔断器 3) 模拟下游故障 4) 验证熔断触发与恢复 5) 监控熔断状态仪表板", "difficulty": "中级"},
                {"title": "级联故障防御", "description": "模拟场景：LLM API 不可用导致 Agent 响应超时→前端请求堆积→服务崩溃。实操：1) 添加熔断+超时+重试机制 2) 设置降级策略 3) 压测验证系统稳定性", "difficulty": "高级"},
            ],
        },
        "logdetective": {
            "blue_team_skills": [
                "日志异常检测：基于统计模型识别日志中的异常模式",
                "可疑登录识别：非工作时间/异常地域/多次失败的登录行为",
                "越权操作检测：非预期的权限提升或资源访问",
                "日志时序分析：按时间线还原攻击路径",
                "基线学习：建立正常行为基线，偏离即告警",
            ],
            "optimization_patches": [
                "将 logdetective 集成到审计日志分析管道",
                "建立常见攻击的日志特征库",
                "添加日志异常到告警系统的自动转发",
            ],
            "training_scenarios": [
                {"title": "日志异常检测实战", "description": "实操：1) 提供一周的系统日志数据 2) 使用 logdetective 分析异常 3) 区分真实威胁与误报 4) 建立行为基线 5) 验证检测效果", "difficulty": "中级"},
                {"title": "登录行为分析", "description": "模拟场景：用户账号被爆破后成功登录。实操：1) 分析 auth.log 时间线 2) 识别爆破特征 3) 定位成功登录 4) 检查登录后操作 5) 封禁攻击 IP 6) 强制密码重置", "difficulty": "初级"},
            ],
        },
    }

    def _analyze_with_llm(self, repo: dict[str, str]) -> dict[str, Any]:
        """用 LLM 分析项目蓝队技能（不需 clone，直接用项目描述）."""
        from security_agent.agent.fallback import FallbackClient
        from security_agent import config

        # 优先使用预设知识（保证离线也有丰富数据）
        preset = self._OFFLINE_KNOWLEDGE.get(repo["name"])
        if not config.llm_configured():
            if preset:
                return preset
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
            logger.warning("LLM 分析 %s 失败: %s，使用预设知识", repo["name"], e)
            if preset:
                return preset
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
            # 无缓存时直接用预设数据生成场景列表
            all_scenarios = []
            for name, preset in self._OFFLINE_KNOWLEDGE.items():
                cat = next((r["category"] for r in BLUE_TEAM_REPOS if r["name"] == name), "未知")
                for s in preset.get("training_scenarios", []):
                    s_copy = dict(s)
                    s_copy["source_project"] = name
                    s_copy["category"] = cat
                    all_scenarios.append(s_copy)
            if not all_scenarios:
                return {"error": "暂无训练场景"}
            day_index = int(time.time() / 86400) % len(all_scenarios)
            return {
                "day_index": day_index,
                "total_scenarios": len(all_scenarios),
                "today": all_scenarios[day_index],
                "all_scenarios": all_scenarios[:10],
            }

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