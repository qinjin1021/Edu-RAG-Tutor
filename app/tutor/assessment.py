"""学前测评 agent：摸底出题 → 本地判分 → 学习路线规划。

流程：用户给出想学的主题 → LLM 生成 10 道由易到难的单选题（答案仅存服务端）→
用户作答后本地判分（对答案即可，无需 LLM）→ 把逐题对错与薄弱点交给 LLM
规划 2-4 阶段的多学习方法路线（每阶段一种学习方法，含切换标准）。

题目与路线均走 llm.chat_json；LLM 不可用时出题/路线各自抛错或降级，
判分永远本地可用。记录存 assessments 表。
"""

import json
import logging

from app.db import models as db
from app.tutor.llm import chat_json_with_raw
from app.tutor.methods import list_methods
from app.tutor.prompts import build_quiz_system, build_route_system

logger = logging.getLogger(__name__)

# 期望题数；LLM 偶尔多给少给，落在 [MIN, MAX] 内都接受
QUIZ_COUNT = 10
MIN_QUESTIONS = 6
MAX_QUESTIONS = 10
OPTIONS_COUNT = 4

# 出题/路线的 max_tokens：推理模型（如 deepseek-v4-flash）的思考 token
# 计入上限，给足余量防 JSON 被截断；截断了还有 _salvage_objects 兜底
QUIZ_MAX_TOKENS = 8000
ROUTE_MAX_TOKENS = 4000

# 得分率 → 水平标签（本地判分即可确定，不依赖 LLM）
_LEVELS = (
    (0.9, "基础扎实"),
    (0.7, "有一定基础"),
    (0.4, "入门水平"),
    (0.0, "初步接触"),
)


def _clean_questions(raw) -> list[dict]:
    """清洗 LLM 返回的题目列表：校验字段、answer 归一到 0-3、截到上限。"""
    questions: list[dict] = []
    if not isinstance(raw, list):
        return questions
    for item in raw:
        if not isinstance(item, dict):
            continue
        q = str(item.get("question", "")).strip()
        options = [str(o).strip() for o in item.get("options", []) or []]
        if not q or len(options) != OPTIONS_COUNT:
            continue
        try:
            answer = int(item.get("answer"))
        except (TypeError, ValueError):
            continue
        if not 0 <= answer < OPTIONS_COUNT:
            continue
        questions.append(
            {
                "question": q,
                "options": options,
                "answer": answer,
                "point": str(item.get("point", "")).strip(),
                "difficulty": str(item.get("difficulty", "")).strip(),
                "explanation": str(item.get("explanation", "")).strip(),
            }
        )
        if len(questions) >= MAX_QUESTIONS:
            break
    return questions


def _level(score: int, total: int) -> str:
    if total <= 0:
        return ""
    rate = score / total
    for threshold, label in _LEVELS:
        if rate >= threshold:
            return label
    return _LEVELS[-1][1]


def _salvage_objects(raw: str, marker: str) -> list[dict]:
    """从被截断的 LLM 原文中逐个抠出完整 JSON 对象（截断救捞）。

    推理模型的思考 token 计入 max_tokens，正文可能写到一半被切断，
    整体 json.loads 失败但前几个对象是完整的：按 marker（如 '{"question"'
    或 '{"method"'）定位每个对象起点，用 raw_decode 逐个解析。
    """
    decoder = json.JSONDecoder()
    objects: list[dict] = []
    idx = raw.find(marker)
    while idx != -1 and len(objects) < MAX_QUESTIONS * 2:
        try:
            obj, end = decoder.raw_decode(raw, idx)
            if isinstance(obj, dict):
                objects.append(obj)
            idx = raw.find(marker, end)
        except json.JSONDecodeError:
            idx = raw.find(marker, idx + 1)
    return objects


def _request_json(system: str, max_tokens: int, marker: str) -> tuple[dict | None, list[dict]]:
    """发一次 JSON 请求，返回 (整体解析结果, 截断救捞出的对象列表)。

    整体解析成功时救捞列表为空；失败时从原文按 marker 抠完整对象。
    """
    data, raw = chat_json_with_raw(
        [{"role": "system", "content": system}],
        temperature=0.4,
        max_tokens=max_tokens,
    )
    if data is not None:
        return data, []
    salvaged = _salvage_objects(raw, marker)
    logger.warning("LLM JSON 解析失败，截断救捞到 %s 个对象", len(salvaged))
    return None, salvaged


def create_quiz(topic: str) -> dict:
    """为主题生成摸底卷并入库；返回 {id, topic, questions(不含答案)}。

    出题失败（LLM 不可用/有效题量不足）抛 RuntimeError；
    JSON 被截断时按救捞出的完整题目继续，凑够下限即用。
    """
    data, salvaged = _request_json(build_quiz_system(topic), QUIZ_MAX_TOKENS, '{"question"')
    raw_questions = (data.get("questions") if isinstance(data, dict) else None) or salvaged
    questions = _clean_questions(raw_questions)
    if len(questions) < MIN_QUESTIONS:
        logger.warning("学前测评出题数量不足：%s", len(questions))
        raise RuntimeError("quiz generation failed")
    aid = db.create_assessment(topic, json.dumps(questions, ensure_ascii=False))
    return {
        "id": aid,
        "topic": topic,
        "questions": [
            {k: q[k] for k in ("question", "options", "point", "difficulty")}
            for q in questions
        ],
    }


def _methods_block() -> str:
    """给路线规划提示词用的方法清单文本。"""
    return "\n".join(f"- {m.id}：{m.name}（{m.intro}）" for m in list_methods())


def _grade_report(topic: str, questions: list[dict], answers: list[int], score: int) -> str:
    """把判分结果整理成路线规划提示词的摸底报告文本。"""
    total = len(questions)
    lines = [f"主题：{topic}", f"得分：{score}/{total}（{_level(score, total)}）", "逐题情况："]
    for i, q in enumerate(questions):
        sel = answers[i] if i < len(answers) else -1
        mark = "答对" if sel == q["answer"] else "答错"
        point = f"（考察：{q['point']}）" if q.get("point") else ""
        diff = f"[{q['difficulty']}] " if q.get("difficulty") else ""
        lines.append(f"- {diff}{q['question'][:50]}…{point}：{mark}")
    return "\n".join(lines)


def _clean_route(raw) -> list[dict]:
    """清洗 LLM 返回的路线阶段：method 必须在注册表内，points 截 5 个。"""
    phases: list[dict] = []
    valid_ids = {m.id for m in list_methods()}
    if not isinstance(raw, dict) or not isinstance(raw.get("phases"), list):
        return phases
    for p in raw["phases"][:4]:
        if not isinstance(p, dict):
            continue
        mid = str(p.get("method", "")).strip()
        if mid not in valid_ids:
            continue
        points = [str(x).strip() for x in p.get("points", []) or [] if str(x).strip()][:5]
        phases.append(
            {
                "method": mid,
                "goal": str(p.get("goal", "")).strip(),
                "points": points,
                "milestone": str(p.get("milestone", "")).strip(),
            }
        )
    return phases


def submit_answers(assessment_id: int, answers: list[int]) -> dict:
    """判分（本地）并规划路线（LLM，失败降级为无路线），结果入库并返回。

    返回 {topic, total, score, level, questions(含 answer/explanation), answers, route, summary}。
    assessment_id 无效抛 KeyError。
    """
    record = db.get_assessment(assessment_id)
    if record is None:
        raise KeyError("assessment not found")
    questions = json.loads(record["questions"] or "[]")
    topic = record["topic"] or ""

    # 判分：缺答/越界一律算错，但不抛错
    norm = [(answers[i] if i < len(answers) else -1) for i in range(len(questions))]
    score = sum(1 for i, q in enumerate(questions) if norm[i] == q["answer"])
    level = _level(score, len(questions))

    # 路线规划：LLM 失败时给空路线（前端引导直接选方法开始）；截断时救捞完整阶段
    route: list[dict] = []
    summary = ""
    try:
        data, salvaged = _request_json(
            build_route_system(topic, _methods_block(), _grade_report(topic, questions, norm, score)),
            ROUTE_MAX_TOKENS,
            '{"method"',
        )
        phases = (data.get("phases") if isinstance(data, dict) else None) or salvaged
        cleaned = _clean_route({"phases": phases})
        if cleaned:
            route = cleaned
        if isinstance(data, dict):
            summary = str(data.get("summary", "")).strip()
    except Exception as exc:  # noqa: BLE001 —— 路线属增值能力，失败不阻断判分返回
        logger.warning("学前测评路线规划失败：%s", exc)

    db.update_assessment_result(
        assessment_id,
        json.dumps(norm, ensure_ascii=False),
        score,
        len(questions),
        level,
        json.dumps(route, ensure_ascii=False),
    )
    return {
        "topic": topic,
        "total": len(questions),
        "score": score,
        "level": level,
        # 回传含答案与解析的题目，供前端逐题复盘
        "questions": [
            {k: q[k] for k in ("question", "options", "answer", "point", "difficulty", "explanation")}
            for q in questions
        ],
        "answers": norm,
        "route": route,
        "summary": summary,
    }
