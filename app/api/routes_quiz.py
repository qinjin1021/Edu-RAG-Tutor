"""阶段自测 + 错题本路由。"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.db import models as db
from app.tutor import quiz
from app.tutor.methods import get_method

router = APIRouter()


class PhaseQuizBody(BaseModel):
    session_id: int


class PhaseSubmitBody(BaseModel):
    quiz_id: int
    answers: list[int] = Field(default_factory=list)  # 每题所选选项下标 0-3


class PracticeBody(BaseModel):
    answers: list[dict] = Field(default_factory=list)  # 每项 {id, choice}


class ResolveBody(BaseModel):
    id: int


@router.post("/api/quiz")
def phase_quiz(body: PhaseQuizBody):
    """为会话已学知识点出一套阶段自测（答案仅存服务端）。"""
    try:
        return quiz.create_phase_quiz(body.session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="会话不存在")
    except ValueError:
        raise HTTPException(status_code=400, detail="当前会话还没有已学的知识点，先学一会儿再来吧")
    except RuntimeError:
        raise HTTPException(status_code=503, detail="出题失败，请检查大模型配置后重试")


@router.post("/api/quiz/submit")
def phase_quiz_submit(body: PhaseSubmitBody):
    """提交阶段自测答案：本地判分，做错的题自动收进错题本。"""
    try:
        return quiz.submit_phase_quiz(body.quiz_id, body.answers)
    except KeyError:
        raise HTTPException(status_code=404, detail="自测记录不存在，请重新出题")


@router.get("/api/wrongbook")
def wrongbook():
    """错题本列表与统计。"""
    items = db.list_wrong_questions()
    unresolved = sum(1 for w in items if not w.get("resolved"))
    for w in items:
        # 学伴名翻译：method id → emoji+名（失效则回退原 id）
        w["method_label"] = ""
        if w.get("method"):
            try:
                spec = get_method(w["method"])
                w["method_label"] = f"{spec.emoji} {spec.name}"
            except Exception:  # noqa: BLE001
                w["method_label"] = str(w["method"])
    return {
        "items": items,
        "stats": {
            "total": len(items),
            "unresolved": unresolved,
            "resolved": len(items) - unresolved,
        },
    }


@router.post("/api/wrongbook/practice")
def wrongbook_practice(body: PracticeBody):
    """错题重练判分：答对自动标记已掌握，答错错误次数 +1。"""
    if not body.answers:
        raise HTTPException(status_code=400, detail="没有要提交的答案")
    judged = []   # 给 DAO 落库用的 {id, ok, choice}
    results = []  # 回给前端复盘用的
    for a in body.answers[:200]:
        try:
            wid = int(a.get("id", 0))
            choice = int(a.get("choice", -1))
        except (TypeError, ValueError):
            continue
        w = db.get_wrong_question(wid)
        if w is None:
            continue
        ok = choice == w.get("answer")
        judged.append({"id": wid, "ok": ok, "choice": choice})
        results.append(
            {
                "id": wid,
                "ok": ok,
                "choice": choice,
                "answer": w.get("answer"),
                "question": w.get("question"),
                "options": w.get("options") or [],
                "point": w.get("point") or "",
                "explanation": w.get("explanation") or "",
            }
        )
    if not results:
        raise HTTPException(status_code=404, detail="错题记录不存在")
    resolved_count = db.practice_submit(judged)
    return {"results": results, "resolved_count": resolved_count}


@router.post("/api/wrongbook/resolve")
def wrongbook_resolve(body: ResolveBody):
    """手动标记错题为已掌握。"""
    if not db.set_resolved(body.id):
        raise HTTPException(status_code=404, detail="错题记录不存在")
    return {"ok": True}
