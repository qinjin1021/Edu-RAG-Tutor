"""阶段自测 agent：针对会话已学知识点出题 → 本地判分 → 错题入本。

流程：知识点完成后由前端发起 → 取会话中非 pending 的知识点 → LLM 针对
这些知识点生成 5 道单选题（答案仅存服务端）→ 用户作答后本地判分 →
做错的题写入错题本（wrong_questions 表，source='phase'）。

出题复用 assessment.request_json / clean_questions（清洗与截断救捞），
判分纯本地、不依赖 LLM。记录存 quizzes 表。
"""

import json
import logging

from app.db import models as db
from app.tutor.assessment import (
    QUIZ_MAX_TOKENS,
    clean_questions,
    request_json,
)
from app.tutor.prompts import build_phase_quiz_system

logger = logging.getLogger(__name__)

# 阶段自测题量：目标 5 题，最少 3 题（少于则视为出题失败）
PHASE_QUIZ_COUNT = 5
PHASE_MIN_QUESTIONS = 3


def _points_block(points: list[dict]) -> str:
    """把已学知识点整理成出题提示词用的清单文本。"""
    lines = []
    for p in points:
        desc = (p.get("description") or "").strip()
        name = p.get("name") or ""
        lines.append(f"- {name}：{desc}" if desc else f"- {name}")
    return "\n".join(lines)


def create_phase_quiz(session_id) -> dict:
    """为会话的已学知识点生成阶段自测卷并入库；返回 {id, topic, questions(不含答案)}。

    会话不存在抛 KeyError；还没有已学知识点抛 ValueError；
    出题失败（LLM 不可用/有效题量不足）抛 RuntimeError。
    """
    session = db.get_session(session_id)
    if session is None:
        raise KeyError("session not found")
    topic = session.get("topic") or ""

    points = [p for p in db.list_points(session_id) if p.get("status") != "pending"]
    if not points:
        raise ValueError("no learned points")

    data, salvaged = request_json(
        build_phase_quiz_system(topic, _points_block(points)),
        QUIZ_MAX_TOKENS,
        '{"question"',
    )
    raw_questions = (data.get("questions") if isinstance(data, dict) else None) or salvaged
    questions = clean_questions(raw_questions)[:PHASE_QUIZ_COUNT]
    if len(questions) < PHASE_MIN_QUESTIONS:
        logger.warning("阶段自测出题数量不足：%s", len(questions))
        raise RuntimeError("quiz generation failed")

    qid = db.create_quiz(session_id, topic, json.dumps(questions, ensure_ascii=False))
    return {
        "id": qid,
        "topic": topic,
        "questions": [
            {k: q[k] for k in ("question", "options", "point", "difficulty")}
            for q in questions
        ],
    }


def submit_phase_quiz(quiz_id, answers: list[int]) -> dict:
    """阶段自测判分（本地）+ 错题入本，结果入库并返回。

    返回 {topic, total, score, questions(含 answer/explanation), answers}。
    quiz_id 无效抛 KeyError；重复提交不重复入错题本（幂等）。
    """
    record = db.get_quiz(quiz_id)
    if record is None:
        raise KeyError("quiz not found")
    questions = json.loads(record["questions"] or "[]")
    topic = record.get("topic") or ""

    # 幂等门：已提交过的自测不重复入错题本
    prev = (record.get("answers") or "").strip()
    already_submitted = bool(prev and prev != "[]")

    # 判分：缺答/越界一律算错，但不抛错
    norm = [(answers[i] if i < len(answers) else -1) for i in range(len(questions))]
    score = sum(1 for i, q in enumerate(questions) if norm[i] == q["answer"])

    db.update_quiz_result(quiz_id, json.dumps(norm, ensure_ascii=False), score, len(questions))

    # 错题入本：带上会话的学习方法（学伴），方便错题本展示来源
    if not already_submitted:
        wrong_items = [
            {
                "question": q["question"],
                "options": q["options"],
                "answer": q["answer"],
                "user_answer": norm[i],
                "point": q.get("point", ""),
                "explanation": q.get("explanation", ""),
            }
            for i, q in enumerate(questions)
            if norm[i] != q["answer"]
        ]
        if wrong_items:
            session = db.get_session(record.get("session_id"))
            method = session.get("method") if session else None
            try:
                db.add_wrong_questions(
                    record.get("session_id"), quiz_id, "phase", topic, method, wrong_items
                )
            except Exception as exc:  # noqa: BLE001 —— 入本是增值能力，失败不阻断判分返回
                logger.warning("阶段自测错题入本失败：%s", exc)

    return {
        "topic": topic,
        "total": len(questions),
        "score": score,
        # 回传含答案与解析的题目，供前端逐题复盘
        "questions": [
            {k: q[k] for k in ("question", "options", "answer", "point", "difficulty", "explanation")}
            for q in questions
        ],
        "answers": norm,
    }
