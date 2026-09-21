"""学习资料上传/联网下载路由：保存→解析入库→触发重规划。"""

import logging
import uuid
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Query, UploadFile
from pydantic import BaseModel

from app.config import get_paths
from app.db import models as db
from app.db.database import get_conn
from app.kb.ingest import ingest_file
from app.kb.websearch import suggest_filename
from app.tutor.socratic import replan

router = APIRouter()

logger = logging.getLogger(__name__)

ALLOWED_EXT = {".txt", ".md", ".pdf", ".docx"}

# 下载上限与下载用浏览器 UA（部分站点拒绝脚本 UA）
MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024
_DL_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
}

# Content-Type → 允许入库的扩展名（缺失/不匹配时回退 URL 后缀）
_CT_EXT = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "text/plain": ".txt",
    "text/markdown": ".md",
}


class DownloadBody(BaseModel):
    url: str
    session_id: int


def _update_chunks(mid: int, chunks: int) -> None:
    """回填材料的实际入库块数。"""
    conn = get_conn()
    try:
        conn.execute("UPDATE materials SET chunks = ? WHERE id = ?", (chunks, mid))
        conn.commit()
    finally:
        conn.close()


@router.post("/api/materials")
async def upload_material(file: UploadFile, session_id: int = Query(...)):
    if db.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    filename = file.filename or "material"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail="仅支持 .txt / .md / .pdf / .docx 文件")

    stored = Path(get_paths()["uploads_dir"]) / f"{uuid.uuid4().hex}{ext}"
    try:
        stored.write_bytes(await file.read())
    finally:
        await file.close()

    mid = db.add_material(session_id, filename, str(stored), 0)
    try:
        chunks = ingest_file(session_id, str(stored), filename, mid)
    except Exception:
        # 真实异常写入日志（打包版在 %APPDATA%\EduRAGTutor\eduragtutor.log），便于排查
        logger.exception("资料入库失败: %s", filename)
        db.delete_material(mid)
        stored.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="文件解析失败，请确认文件内容有效")
    _update_chunks(mid, chunks)

    replanned = replan(session_id)
    return {
        "material": {"id": mid, "filename": filename, "chunks": chunks},
        "replanned": replanned,
        "points": db.list_points(session_id),
    }


@router.post("/api/materials/download")
def download_material(body: DownloadBody):
    """从网络链接下载文档并入库（复用上传的解析→向量化→重规划管线）。"""
    if db.get_session(body.session_id) is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    url = (body.url or "").strip()
    if not url.lower().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="仅支持 http/https 链接")

    # 流式下载：Content-Length 预检 + 累计字节双重限制，防超大文件
    try:
        with httpx.Client(follow_redirects=True, timeout=60, headers=_DL_HEADERS) as client:
            with client.stream("GET", url) as resp:
                resp.raise_for_status()
                ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
                content_length = resp.headers.get("content-length")
                if content_length and int(content_length) > MAX_DOWNLOAD_BYTES:
                    raise HTTPException(status_code=400, detail="文件超过 50MB 下载上限")

                ext = Path(urlparse(url).path).suffix.lower()
                if ext not in ALLOWED_EXT:
                    ext = _CT_EXT.get(ctype, "")
                if ext not in ALLOWED_EXT:
                    raise HTTPException(
                        status_code=400,
                        detail="该链接不是可直接下载的文档（pdf/docx/txt/md），请在浏览器中打开",
                    )

                buf = bytearray()
                for chunk in resp.iter_bytes(65536):
                    buf.extend(chunk)
                    if len(buf) > MAX_DOWNLOAD_BYTES:
                        raise HTTPException(status_code=400, detail="文件超过 50MB 下载上限")
    except HTTPException:
        raise
    except Exception:
        logger.exception("资料下载失败: %s", url)
        raise HTTPException(status_code=502, detail="下载失败，链接不可达或被站点拒绝")

    if not buf:
        raise HTTPException(status_code=400, detail="下载内容为空")

    filename = suggest_filename(url)
    if not filename.lower().endswith(ext):
        filename = f"{filename}{ext}"

    stored = Path(get_paths()["uploads_dir"]) / f"{uuid.uuid4().hex}{ext}"
    stored.write_bytes(bytes(buf))

    mid = db.add_material(body.session_id, filename, str(stored), 0)
    try:
        chunks = ingest_file(body.session_id, str(stored), filename, mid)
    except Exception:
        logger.exception("资料入库失败: %s", filename)
        db.delete_material(mid)
        stored.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="文件解析失败，请确认内容有效")
    _update_chunks(mid, chunks)

    replanned = replan(body.session_id)
    return {
        "material": {"id": mid, "filename": filename, "chunks": chunks},
        "replanned": replanned,
        "points": db.list_points(body.session_id),
    }
