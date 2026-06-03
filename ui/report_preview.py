"""报告预览 — 浅色可读样式（适配 Streamlit 深色主题）."""

from __future__ import annotations

import json
import re
from pathlib import Path

_BODY_PLACEHOLDER = "@@REPORT_BODY@@"

# 使用占位符替换，避免报告 HTML 内 CSS 花括号与 str.format 冲突导致乱码
REPORT_IFRAME_SHELL = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="color-scheme" content="light">
<style>
  html, body {{
    margin: 0; padding: 0;
    background: #eef2f7 !important;
    color-scheme: light;
  }}
  .report-shell {{
    background: #ffffff;
    color: #1e293b;
    padding: 20px 24px 28px;
    font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    font-size: 14px;
    line-height: 1.5;
    min-height: 100%;
    box-sizing: border-box;
  }}
  .report-shell h1 {{
    color: #0f172a;
    font-size: 1.5rem;
    margin: 0 0 12px;
    border-bottom: 2px solid #1565c0;
    padding-bottom: 8px;
  }}
  .report-shell p {{
    color: #475569;
    margin: 6px 0;
  }}
  .report-shell table {{
    border-collapse: collapse;
    width: 100%;
    margin-top: 12px;
    background: #fff;
  }}
  .report-shell th {{
    background: #1565c0;
    color: #ffffff;
    padding: 10px 12px;
    text-align: left;
    font-weight: 600;
  }}
  .report-shell td {{
    border: 1px solid #e2e8f0;
    padding: 8px 12px;
    color: #334155;
    vertical-align: top;
  }}
  .report-shell tr:nth-child(even) td {{
    background: #f8fafc;
  }}
  .report-shell tr:hover td {{
    background: #eff6ff;
  }}
</style>
</head>
<body>
<div class="report-shell">
{_BODY_PLACEHOLDER}
</div>
</body>
</html>"""


def _extract_body(html_text: str) -> str:
    m = re.search(r"<body[^>]*>([\s\S]*)</body>", html_text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return html_text.strip()


def wrap_report_for_preview(html_text: str) -> str:
    inner = _extract_body(html_text)
    # 去掉原报告内嵌 style，避免与外壳冲突；保留表格结构
    inner = re.sub(r"<style[\s\S]*?</style>", "", inner, flags=re.IGNORECASE)
    inner = re.sub(r"<script[\s\S]*?</script>", "", inner, flags=re.IGNORECASE)
    return REPORT_IFRAME_SHELL.replace(_BODY_PLACEHOLDER, inner)


def load_report_json(html_path: Path) -> dict | None:
    json_path = html_path.with_suffix(".json")
    if json_path.exists():
        try:
            return json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
    return None


def render_report_html(preview_html: str, *, height: int = 560) -> None:
    """Streamlit 中安全渲染报告 HTML（固定高度、可滚动）."""
    import inspect

    import streamlit as st
    import streamlit.components.v1 as components

    # 部分版本有 st.html 但不支持 height（会报 HtmlMixin.html() unexpected keyword）
    use_st_html = False
    if hasattr(st, "html"):
        try:
            params = inspect.signature(st.html).parameters
            use_st_html = "height" in params
        except (TypeError, ValueError):
            use_st_html = False

    if use_st_html:
        try:
            st.html(preview_html, height=height, scrolling=True)
            return
        except TypeError:
            pass

    components.html(preview_html, height=height, scrolling=True)
