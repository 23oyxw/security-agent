"""安全知识库 — 结构化剧本，供检索 grounding，降低幻觉与误操作."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Playbook:
    id: str
    title: str
    body: str
    threat_tags: tuple[str, ...]
    severity: str
    requires_root_confirm: bool
    keywords: tuple[str, ...]
    do_not: tuple[str, ...] = ()
    suggested_actions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "threat_tags": list(self.threat_tags),
            "severity": self.severity,
            "requires_root_confirm": self.requires_root_confirm,
            "keywords": list(self.keywords),
            "do_not": list(self.do_not),
            "suggested_actions": list(self.suggested_actions),
        }


# 30+ 条：覆盖误删、伪装窃密、端口暴露、权限、监控盲区、人性化处置
PLAYBOOKS: tuple[Playbook, ...] = (
    Playbook(
        "PB-MISDELETE-01",
        "拦截进程前必须二次确认",
        "任何 kill/block 前应先 list_processes 或 get_process_detail，核对 PID、用户、命令行。"
        "开发中的 streamlit/python/node 常被误判；演练诱饵 decoy 可安全停止。",
        ("misdelete", "process"),
        "高",
        False,
        ("误删", "kill", "拦截", "进程", "确认"),
        ("未核对 PID 就 block", "批量 kill 开发服务"),
        ("核对 cmdline 与业务归属", "优先 stop 而非 kill -9", "记录审计"),
    ),
    Playbook(
        "PB-MISDELETE-02",
        "高危工具名不等于恶意",
        "grep/cat 日志中出现 nmap/nc 多为检索关键字；官方 decoy 路径可豁免。"
        "应结合进程树、网络连接、文件变更综合判断。",
        ("misdelete", "false_positive"),
        "中",
        False,
        ("误报", "nmap", "nc", "grep", "日志"),
        ("仅因命令行含工具名就终止",),
        ("运行 detection_calibration 校准", "查看完整 cmdline", "对比监控事件时间线"),
    ),
    Playbook(
        "PB-EXFIL-01",
        "伪装与窃密进程特征",
        "警惕：异常外连、监听高端口、进程名仿系统（sshd2）、工作目录在 /tmp、"
        "cmdline 含 base64|curl|wget 管道、无对应软件包。",
        ("exfiltration", "impersonation", "process"),
        "严重",
        False,
        ("窃密", "伪装", "外连", "base64", "反弹"),
        ("未取证就删进程",),
        ("保留 PID 与连接快照", "查 /proc/PID/fd", "对照审计与 auth.log"),
    ),
    Playbook(
        "PB-EXFIL-02",
        "敏感文件外传路径",
        "关注对 /etc/shadow、.ssh/id_rsa、业务数据库配置的读取与外传；"
        "tar+curl、scp 到未知 IP 需告警。",
        ("exfiltration", "data"),
        "严重",
        True,
        ("外传", "shadow", "ssh", "密钥", "scp"),
        ("在未确认下 chmod 放宽权限",),
        ("check_sensitive_paths", "收紧权限", "轮换密钥"),
    ),
    Playbook(
        "PB-PORT-01",
        "端口暴露与对外监听",
        "0.0.0.0 或 :: 上监听数据库/Redis/调试口（6379/9200/4444）属高风险；"
        "应仅内网或 localhost 绑定。",
        ("port_exposure", "network"),
        "高",
        False,
        ("端口", "暴露", "监听", "6379", "redis", "0.0.0.0"),
        ("直接 iptables -F",),
        ("check_exposed_ports", "ss -tlnp 复核", "防火墙最小放行"),
    ),
    Playbook(
        "PB-PORT-02",
        "SSH/RDP 暴露面",
        "22/3389 对公网开放需强认证与 fail2ban；非标准端口不能替代弱口令。",
        ("port_exposure", "network"),
        "高",
        False,
        ("ssh", "3389", "rdp", "22", "公网"),
        (),
        ("限制来源 IP", "禁用密码仅密钥", "审查 authorized_keys"),
    ),
    Playbook(
        "PB-ROOT-01",
        "root 增删改查须人工确认",
        "涉及 sudo/su、useradd/userdel、chmod/chown、写 /etc、iptables、systemctl stop 等"
        "一律 NEED_CONFIRM，界面勾选后方可执行。",
        ("privilege", "root"),
        "严重",
        True,
        ("root", "sudo", "权限", "userdel", "chmod"),
        ("Agent 自动 sudo", "未确认执行写操作",),
        ("展示命令与影响范围", "双人复核高危变更", "写审计"),
    ),
    Playbook(
        "PB-ROOT-02",
        "只读 root 观测允许",
        "sudo systemctl status、sudo cat /var/log、sudo ss -tlnp 等只读排查可自动；"
        "与写操作严格区分。",
        ("privilege", "root"),
        "低",
        False,
        ("只读", "sudo", "status", "journalctl"),
        ("把只读命令与写操作混在同一脚本",),
        ("拆分观测与变更步骤",),
    ),
    Playbook(
        "PB-MON-01",
        "监控无死角检查清单",
        "除进程外应覆盖：新监听端口、敏感文件 mtime、auth.log 失败登录、"
        "异常 cron、新 systemd unit。建议常开 monitor 并设 5s 刷新。",
        ("monitoring_gap",),
        "中",
        False,
        ("监控", "盲区", "cron", "systemd", "auth"),
        ("仅依赖单次扫描",),
        ("start_monitor", "定期 run_full_security_check", "审计导出"),
    ),
    Playbook(
        "PB-MON-02",
        "高危后持续跟踪",
        "告警后 15 分钟内复查进程是否复活、端口是否重开、同 IP 多连接。",
        ("monitoring_gap", "process"),
        "中",
        False,
        ("复发", "持久化", "跟踪"),
        (),
        ("二次扫描对比", "记录事件时间线",),
    ),
    Playbook(
        "PB-DEV-01",
        "日常开发进程白名单意识",
        "streamlit、uv、docker、node、java、postgres 等为正常栈；"
        "告警时先问「是否本人在跑 CI/控制台」。",
        ("misdelete", "daily_dev"),
        "低",
        False,
        ("开发", "streamlit", "docker", "node"),
        ("杀掉正在演示的控制台",),
        ("确认端口 8501 占用者", "用 get_process_detail"),
    ),
    Playbook(
        "PB-DEV-02",
        "改检测规则后跑校准",
        "修改 HIGH_RISK 或规则引擎后必须 run_detection_calibration，保持 66 例全绿。",
        ("false_positive", "daily_dev"),
        "低",
        False,
        ("校准", "fixture", "误报"),
        (),
        ("scripts/demo_risk.py calibration",),
    ),
    Playbook(
        "PB-KYLIN-01",
        "银河麒麟与 kysec",
        "部分脚本 source 被拦截；用 boot_start.sh 单文件启动。"
        "pkexec/sudo 弹窗需用户在场，Agent 不得代替点击确认。",
        ("privilege", "kylin"),
        "中",
        True,
        ("麒麟", "kysec", "pkexec", "kylin"),
        ("绕过 kysec 执行未签名脚本",),
        ("使用项目 boot 脚本", "root 操作走 UI 确认",),
    ),
    Playbook(
        "PB-NET-01",
        "异常外连研判",
        "内网主机连境外 443/4444 需关联进程；LISTEN 与 ESTABLISHED 分开看。",
        ("exfiltration", "network"),
        "高",
        False,
        ("外连", "established", "c2"),
        (),
        ("list_network_connections", "对照 PID", "必要时临时封禁需确认",),
    ),
    Playbook(
        "PB-NET-02",
        "反向 shell 迹象",
        "nc -e、bash -i、/dev/tcp 等模式高危；先隔离网络再处置。",
        ("exfiltration", "network"),
        "严重",
        True,
        ("反弹", "shell", "nc -e", "/dev/tcp"),
        ("未断网就杀进程导致证据丢失",),
        ("保存连接与 cmdline", "断网", "再 block",),
    ),
    Playbook(
        "PB-PERM-01",
        "敏感路径可写",
        "/etc/passwd、shadow、.ssh 可写多为配置错误或入侵；"
        "非 root 可写 shadow 必须立即收紧。",
        ("privilege", "data"),
        "严重",
        True,
        ("权限", "shadow", "passwd", "可写"),
        ("chmod 777 修复",),
        ("check_sensitive_paths", "恢复权限", "查变更时间",),
    ),
    Playbook(
        "PB-AUDIT-01",
        "审计与可追溯",
        "block、terminal、自主任务均写 audit.log；"
        "建议定期导出，事故时按时间线复盘。",
        ("monitoring_gap",),
        "低",
        False,
        ("审计", "日志", "追溯"),
        (),
        ("get_audit_log", "报告中心导出",),
    ),
    Playbook(
        "PB-ADVICE-01",
        "人性化回复结构",
        "先一句话结论（安全/有风险/需确认），再列 1-3 条依据（工具输出/知识库条目），"
        "最后给可执行建议与「请勿」事项；禁止编造未调工具的数据。",
        ("advisor",),
        "信息",
        False,
        ("建议", "结论", "依据", "幻觉"),
        ("编造 PID 或端口", "无依据断言已被入侵",),
        ("引用检索到的 PB-* 编号", "标明需用户确认的操作",),
    ),
    Playbook(
        "PB-ADVICE-02",
        "处置优先级",
        "严重：断网/隔离 → 保全证据 → 用户确认后处置；"
        "高：确认后 block；中低：观察或排期修复。",
        ("advisor",),
        "信息",
        False,
        ("优先级", "处置", "隔离"),
        ("一次性执行所有建议",),
        ("按 severity 排序", "每步可回滚",),
    ),
    Playbook(
        "PB-IMPERSON-01",
        "进程名伪装",
        "名为 [kworker]、sshd 但路径在 /tmp 或 /dev/shm 多为伪装；"
        "用 readlink /proc/PID/exe 核实。",
        ("impersonation", "process"),
        "严重",
        False,
        ("伪装", "kworker", "sshd", "tmp"),
        ("信任进程名 alone",),
        ("get_process_detail", "核对 exe 路径",),
    ),
    Playbook(
        "PB-CRON-01",
        "持久化 cron/systemd",
        "新出现未知 cron、~/.config/systemd/user 下可疑 unit 需查创建时间与内容。",
        ("monitoring_gap", "impersonation"),
        "高",
        True,
        ("cron", "systemd", "持久化"),
        ("直接删系统 cron",),
        ("cat unit 内容", "确认后禁用",),
    ),
    Playbook(
        "PB-DOCKER-01",
        "容器逃逸与特权容器",
        "--privileged、挂载 /、docker.sock 暴露宿主机风险；"
        "生产避免 privileged。",
        ("privilege", "daily_dev"),
        "高",
        False,
        ("docker", "privileged", "逃逸"),
        (),
        ("docker inspect 查 Privileged", "限制 sock 权限",),
    ),
    Playbook(
        "PB-LLM-01",
        "检索 grounding 防幻觉",
        "回答前必须 search_security_knowledge 或已有工具结果；"
        "知识库无依据时明确说「需进一步扫描」。",
        ("advisor", "false_positive"),
        "信息",
        False,
        ("检索", "向量", "grounding", "幻觉"),
        ("编造校准通过率", "虚构 CVE",),
        ("引用 PB 编号与工具输出",),
    ),
    Playbook(
        "PB-PORT-03",
        "数据库默认端口",
        "3306/5432/27017/9200 对 0.0.0.0 监听且弱口令=极高风险。",
        ("port_exposure", "network"),
        "严重",
        False,
        ("mysql", "redis", "mongodb", "elasticsearch", "3306"),
        (),
        ("check_exposed_ports", "改 bind-address", "强密码",),
    ),
    Playbook(
        "PB-BACKUP-01",
        "误删恢复",
        "删进程/文件前确认备份与可重启性；"
        "生产数据库/配置先快照。",
        ("misdelete",),
        "高",
        True,
        ("备份", "恢复", "快照"),
        ("无备份执行 rm",),
        ("确认备份窗口", "用 stop 代替 kill",),
    ),
    Playbook(
        "PB-SCAN-01",
        "综合体检节奏",
        "上线前、变更后、每周 run_full_security_check；"
        "与 calibration 区分：前者查实盘，后者验证规则。",
        ("monitoring_gap", "daily_dev"),
        "低",
        False,
        ("体检", "扫描", "周期"),
        (),
        ("run_full_security_check", "生成 HTML 报告",),
    ),
    Playbook(
        "PB-TERMINAL-01",
        "终端白名单边界",
        "观测类 ps/ss/df 自动；kill/sudo 写操作需确认；"
        "rm -rf、管道 bash 一律拒绝。",
        ("privilege", "misdelete"),
        "高",
        True,
        ("终端", "白名单", "sudo"),
        ("echo|python 绕过执行",),
        ("test_terminal_boundaries",),
    ),
    Playbook(
        "PB-EXFIL-03",
        "DNS/ICMP 隧道",
        "异常 DNS 查询频率、大块 TXT 记录可能为隧道；"
        "需网络层 IDS 与主机进程关联。",
        ("exfiltration", "network"),
        "高",
        False,
        ("dns", "隧道", "icmp"),
        (),
        ("抓包时段分析", "查异常进程",),
    ),
    Playbook(
        "PB-HOST-01",
        "主机沦陷应急",
        "怀疑沦陷时：断网 → 保全内存/连接/日志 → 改密钥 → 复盘入侵路径；"
        "恢复业务前跑 full_drill + calibration。",
        ("exfiltration", "advisor"),
        "严重",
        True,
        ("沦陷", "应急", "断网", "取证"),
        ("未取证就重装",),
        ("隔离", "保全证据", "全量扫描",),
    ),
    Playbook(
        "PB-LLM-02",
        "多维数据含义",
        "检索维度：威胁类型、严重度、是否需 root 确认、建议/禁止动作；"
        "与实盘 scan/monitor/端口 交叉验证。",
        ("advisor",),
        "信息",
        False,
        ("多维", "向量", "标签", "metadata"),
        (),
        ("按标签筛选 search", "结合 check_exposed_ports",),
    ),
    Playbook(
        "PB-REDACT-01",
        "敏感信息自动打码",
        "界面、审计、终端输出、工具返回均经 redact：password/token/sk-/Bearer/auth 登录行；"
        "展示前打码，避免密码泄露到报告或聊天记录。",
        ("advisor", "privilege"),
        "中",
        False,
        ("打码", "脱敏", "密码", "token"),
        ("在聊天中粘贴明文密码",),
        ("日志导出前已打码", "勿关闭脱敏",),
    ),
    Playbook(
        "PB-UI-01",
        "界面确认勾选",
        "自主运维页「允许高危终端」未勾选时，kill/sudo 必须拒绝；"
        "与用户口头确认不等同于 UI 确认。",
        ("privilege", "misdelete"),
        "严重",
        True,
        ("确认", "勾选", "UI"),
        ("口头确认代替勾选",),
        ("勾选后再执行", "审计记录 confirmed=true",),
    ),
    # ===== 蓝队开源项目知识 =====
    Playbook(
        "PB-BT-HUNT-01",
        "ThreatHunter 异常进程排查",
        "检测隐藏进程、无对应二进制的可疑进程；通过 rkhunter/chkrootkit 扫描内核级后门；"
        "解析 /var/log/auth.log 发现暴力破解；扫描 /tmp /dev/shm 下可执行文件；"
        "关联进程与网络连接发现反向 Shell 与 C2；检查 crontab/systemd timer 持久化后门。",
        ("blue_team", "intrusion", "process"),
        "高",
        False,
        ("入侵排查", "Rootkit", "后门", "隐藏进程", "ThreatHunter", "rkhunter"),
        ("仅依赖 ps/top 排查",),
        ("rkhunter --check", "chkrootkit", "find /tmp -executable", "审计 crontab",),
    ),
    Playbook(
        "PB-BT-HUNT-02",
        "SSH 后门与用户审计",
        "对比 sshd 二进制哈希检测 SSH wrapper 后门；"
        "扫描 /etc/passwd /etc/shadow 异常 UID/GID 用户；审计 authorized_keys。",
        ("blue_team", "intrusion", "privilege"),
        "严重",
        True,
        ("SSH后门", "ssh", "passwd", "shadow", "authorized_keys", "用户审计"),
        ("信任默认 sshd",),
        ("sha256sum /usr/sbin/sshd", "检查 authorized_keys", "审计 UID=0 用户",),
    ),
    Playbook(
        "PB-BT-SIGMA-01",
        "Sigma 检测规则编写",
        "使用 Sigma 语法编写跨平台 SIEM 检测规则：Web 攻击(SQL注入/XSS)、"
        "横向移动(Pass-the-Hash/PsExec/WMI)、提权(UAC绕过/Token窃取)；"
        "PowerShell 混淆执行与 CobaltStrike Beacon 通信特征检测。",
        ("blue_team", "detection", "sigma"),
        "中",
        False,
        ("Sigma", "检测规则", "SIEM", "横向移动", "提权", "Web攻击"),
        ("仅用默认规则不更新",),
        ("按场景定制规则", "建立规则测试框架", "降低误报",),
    ),
    Playbook(
        "PB-BT-SIGMA-02",
        "攻击链检测与日志关联",
        "完整攻击链覆盖：侦察→漏洞利用→提权→横向移动→数据窃取；"
        "跨源日志(Windows/Linux/Network)关联分析攻击链；"
        "将 Sigma 规则转为 Splunk/ES/KQL 等目标平台格式。",
        ("blue_team", "detection", "log_analysis"),
        "高",
        False,
        ("攻击链", "日志关联", "Sigma", "检测覆盖率"),
        ("仅关注单点告警",),
        ("按攻击阶段串联规则", "分析告警时间线", "找出检测盲区",),
    ),
    Playbook(
        "PB-BT-SCAN-01",
        "巡风资产安全扫描",
        "自动化扫描内网存活主机与开放端口；识别常见 CVE 漏洞；"
        "对 SSH/FTP/MySQL/Redis 进行弱口令审计；Web 指纹识别(CMS/框架/组件版本)；"
        "定期扫描对比发现新增/消失的资产与端口。",
        ("blue_team", "asset_scan", "network"),
        "中",
        False,
        ("巡风", "xunfeng", "资产扫描", "弱口令", "漏洞扫描", "端口扫描"),
        ("一次性扫描不做持续监控",),
        ("建立资产清单", "设置周期性扫描", "更新漏洞库",),
    ),
    Playbook(
        "PB-BT-KB-01",
        "蓝队应急响应知识库",
        "Windows/Linux 入侵排查标准操作流程(SOP)；日志分析方法论(关键字段与技巧)；"
        "溯源工具链(IP定位/域名反查/样本分析)；常见攻击手法识别(APT/勒索/挖矿/蠕虫)；"
        "取证流程规范(证据保全链/内存取证/磁盘取证)。",
        ("blue_team", "knowledge_base", "incident_response"),
        "高",
        False,
        ("应急响应", "SOP", "日志分析", "溯源", "取证", "蓝队知识库"),
        ("缺少标准化应急流程",),
        ("建立自动化应急流程", "集成溯源工具链", "标准化安全报告",),
    ),
    Playbook(
        "PB-BT-API-01",
        "API 限流与 CC 防御",
        "基于 IP/用户/端点的请求频率控制；识别并阻止高频恶意请求(CC攻击)；"
        "当请求异常率过高时自动降级保护(熔断)；突发流量缓冲与排队；"
        "按业务场景配置不同限流规则。",
        ("blue_team", "api_security", "network"),
        "中",
        False,
        ("API限流", "CC攻击", "速率限制", "slowapi", "熔断"),
        ("不做任何限流保护",),
        ("关键接口添加限流", "IP维度限流", "添加请求日志审计",),
    ),
    Playbook(
        "PB-BT-API-02",
        "熔断器与故障隔离",
        "当下游服务故障率超阈值时自动断开调用(熔断器模式)；"
        "防止单个服务故障引发级联雪崩；熔断后定期尝试半开状态恢复；"
        "熔断时返回默认值或缓存数据(降级策略)。",
        ("blue_team", "api_security", "resilience"),
        "中",
        False,
        ("熔断", "pybreaker", "故障隔离", "级联故障", "降级"),
        ("无保护地调用外部依赖",),
        ("LLM API 调用添加熔断器", "MCP 工具添加熔断保护", "监控熔断事件",),
    ),
    Playbook(
        "PB-BT-LOG-01",
        "日志异常检测与行为分析",
        "基于统计模型识别日志中的异常模式；检测可疑登录(非工作时间/异常地域/多次失败)；"
        "越权操作检测(非预期的权限提升或资源访问)；按时间线还原攻击路径；"
        "建立正常行为基线，偏离即告警。",
        ("blue_team", "log_analysis", "detection"),
        "中",
        False,
        ("日志异常", "logdetective", "行为分析", "基线", "可疑登录"),
        ("仅查看日志不做分析",),
        ("建立行为基线", "集成到审计日志管道", "建立攻击特征库",),
    ),
    Playbook(
        "PB-BT-IR-01",
        "完整应急响应流程",
        "服务器被入侵的标准处置流程：接收报警→隔离主机→证据保全(内存/日志/进程/连接)→"
        "入侵分析→清除后门→恢复业务→事后报告。"
        "勒索病毒处置：断网隔离→检查感染范围→识别病毒家族→寻找解密工具→备份恢复→加固。",
        ("blue_team", "incident_response"),
        "严重",
        True,
        ("应急响应", "入侵处置", "勒索病毒", "隔离", "取证", "恢复"),
        ("未取证就重装系统",),
        ("保全证据链", "隔离网络", "生成事件报告",),
    ),
    Playbook(
        "PB-BT-LOG-02",
        "日志关联分析方法",
        "给定 Web 访问日志、系统认证日志、防火墙日志，提取关键字段按时间线排序，"
        "关联分析攻击路径确定入侵入口评估影响范围。"
        "Web日志关注: 请求路径/状态码/User-Agent/IP/参数；"
        "认证日志关注: 成功/失败/来源IP/时间/用户。",
        ("blue_team", "log_analysis"),
        "中",
        False,
        ("日志关联", "Web日志", "认证日志", "防火墙日志", "攻击路径"),
        ("仅看单类日志",),
        ("提取关键字段", "按时间线排序", "关联分析",),
    ),
    # ===== WAF / Web安全 =====
    Playbook(
        "PB-BT-WAF-01",
        "WebShell 检测与处置",
        "特征：文件内容含 eval/base64_decode/assert/system+外部变量；"
        "创建时间异常（凌晨/周末）；文件名伪装为 .jpg/.css；"
        "通过 Web 日志分析发现异常 POST 请求，定位上传漏洞入口。",
        ("blue_team", "webshell", "waf"),
        "严重",
        True,
        ("webshell", "eval", "base64", "system", "assert", "上传"),
        ("仅删文件不查入口",),
        ("查找近期修改 PHP/JSP 文件", "检查文件内容可疑函数", "追溯 Web 日志上传请求", "修复上传漏洞",),
    ),
    Playbook(
        "PB-BT-WAF-02",
        "ModSecurity WAF 规则部署",
        "开源 WAF 部署：OWASP CRS 核心规则集防御 SQL 注入/XSS/命令注入/路径遍历；"
        "规则配置：检测模式→阻断模式逐步切换；白名单排除正常业务路径；"
        "日志监控：查看 ModSecurity 审计日志了解攻击来源和 payload。",
        ("blue_team", "waf", "network"),
        "中",
        False,
        ("ModSecurity", "WAF", "CRS", "规则集", "SQL注入", "XSS"),
        ("直接启用阻断模式",),
        ("先以检测模式运行收集数据", "配置白名单减少误报", "逐步切换为阻断", "监控审计日志",),
    ),
    # ===== 审计与合规 =====
    Playbook(
        "PB-BT-AUDIT-01",
        "auditd 关键路径审计",
        "监控 /etc/passwd,/etc/shadow,/etc/sudoers 的写操作；"
        "监控 useradd/userdel/passwd 命令执行；"
        "监控网络配置、cron 变更、内核模块加载；"
        "使用 aureport 生成认证摘要、文件访问报告、异常报告。",
        ("blue_team", "audit", "privilege"),
        "高",
        False,
        ("auditd", "审计规则", "aureport", "ausearch", "文件监控"),
        ("只启用默认审计规则",),
        ("配置关键路径审计规则", "周期性生成审计报告", "设置审计日志告警",),
    ),
    Playbook(
        "PB-BT-AUDIT-02",
        "文件完整性监控 (AIDE/Tripwire)",
        "AIDE 初始化基线数据库 → 定期检查文件变更(哈希/权限/大小)；"
        "核心监控目录: /boot,/bin,/sbin,/etc,/usr/bin,/usr/sbin；"
        "排除频繁变化目录: /var/log,/proc；变更后更新基线确认合法修改。",
        ("blue_team", "audit", "monitoring_gap"),
        "中",
        False,
        ("AIDE", "文件完整性", "哈希", "基线", "Tripwire", "篡改"),
        ("从不更新基线导致告警堆积",),
        ("aide --init 建立基线", "定期 aide --check", "合法变更后 --update", "集成到告警系统",),
    ),
    # ===== 内核与系统加固 =====
    Playbook(
        "PB-BT-SYS-01",
        "内核安全参数加固",
        "关键 sysctl 参数: net.ipv4.tcp_syncookies=1 防SYN Flood；"
        "net.ipv4.conf.all.rp_filter=1 防IP欺骗；"
        "kernel.randomize_va_space=2 启用KASLR；"
        "kernel.dmesg_restrict=1 + kernel.kptr_restrict=2 防止内核信息泄露；"
        "禁止源路由/ICMP重定向，限制 ptrace 作用域。",
        ("blue_team", "privilege", "system"),
        "高",
        True,
        ("sysctl", "内核参数", "KASLR", "iptables", "加固", "安全基线"),
        ("不经测试直接应用到生产",),
        ("逐条验证参数效果", "在测试环境先行验证", "记录变更前后对比", "注册为 CIS 检查项",),
    ),
    Playbook(
        "PB-BT-SYS-02",
        "SELinux/AppArmor 强制访问控制",
        "SELinux 三种模式: Enforcing(强制)/Permissive(仅记录)/Disabled(关闭)；"
        "使用 audit2allow 生成自定义策略允许正常业务；"
        "AppArmor 配置文件在 /etc/apparmor.d/ 管理进程权限；"
        "生产环境必须保持 Enforcing，开发环境可用 Permissive 定位问题。",
        ("blue_team", "privilege", "system"),
        "高",
        True,
        ("SELinux", "AppArmor", "强制访问控制", "MAC", "getenforce", "aa-status"),
        ("遇到拒绝就 setenforce 0",),
        ("查看 AVC 日志定位原因", "用 audit2allow 生成精准策略", "保持 Enforcing",),
    ),
    # ===== 网络 =====
    Playbook(
        "PB-BT-NET-03",
        "iptables/nftables 安全策略",
        "默认策略: INPUT/FORWARD DROP, OUTPUT ACCEPT；"
        "允许 ESTABLISHED/RELATED 回包；限制 SSH 来源 IP 段；"
        "SYN Flood 限速: iptables --limit 1/s --limit-burst 3；"
        "日志记录并定期分析 DROP 条目发现攻击模式。",
        ("blue_team", "network"),
        "高",
        True,
        ("iptables", "nftables", "防火墙", "策略", "限速", "DROP"),
        ("iptables -F 清空所有规则",),
        ("先导出当前规则备份", "逐条添加白名单规则", "测试后再保存", "定期审计规则列表",),
    ),
    Playbook(
        "PB-BT-IDS-01",
        "Suricata/Snort IDS 部署",
        "网络入侵检测部署: 配置 HOME_NET 变量 → 加载规则集(Emerging Threats/ET Pro) →"
        "输出 eve.json 到 Elasticsearch → Kibana 可视化告警；"
        "规则更新: suricata-update 保持特征库最新；"
        "IPS 模式: 在检测稳定后启用 inline 阻断。",
        ("blue_team", "ids", "network"),
        "中",
        False,
        ("Suricata", "Snort", "IDS", "IPS", "特征库", "eve.json"),
        ("不更新规则集", "未经测试启用阻断模式",),
        ("定期 suricata-update", "监控误报率", "逐步切换检测→阻断",),
    ),
    # ===== 威胁情报与溯源 =====
    Playbook(
        "PB-BT-TI-01",
        "IOC 威胁情报自动化匹配",
        "IOC 来源: 开源情报(MISP/OTX)、商业威胁情报、自研捕获；"
        "检测目标: 进程网络连接 IP、DNS 解析域名、文件哈希、HTTP User-Agent；"
        "自动化流程: 每4小时拉取最新IOC → 对比系统日志 → 命中则生成告警。",
        ("blue_team", "intrusion", "detection"),
        "中",
        False,
        ("IOC", "威胁情报", "MISP", "OTX", "自动化", "域名"),
        ("仅手工比对IOC",),
        ("定时拉取威胁情报", "自动化匹配系统日志", "命中后联动应急响应",),
    ),
    Playbook(
        "PB-BT-TI-02",
        "YARA 规则恶意样本检测",
        "YARA 规则结构: meta(描述/作者/日期) + strings(匹配字符串) + condition(逻辑)；"
        "扫描目标: 可疑进程内存、磁盘文件、Web 上传目录；"
        "覆盖类型: Rootkit、Webshell、挖矿程序、勒索软件。",
        ("blue_team", "detection", "intrusion"),
        "中",
        False,
        ("YARA", "样本分析", "签名", "规则", "yara", "匹配"),
        ("仅依赖文件名/路径判断",),
        ("编写专业 YARA 规则", "定时扫描 /tmp /dev/shm", "对 Web 项目部署定期扫描",),
    ),
)

PLAYBOOK_BY_ID = {p.id: p for p in PLAYBOOKS}
