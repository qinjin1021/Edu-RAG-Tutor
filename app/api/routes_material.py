"""学习资料上传路由：保存→解析入库→触发重规划。"""

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, UploadFile

from app.config import get_paths
from app.db import models as db
from app.db.database import get_conn
from app.kb.ingest import ingest_file
from app.tutor.socratic import replan

router = APIRouter()

logger = logging.getLogger(__name__)

ALLOWED_EXT = {".txt", ".md", ".pdf", ".docx"}


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
        # 真实异常写入日志（打包版在 %APPDATA%\SiXiaoJie\sixiaojie.log），便于排查
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
