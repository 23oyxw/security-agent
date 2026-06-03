"""Platform-aware configuration."""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
AUDIT_LOG_PATH = DATA_DIR / "audit.log"
REPORTS_DIR = DATA_DIR / "reports"

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")

# 通用 LLM（OpenAI 兼容）— 优先 LLM_*，回退 DEEPSEEK_*
LLM_API_KEY = (
    os.getenv("LLM_API_KEY", "")
    or os.getenv("DEEPSEEK_API_KEY", "")
    or ""
)
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "") or os.getenv(
    "DEEPSEEK_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1"
)
# 直连 MiMo 时推荐 mimo-v2.5；Pro 需 Key 支持。经 LiteLLM 请 USE_LITELLM_PROXY=true 且 LLM_MODEL=mimo-chat
LLM_MODEL = os.getenv("LLM_MODEL", "") or os.getenv("DEEPSEEK_MODEL", "mimo-v2.5")


def using_litellm_proxy() -> bool:
    """是否经 LiteLLM 代理（.env 显式开启或 BASE_URL 指向 :4000）."""
    if USE_LITELLM_PROXY:
        return True
    url = (LLM_BASE_URL or BUDGET_BASE_URL or "").lower()
    return ":4000" in url or "/v1" in url and "localhost" in url and "4000" in url


# LiteLLM model_list 中的 model_name（客户端应传这些，而非 deepseek-v4-flash）
LITELLM_MODEL_ALIASES: dict[str, str] = {
    "mimo-v2.5-pro": "mimo-chat",
    "mimo-v2.5": "mimo-chat",
    "mimo-v2": "mimo-fast",
    "mimo-chat": "mimo-chat",
    "mimo-fast": "mimo-fast",
    "deepseek-v4-flash": "deepseek-chat",
    "deepseek-v4-pro": "deepseek-reasoner",
    "deepseek-chat": "deepseek-chat",
    "deepseek-reasoner": "deepseek-reasoner",
}


def resolve_llm_model(model: str | None = None) -> str:
    """解析直连 MiMo/DeepSeek 的 model id；Pro 在 Key 不支持时自动降为 v2.5."""
    m = (model or LLM_MODEL or "mimo-v2.5").strip().lower()
    if using_litellm_proxy():
        return LITELLM_MODEL_ALIASES.get(m, m)
    if m == "mimo-v2.5-pro":
        if os.getenv("LLM_USE_PRO", "").lower() not in ("1", "true", "yes"):
            return "mimo-v2.5"
    return m


def resolve_agent_model(model: str | None = None) -> str:
    """Agent 对话用 model：LiteLLM 场景映射为 mimo-chat / mimo-fast."""
    return resolve_llm_model(model)


def resolve_fallback_model(primary: str | None = None) -> tuple[str, str, str]:
    """返回 (fallback_model, base_url, api_key) 供 FallbackClient 使用."""
    if using_litellm_proxy():
        fb = os.getenv("LITELLM_FALLBACK_MODEL", "deepseek-chat")
        key = LITELLM_MASTER_KEY or LLM_API_KEY or "sk-1234"
        return fb, LITELLM_PROXY_URL, key
    fb = BUDGET_MODEL or "deepseek-v4-flash"
    return fb, BUDGET_BASE_URL or "https://api.deepseek.com/v1", BUDGET_API_KEY or LLM_API_KEY

# 兼容旧代码
DEEPSEEK_API_KEY = LLM_API_KEY
DEEPSEEK_BASE_URL = LLM_BASE_URL
DEEPSEEK_MODEL = LLM_MODEL

# 自主任务 Agent（DeepSeek V4 Pro — 深度规划/分析/决策）
AUTONOMOUS_API_KEY = os.getenv("AUTONOMOUS_API_KEY", "") or os.getenv("DEEPSEEK_REASONER_API_KEY", "")
AUTONOMOUS_BASE_URL = os.getenv("AUTONOMOUS_BASE_URL", "") or os.getenv(
    "DEEPSEEK_REASONER_BASE_URL", "https://api.deepseek.com/v1"
)
AUTONOMOUS_MODEL = os.getenv("AUTONOMOUS_MODEL", "") or os.getenv(
    "DEEPSEEK_REASONER_MODEL", "deepseek-v4-pro"
)

# RAG 向量嵌入（OpenAI text-embedding-3-small 或 DeepSeek 等兼容接口）
# 注意：text-embedding-3-small 是 OpenAI 模型，需要 OpenAI API Key；
#       如果用 DeepSeek API，请改 EMBEDDING_MODEL 为 DeepSeek 支持的嵌入模型。
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "") or os.getenv(
    "DEEPSEEK_EMBEDDING_API_KEY", ""
)
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "") or os.getenv(
    "DEEPSEEK_EMBEDDING_BASE_URL", "https://api.openai.com/v1"
)

# 批量/高频任务 Agent — DeepSeek V4 Flash（性价比之王，批量生成/测试用例/文档）
BUDGET_API_KEY = os.getenv("BUDGET_API_KEY", "") or os.getenv("DEEPSEEK_API_KEY", "")
BUDGET_BASE_URL = os.getenv("BUDGET_BASE_URL", "") or os.getenv(
    "DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"
)
BUDGET_MODEL = os.getenv("BUDGET_MODEL", "") or os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

# ---- LiteLLM Proxy 统一路由 ----
# 使用 LiteLLM 集中管理多模型路由、fallback、成本追踪
# 开启后所有模型请求通过本地代理，便于统一监控
USE_LITELLM_PROXY = os.getenv("USE_LITELLM_PROXY", "false").lower() in ("1", "true", "yes")
LITELLM_PROXY_URL = os.getenv("LITELLM_PROXY_URL", "http://localhost:4000/v1")
LITELLM_MASTER_KEY = os.getenv("LITELLM_MASTER_KEY", "")  # 可选，用于代理认证

# 当启用 LiteLLM Proxy 时，覆盖默认配置
if USE_LITELLM_PROXY:
    LLM_BASE_URL = LITELLM_PROXY_URL
    AUTONOMOUS_BASE_URL = LITELLM_PROXY_URL
    BUDGET_BASE_URL = LITELLM_PROXY_URL
    EMBEDDING_BASE_URL = LITELLM_PROXY_URL
    # 客户端 model 必须为 litellm model_name，不是底层 id
    if LLM_MODEL.lower() in ("mimo-v2.5", "mimo-v2.5-pro", "deepseek-v4-flash", "deepseek-v4-pro"):
        LLM_MODEL = LITELLM_MODEL_ALIASES.get(LLM_MODEL.lower(), "mimo-chat")
    if BUDGET_MODEL.lower() in ("deepseek-v4-flash", "deepseek-v4-pro"):
        BUDGET_MODEL = LITELLM_MODEL_ALIASES.get(BUDGET_MODEL.lower(), "deepseek-chat")
    if AUTONOMOUS_MODEL.lower() in ("deepseek-v4-pro", "deepseek-v4-flash"):
        AUTONOMOUS_MODEL = LITELLM_MODEL_ALIASES.get(
            AUTONOMOUS_MODEL.lower(), "deepseek-reasoner"
        )
    # API Key 使用 master_key 或 sk-1234（默认）
    if LITELLM_MASTER_KEY:
        LLM_API_KEY = LITELLM_MASTER_KEY
        AUTONOMOUS_API_KEY = LITELLM_MASTER_KEY
        BUDGET_API_KEY = LITELLM_MASTER_KEY
        EMBEDDING_API_KEY = LITELLM_MASTER_KEY
    elif not LLM_API_KEY:
        LLM_API_KEY = "sk-1234"

# Cursor 密钥（crsr_ 开头，供扩展功能；不能用于 LLM 接口）
CURSOR_API_KEY = os.getenv("CURSOR_API_KEY", "")

# ---- 模型预设（供 UI 切换）----
# MiMo 可用模型（通过 /v1/models 查询）:
#   mimo-v2.5-pro (旗舰 agent)、mimo-v2.5 (标准快速)、mimo-v2-omni (多模态)
#   mimo-v2.5-tts* / mimo-v2-tts (TTS 音频，安全运维不使用)

# 基础预设
_BASE_PRESETS: dict[str, dict[str, str]] = {
    "MiMo v2.5 Pro（Agent 旗舰）": {
        "api_key": LLM_API_KEY,
        "base_url": LLM_BASE_URL,
        "model": "mimo-v2.5-pro",
    },
    "MiMo v2.5（快速轻量）": {
        "api_key": LLM_API_KEY,
        "base_url": LLM_BASE_URL,
        "model": "mimo-v2.5",
    },
    "DeepSeek V4 Flash（批量/高频）": {
        "api_key": BUDGET_API_KEY,
        "base_url": BUDGET_BASE_URL,
        "model": BUDGET_MODEL or "deepseek-v4-flash",
    },
    "DeepSeek V4 Pro（深度推理）": {
        "api_key": AUTONOMOUS_API_KEY,
        "base_url": AUTONOMOUS_BASE_URL,
        "model": AUTONOMOUS_MODEL or "deepseek-v4-pro",
    },
}

# LiteLLM Proxy 预设（当启用代理时使用 LiteLLM 的 model_name）
_LITELLM_PRESETS: dict[str, dict[str, str]] = {
    "LiteLLM: MiMo Chat（Agent）": {
        "api_key": LITELLM_MASTER_KEY or LLM_API_KEY,
        "base_url": LITELLM_PROXY_URL,
        "model": "mimo-chat",  # litellm_config.yaml 中定义的 model_name
    },
    "LiteLLM: MiMo Fast（轻量）": {
        "api_key": LITELLM_MASTER_KEY or LLM_API_KEY,
        "base_url": LITELLM_PROXY_URL,
        "model": "mimo-fast",
    },
    "LiteLLM: DeepSeek V4 Flash（批量）": {
        "api_key": LITELLM_MASTER_KEY or BUDGET_API_KEY,
        "base_url": LITELLM_PROXY_URL,
        "model": "deepseek-chat",
    },
    "LiteLLM: DeepSeek V4 Pro（深度）": {
        "api_key": LITELLM_MASTER_KEY or AUTONOMOUS_API_KEY,
        "base_url": LITELLM_PROXY_URL,
        "model": "deepseek-reasoner",
    },
}

# 动态选择预设
if USE_LITELLM_PROXY:
    MODEL_PRESETS = _LITELLM_PRESETS
    DEFAULT_MODEL_PRESET = "LiteLLM: MiMo Chat（Agent）"
else:
    MODEL_PRESETS = _BASE_PRESETS
    DEFAULT_MODEL_PRESET = "MiMo v2.5 Pro（Agent 旗舰）"

HIGH_RISK_PROCESS_NAMES = frozenset(
    {"nc", "ncat", "nmap", "masscan", "hydra", "sqlmap", "metasploit", "msfconsole"}
)
HIGH_RISK_CMD_PATTERNS = (
    "rm -rf /",
    "chmod 777",
    ":(){ :|:& };:",
    "| bash",
    "| sh",
    "dd if=",
)
# 进程名与高危工具同名但属系统/日常 — 避免误报
HIGH_RISK_PROCESS_ALLOWLIST = frozenset(
    {
        "sync",
        "systemd",
        "systemd-journald",
        "systemd-logind",
        "systemd-udevd",
        "kworker",
        "ksoftirqd",
        "migration",
        "rcu_sched",
        "sshd",
        "postgres",
        "postmaster",
        "mysqld",
        "redis-server",
        "nginx",
        "java",
        "node",
        "python",
        "python3",
        "streamlit",
        "uvicorn",
        "gunicorn",
        "docker",
        "containerd",
        "containerd-shim",
        "bash",
        "sh",
    }
)
# 命令行包含以下片段时跳过进程名/工具 token 检测（演练诱饵等）
HIGH_RISK_SAFE_CMDLINE_FRAGMENTS = (
    "security_agent/demo/decoy.py",
    "scripts/demo_risk.py",
)
# 仅用于日志/文件查看的只读命令 — 其后的高危词视为检索关键字而非执行
HIGH_RISK_LOG_READ_PREFIXES = frozenset(
    {
        "grep",
        "egrep",
        "fgrep",
        "cat",
        "head",
        "tail",
        "less",
        "more",
        "strings",
        "zgrep",
        "zcat",
        "awk",
        "sed",
    }
)

if IS_WINDOWS:
    SENSITIVE_PATHS = [
        r"C:\Windows\System32\config\SAM",
        r"C:\ProgramData\ssh\administrators_authorized_keys",
    ]
else:
    SENSITIVE_PATHS = [
        "/etc/shadow",
        "/etc/passwd",
        "/root/.ssh/id_rsa",
        "/var/log/auth.log",
    ]


def llm_configured() -> bool:
    """检查是否有至少一个模型 API Key 已配置."""
    for key in (LLM_API_KEY, BUDGET_API_KEY, AUTONOMOUS_API_KEY):
        if key and key not in ("your_key_here", "sk-your-key-here"):
            return True
    return False


def litellm_status() -> dict[str, bool | str]:
    """检查 LiteLLM 代理状态.

    Returns:
        {
            "enabled": bool,      # .env 中是否启用
            "running": bool,      # 代理是否实际运行
            "url": str,           # 代理地址
            "healthy": bool,      # 健康检查是否通过
        }
    """
    status = {
        "enabled": USE_LITELLM_PROXY,
        "running": False,
        "url": LITELLM_PROXY_URL,
        "healthy": False,
    }

    if not USE_LITELLM_PROXY:
        return status

    # 优先检查 Docker 容器（当前主要部署方式）
    try:
        import subprocess
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=security-agent-litellm",
             "--format", "{{.Status}}"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0 and "Up" in result.stdout:
            status["running"] = True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    # 回退检查 PID 文件（兼容旧的直接进程部署方式）
    if not status["running"]:
        pid_file = DATA_DIR / ".litellm.pid"
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                os.kill(pid, 0)  # 信号 0 只检查，不发送
                status["running"] = True
            except (ValueError, OSError, ProcessLookupError):
                status["running"] = False

    # 简单 HTTP 检查
    if status["running"]:
        try:
            import urllib.request
            import urllib.error
            import socket

            # 设置短超时
            timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(1)

            try:
                # 尝试访问 /v1/models 端点
                urllib.request.urlopen(
                    f"{LITELLM_PROXY_URL}/models",
                    timeout=1
                )
                status["healthy"] = True
            except (urllib.error.URLError, socket.timeout):
                status["healthy"] = False
            finally:
                socket.setdefaulttimeout(timeout)
        except Exception:
            status["healthy"] = False

    return status


def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "alerts").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "logs").mkdir(parents=True, exist_ok=True)


def python_executable() -> str:
    return os.environ.get("SECURITY_AGENT_PYTHON", sys.executable)


def mcp_server_script() -> str:
    return str(PROJECT_ROOT / "security_agent" / "knowledge" / "mcp" / "server.py")


# RAG / 向量检索（与 LLM 同 API；关闭则仅关键词检索）
RAG_USE_EMBEDDINGS = os.getenv("RAG_USE_EMBEDDINGS", "true").lower() in ("1", "true", "yes")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

# 对 0.0.0.0 / :: 监听时视为高风险的端口（数据库/调试/远控等）
# 登录审计日志（麒麟/RedHat 常用 secure）
AUTH_LOG_PATHS = [
    "/var/log/auth.log",
    "/var/log/secure",
]
AUTH_FAIL_BURST_THRESHOLD = int(os.getenv("AUTH_FAIL_BURST_THRESHOLD", "5"))

# P2 监控开关
MONITOR_AUTH_ENABLED = os.getenv("MONITOR_AUTH_ENABLED", "true").lower() in ("1", "true", "yes")
MONITOR_LISTEN_ENABLED = os.getenv("MONITOR_LISTEN_ENABLED", "true").lower() in ("1", "true", "yes")
MONITOR_CRON_ENABLED = os.getenv("MONITOR_CRON_ENABLED", "true").lower() in ("1", "true", "yes")

EXPOSED_RISKY_PORTS = frozenset(
    {
        23,
        445,
        1433,
        1521,
        3306,
        3389,
        4444,
        5432,
        5900,
        6379,
        9200,
        11211,
        27017,
    }
)


# Dify webhook 签名校验（生产建议开启）
SIGNING_ENABLED = os.getenv("SIGNING_ENABLED", "false").lower() in ("1", "true", "yes")
SIGNING_KEY = os.getenv("SIGNING_KEY", "") or os.getenv("AGENT_SIGNING_KEY", "")

# 弹性：请求预算与熔断
REQUEST_BUDGET_SEC = float(os.getenv("REQUEST_BUDGET_SEC", "120"))
CIRCUIT_FAILURE_THRESHOLD = int(os.getenv("CIRCUIT_FAILURE_THRESHOLD", "5"))
CIRCUIT_OPEN_SEC = float(os.getenv("CIRCUIT_OPEN_SEC", "60"))

# 人工审批（S4）超时 — 超时自动标记为 timeout，禁止执行
CONFIRMATION_TIMEOUT_SEC = int(os.getenv("CONFIRMATION_TIMEOUT_SEC", "3600"))

# ReAct 上下文治理（防止循环越长上下文越膨胀）
REACT_MAX_TOOL_ROUNDS = int(os.getenv("REACT_MAX_TOOL_ROUNDS", "8"))
REACT_TOOL_OBSERVATION_MAX_CHARS = int(os.getenv("REACT_TOOL_OBSERVATION_MAX_CHARS", "2000"))
REACT_GROUNDING_MAX_CHARS = int(os.getenv("REACT_GROUNDING_MAX_CHARS", "2400"))
REACT_PERCEPTION_MAX_CHARS = int(os.getenv("REACT_PERCEPTION_MAX_CHARS", "2200"))
REACT_PLANNER_NOTE_MAX_CHARS = int(os.getenv("REACT_PLANNER_NOTE_MAX_CHARS", "800"))
REACT_CHAIN_OUTPUT_MAX_CHARS = int(os.getenv("REACT_CHAIN_OUTPUT_MAX_CHARS", "3500"))
MAX_HISTORY_ROUNDS = int(os.getenv("MAX_HISTORY_ROUNDS", "15"))


def platform_label() -> str:
    if IS_WINDOWS:
        return "Windows"
    if "kylin" in platform.platform().lower() or Path("/etc/kylin-release").exists():
        return "银河麒麟"
    if IS_LINUX:
        return "Linux"
    return platform.system()
