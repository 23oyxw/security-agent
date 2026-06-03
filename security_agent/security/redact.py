"""敏感信息自动打码 — 密码、密钥、Token、登录凭证."""

from __future__ import annotations

import re
from typing import Any

# JSON/字典字段名（小写匹配）
SENSITIVE_KEYS = frozenset(
    {
        "password",
        "passwd",
        "pwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "authorization",
        "credential",
        "private_key",
        "llm_api_key",
        "deepseek_api_key",
        "cursor_api_key",
    }
)

_MASK = "***"

# key=value / key: value
_KV_PATTERN = re.compile(
    r"(?i)\b(password|passwd|pwd|secret|api[_-]?key|access[_-]?token|refresh[_-]?token|token|authorization)\s*[=:]\s*([^\s'\";,]+|'[^']*'|\"[^\"]*\")"
)

# OpenAI/DeepSeek/Cursor 密钥形态
_SK_PATTERN = re.compile(r"\bsk-[a-zA-Z0-9]{8,}\b")
_CRSR_PATTERN = re.compile(r"\bcrsr_[a-zA-Z0-9]{8,}\b")
_BEARER_PATTERN = re.compile(r"\bBearer\s+[A-Za-z0-9._\-+/=]{8,}\b", re.IGNORECASE)

# auth.log: password for user / Failed password
_AUTH_PASSWORD_SEGMENT = re.compile(
    r"(?i)(password\s+(?:for|accepted|failed)\s+(?:invalid user\s+)?\S+|"
    r"Failed\s+password\s+for\s+(?:invalid user\s+)?\S+)",
)

# URL 中的 user:pass@
_URL_CREDS = re.compile(r"([a-zA-Z][a-zA-Z0-9+.-]*://)([^@\s/]+):([^@\s/]+)@")


def redact_text(text: str, *, mask_char: str = "*") -> str:
    if not text:
        return text
    out = text
    mask = mask_char * 3 if len(mask_char) == 1 else _MASK

    out = _KV_PATTERN.sub(lambda m: f"{m.group(1)}={mask}", out)
    out = _SK_PATTERN.sub("sk-" + mask, out)
    out = _CRSR_PATTERN.sub("crsr_" + mask, out)
    out = _BEARER_PATTERN.sub("Bearer " + mask, out)
    out = _URL_CREDS.sub(lambda m: f"{m.group(1)}{m.group(2)}:{mask}@", out)

    # auth 行：保留结构，隐藏可能跟在后面的凭证片段
    if "password" in out.lower() or "auth.log" in out.lower():
        out = re.sub(
            r"(?i)(failed\s+password\s+for\s+(?:invalid user\s+)?)(\S+)",
            r"\1" + mask,
            out,
        )
        out = re.sub(
            r"(?i)(accepted\s+(?:password|publickey)\s+for\s+)(\S+)(\s+from\s+)",
            r"\1" + mask + r"\3",
            out,
        )

    return out


def redact_dict(data: Any, *, depth: int = 0) -> Any:
    if depth > 12:
        return data
    if isinstance(data, dict):
        out: dict[str, Any] = {}
        for k, v in data.items():
            key_lower = str(k).lower().replace("-", "_")
            if key_lower in SENSITIVE_KEYS:
                out[k] = _MASK
            else:
                out[k] = redact_dict(v, depth=depth + 1)
        return out
    if isinstance(data, list):
        return [redact_dict(x, depth=depth + 1) for x in data]
    if isinstance(data, str):
        return redact_text(data)
    return data


def redact_command(cmd: str) -> str:
    """终端命令行展示打码."""
    return redact_text(cmd)
