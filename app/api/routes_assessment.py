"""学前测评路由：摸底出题 + 提交判分与学习路线规划。"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.tutor import assessment

router = APIRouter()


class QuizBody(BaseModel):
    topic: str


class SubmitBody(BaseModel):
    assessment_id: int
    answers: list[int] = Field(default_factory=list)  # 每题所选选项下标 0-3


@router.post("/api/assessment/quiz")
def assessment_quiz(body: QuizBody):
    """为主题出一套摸底选择题（答案仅存服务端）。"""
    topic = (body.topic or "").strip()[:80]
    if not topic:
        raise HTTPException(status_code=400, detail="请先填写想学的主题")
    try:
        return assessment.create_quiz(topic)
    except RuntimeError:
        raise HTTPException(status_code=503, detail="出题失败，请检查大模型配置后重试")


@router.post("/api/assessment/submit")
def assessment_submit(body: SubmitBody):
    """提交答案：本地判分 + LLM 规划学习路线（路线失败不阻断，route 返回空数组）。"""
    try:
        return assessment.submit_answers(body.assessment_id, body.answers)
    except KeyError:
        raise HTTPException(status_code=404, detail="测评记录不存在，请重新出题")
