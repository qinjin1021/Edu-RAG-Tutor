"""会话 CRUD 路由。"""

from fastapi import APIRouter, HTTPException

from app.db import models as db
from app.kb.retrieve import delete_collection

router = APIRouter()

GREETING = (
    "你好呀！我是思小诘，你的苏格拉底式学习伙伴～ "
    "今天想学习什么知识呢？告诉我主题，我们开始吧！(◕‿◕)"
)


def _with_progress(session: dict) -> dict:
    """为会话 dict 补充 progress（知识点平均掌握度取整）。"""
    points = db.list_points(session["id"])
    session["progress"] = (
        int(sum(p["mastery"] for p in points) / len(points) + 0.5) if points else 0
    )
    return session


@router.get("/api/sessions")
def get_sessions():
    return {"sessions": db.list_sessions()}


@router.post("/api/sessions")
def post_session():
    sid = db.create_session()
    return {"session": _with_progress(db.get_session(sid)), "greeting": GREETING}


@router.get("/api/sessions/{sid}")
def get_session_detail(sid: int):
    session = db.get_session(sid)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {
        "session": _with_progress(session),
        "messages": db.list_messages(sid),
        "points": db.list_points(sid),
        "materials": db.list_materials(sid),
    }


@router.delete("/api/sessions/{sid}")
def delete_session_route(sid: int):
    if db.get_session(sid) is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    db.delete_session(sid)
    delete_collection(sid)
    return {"ok": True}
