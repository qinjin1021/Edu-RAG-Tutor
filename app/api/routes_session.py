"""会话 CRUD 路由 + 学习方法清单接口。"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db import models as db
from app.kb.retrieve import delete_collection
from app.tutor.methods import get_method, method_assets_payload

router = APIRouter()


class SessionBody(BaseModel):
    method: str = ""  # 学习方法 ID；留空/无效 = 苏格拉底问答法


def _with_progress(session: dict) -> dict:
    """为会话 dict 补充 progress（知识点平均掌握度取整）。"""
    points = db.list_points(session["id"])
    session["progress"] = (
        int(sum(p["mastery"] for p in points) / len(points) + 0.5) if points else 0
    )
    return session


@router.get("/api/methods")
def get_methods():
    """全部学习方法（含人物信息与表情图回退映射），每次现扫支持热放图。"""
    return {"methods": method_assets_payload()}


@router.get("/api/sessions")
def get_sessions():
    return {"sessions": db.list_sessions()}


@router.post("/api/sessions")
def post_session(body: SessionBody | None = None):
    """创建会话。body 可省略（兼容旧调用）；method 无效回退 socratic。"""
    method = get_method(body.method if body else "")
    sid = db.create_session(method.id)
    return {"session": _with_progress(db.get_session(sid)), "greeting": method.greeting}


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
