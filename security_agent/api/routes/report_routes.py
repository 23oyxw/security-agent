"""扫描报告 + 任务/命令分析（支持上传）。"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from security_agent.api.deps import get_current_user
from security_agent.auth.models import User
from security_agent.config import REPORTS_DIR, ensure_data_dirs
from security_agent.security.response_policy import apply_response_policy

router = APIRouter()

_FILENAME_RE = re.compile(r"^security_report_[\w.-]+\.(html|json|txt)$")
_ANALYSIS_DIR = Path(__file__).resolve().parents[3] / "data" / "analysis"
_MAX_UPLOAD = 512 * 1024


def _safe_report_path(filename: str) -> Path:
    if not _FILENAME_RE.match(filename):
        raise HTTPException(400, "非法报告文件名")
    ensure_data_dirs()
    path = (REPORTS_DIR / filename).resolve()
    if not str(path).startswith(str(REPORTS_DIR.resolve())):
        raise HTTPException(400, "路径越界")
    return path


def _save_analysis(record: dict) -> None:
    _ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    aid = record.get("analysis_id", "unknown")
    path = _ANALYSIS_DIR / f"{aid}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")


@router.get("/")
async def list_reports(user: User = Depends(get_current_user)):
    """列出 data/reports 下最近生成的扫描报告。"""
    ensure_data_dirs()
    items = []
    for fp in sorted(REPORTS_DIR.glob("security_report_*.html"), reverse=True)[:30]:
        items.append({
            "filename": fp.name,
            "path": str(fp),
            "size_bytes": fp.stat().st_size,
            "modified_at": fp.stat().st_mtime,
        })
    analyses = []
    if _ANALYSIS_DIR.is_dir():
        for fp in sorted(_ANALYSIS_DIR.glob("*.json"), reverse=True)[:20]:
            try:
                rec = json.loads(fp.read_text(encoding="utf-8"))
                analyses.append({
                    "analysis_id": rec.get("analysis_id"),
                    "intent": rec.get("intent"),
                    "created_at": rec.get("created_at"),
                    "risk_level": (rec.get("risk") or {}).get("level"),
                })
            except Exception:
                continue
    return apply_response_policy({"reports": items, "total": len(items), "analyses": analyses}, user)


@router.post("/analyze")
async def analyze_prompt_or_file(
    prompt: str = Form(""),
    file: Optional[UploadFile] = File(None),
    user: User = Depends(get_current_user),
):
    """Prompt/命令任务分析 — 主线分层 + 工作流匹配 + 学术参照（支持上传）。"""
    from security_agent.analysis.task_analyzer import analyze_task

    excerpt = None
    fname = None
    if file and file.filename:
        raw = await file.read()
        if len(raw) > _MAX_UPLOAD:
            raise HTTPException(400, f"文件超过 {_MAX_UPLOAD // 1024}KB 限制")
        fname = file.filename
        try:
            excerpt = raw.decode("utf-8")
        except UnicodeDecodeError:
            excerpt = raw.decode("utf-8", errors="replace")

    if not (prompt or "").strip() and not excerpt:
        raise HTTPException(400, "请提供 prompt 或上传文件")

    record = analyze_task(
        prompt,
        filename=fname,
        file_excerpt=excerpt,
        user_role=user.role,
    )
    record["analyzed_by"] = user.username
    _save_analysis(record)
    return apply_response_policy(record, user)


@router.get("/analysis/{analysis_id}")
async def get_analysis(analysis_id: str, user: User = Depends(get_current_user)):
    path = _ANALYSIS_DIR / f"{analysis_id}.json"
    if not path.is_file():
        raise HTTPException(404, "分析记录不存在")
    record = json.loads(path.read_text(encoding="utf-8"))
    return apply_response_policy(record, user)


@router.get("/files/{filename}")
async def download_report_file(filename: str, user: User = Depends(get_current_user)):
    """下载单份扫描报告（HTML 等）。"""
    path = _safe_report_path(filename)
    if not path.is_file():
        raise HTTPException(404, "报告不存在")
    media = "text/html" if path.suffix == ".html" else "application/json"
    if path.suffix == ".txt":
        media = "text/plain"
    return FileResponse(path, media_type=media, filename=path.name)
