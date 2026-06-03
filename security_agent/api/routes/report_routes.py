"""扫描报告文件下载（HTML / JSON）。"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from security_agent.api.deps import get_current_user
from security_agent.auth.models import User
from security_agent.config import REPORTS_DIR, ensure_data_dirs

router = APIRouter()

_FILENAME_RE = re.compile(r"^security_report_[\w.-]+\.(html|json|txt)$")


def _safe_report_path(filename: str) -> Path:
    if not _FILENAME_RE.match(filename):
        raise HTTPException(400, "非法报告文件名")
    ensure_data_dirs()
    path = (REPORTS_DIR / filename).resolve()
    if not str(path).startswith(str(REPORTS_DIR.resolve())):
        raise HTTPException(400, "路径越界")
    return path


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
    return {"reports": items, "total": len(items)}


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
