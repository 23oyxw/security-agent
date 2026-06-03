"""清洗助手回复中的模型伪工具标记与乱码 Markdown."""

from __future__ import annotations

import re

# MiMo / 部分模型在正文里输出的伪 tool 标记
_DSML_BLOCK = re.compile(
    r"<\|?\|?DSML\|?\|?>.*?(?:</\|?\|?DSML\|?\|?>|$)",
    re.IGNORECASE | re.DOTALL,
)
_DSML_LINE = re.compile(r"^.*DSML.*$", re.IGNORECASE | re.MULTILINE)
_XML_TOOL = re.compile(
    r"<(?:tool_calls|invoke|function_call)[^>]*>.*?</(?:tool_calls|invoke|function_call)>",
    re.IGNORECASE | re.DOTALL,
)


def is_markup_heavy(text: str) -> bool:
    if not text or not text.strip():
        return True
    t = text.strip()
    if "DSML" in t or "tool_calls" in t.lower():
        if len(re.sub(r"[\s\d\W]+", "", t)) < 40:
            return True
        # DSML 占主导
        clean = _DSML_BLOCK.sub("", t)
        clean = _DSML_LINE.sub("", clean)
        if len(clean.strip()) < max(80, len(t) * 0.15):
            return True
    return False


def sanitize_assistant_reply(text: str) -> str:
    if not text:
        return ""
    out = text
    out = _DSML_BLOCK.sub("", out)
    out = _XML_TOOL.sub("", out)
    out = _DSML_LINE.sub("", out)
    # 修复 ``bash 等未闭合围栏
    out = re.sub(r"`{2,}(bash|sh|shell)\s*\n", "```\\1\n", out, flags=re.IGNORECASE)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def fallback_reply_when_markup_only(user_message: str) -> str:
    return (
        "刚才的模型回复格式异常（工具标记混入了正文），未能正常展示。\n\n"
        "请换一种说法重试，例如：\n"
        "· **关闭 VNC**：`安全执行 killall vino-server`\n"
        "· **拦截进程**：`拦截进程 4911`\n"
        "· **生成报告**：`生成扫描报告`\n\n"
        f"您刚才说的是：「{user_message[:80]}」"
    )
