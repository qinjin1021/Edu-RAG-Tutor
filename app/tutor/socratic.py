"""学习教学引擎：按学习方法制定计划、驱动学习/复习/总结的完整状态机。

handle_chat() 是一个生成器，产出门事件字典序列（SSE 契约）：
  {"type":"delta","text":...}   流式文本增量（已过滤评估块）
  {"type":"state",...}          阶段/知识点/进度状态
  {"type":"reward","point":...} 阶段奖励（知识点达标进入巩固轮，前端庆祝动画）
  {"type":"emotion","emotion":...}
  {"type":"done","message_id":...,"emotion":...}
  {"type":"error","message":...}
"""

import json
import logging
from typing import Generator, Optional

from app.config import get_settings
from app.db import models as db
from app.kb.retrieve import retrieve
from app.tutor.llm import chat_json, chat_once, chat_stream
from app.tutor.methods import MethodSpec, get_method
from app.tutor.prompts import (
    build_opening_system,
    build_plan_system,
    build_review_system,
    build_stage_reward_system,
    build_summary_system,
    build_tutor_system,
)

logger = logging.getLogger(__name__)

# 评估块分隔标记
MARKER = "<<<EVAL>>>"

# 合法表情集合（与前端 EMOTIONS 一致）
_EMOTIONS = {"idle", "think", "happy", "encourage", "surprise"}

# 知识点状态中文（供提示词展示）
_STATUS_ZH = {
    "pending": "待学习",
    "learning": "学习中",
    "mastered": "已掌握",
    "weak": "待加强",
}


# ---------- 工具函数 ----------

def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _as_int(val, default: int = 0) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _avg_progress(points: list[dict]) -> int:
    if not points:
        return 0
    return int(sum(p["mastery"] for p in points) / len(points) + 0.5)


def _safe_split(pending: str) -> tuple[str, str]:
    """把缓冲拆为（可安全输出，需保留）。

    需保留的部分：疑似半截标记（是 MARKER 的真前缀）或完整标记及其后内容，
    确保评估块绝不外泄。
    """
    for i, ch in enumerate(pending):
        if ch != "<":
            continue
        rest = pending[i:]
        if rest.startswith(MARKER) or MARKER.startswith(rest):
            return pending[:i], pending[i:]
    return pending, ""


def _split_eval(emitted: str, pending: str) -> tuple[str, str]:
    """流结束后分离展示文本与评估块原始内容。"""
    if MARKER in pending:
        before, _, after = pending.partition(MARKER)
        display = (emitted + before).rstrip()
        return display, after
    # 没有完整标记：pending 至多是疑似半截标记，拼回展示文本
    return (emitted + pending).rstrip(), ""


def _parse_eval(raw: str) -> dict:
    """容错解析评估块 JSON：剥围栏，取第一个 { 到最后一个 }。"""
    if not raw:
        return {}
    text = raw.strip().strip("`").strip()
    if text[:4].lower() == "json":
        text = text[4:].strip()
    first, last = text.find("{"), text.rfind("}")
    if first == -1 or last <= first:
        return {}
    try:
        obj = json.loads(text[first : last + 1])
        return obj if isinstance(obj, dict) else {}
    except json.JSONDecodeError:
        logger.warning("评估块解析失败: %s", raw[:200])
        return {}


def _map_emotion(ev: dict, is_summary: bool) -> str:
    """由评估结果映射立绘表情。"""
    if is_summary:
        return "encourage"
    action = str(ev.get("action") or "")
    if action == "need_material":
        return "surprise"
    if action in ("hint", "probe"):
        return "think"
    if ev.get("understood") is True:
        return "happy"
    emo = str(ev.get("emotion") or "")
    return emo if emo in _EMOTIONS else "idle"


# ---------- 占位符格式化 ----------

def _fmt_points(points: list[dict]) -> str:
    if not points:
        return "（暂无知识点）"
    lines = []
    for p in points:
        status = _STATUS_ZH.get(p["status"], p["status"])
        lines.append(
            f"{p['idx'] + 1}. {p['name']}（掌握度 {int(p['mastery'])}%，状态：{status}）"
        )
    return "\n".join(lines)


def _fmt_point(point: Optional[dict]) -> str:
    if not point:
        return "（当前没有进行中的薄弱知识点；若清单全部达标，请友好收尾并给 action=finish）"
    desc = f"：{point['description']}" if point.get("description") else ""
    return f"{point['name']}（掌握度 {int(point['mastery'])}%，状态：{_STATUS_ZH.get(point['status'], point['status'])}）{desc}"


def _fmt_reference(sid: int, topic: str, point: Optional[dict]) -> str:
    query = f"{topic} {point['name']}" if point else topic
    try:
        refs = retrieve(sid, query)
    except Exception:
        refs = []
    return "\n---\n".join(refs) if refs else "（暂无资料）"


# ---------- 状态机辅助 ----------

def _pick_point(sid: int, status: str) -> Optional[dict]:
    """按阶段取当前知识点：learning 用 DAO；review 取第一个未达标点。"""
    if status in ("review", "done"):
        threshold = get_settings().mastery_threshold
        for p in db.list_points(sid):
            if p["mastery"] < threshold:
                return p
        return None
    return db.get_current_point(sid)


def _normalize_points(sid: int) -> None:
    """按掌握度归位知识点状态：达标→mastered，未达标→weak。"""
    threshold = get_settings().mastery_threshold
    for p in db.list_points(sid):
        if p["mastery"] >= threshold:
            if p["status"] != "mastered":
                db.update_point(p["id"], status="mastered")
        elif p["status"] != "weak":
            db.update_point(p["id"], status="weak")


def _enter_review(sid: int) -> None:
    """进入查漏补缺阶段。"""
    _normalize_points(sid)
    db.update_session(sid, status="review")


def _make_summary(sid: int, topic: str, spec: MethodSpec) -> str:
    """用全部历史生成学习总结（保证以"学习总结"开头）。"""
    history = [
        {"role": m["role"], "content": m["content"]} for m in db.list_messages(sid)
    ]
    text = chat_once(
        [
            {"role": "system", "content": build_summary_system(spec)},
            *history,
        ],
        temperature=0.3,
    )
    text = (text or "").strip()
    if MARKER in text:
        text = text.split(MARKER)[0].strip()
    if not text.startswith("学习总结"):
        head = f"学习总结：{topic}" if topic else "学习总结"
        text = f"{head}\n{text}"
    return text


def _make_stage_reward(sid: int, topic: str, point: dict, spec: MethodSpec) -> str:
    """知识点首次达标：生成阶段奖励（鼓励 + 阶段小结/不足 + 巩固问题）。

    LLM 失败时回退到固定文案，保证巩固轮流程不中断。
    """
    history = db.list_messages(sid, 20)
    record = "\n".join(
        f"{'用户' if m['role'] == 'user' else spec.char_name}：{m['content']}"
        for m in history
    )
    try:
        text = chat_once(
            [
                {
                    "role": "system",
                    "content": build_stage_reward_system(
                        spec,
                        topic=topic,
                        point_name=point["name"],
                        point_desc=point.get("description") or point["name"],
                        record=record or "（暂无记录）",
                    ),
                }
            ],
            temperature=0.6,
        )
        text = (text or "").strip()
        if MARKER in text:
            text = text.split(MARKER)[0].strip()
        if text and not text.startswith("🎉"):
            text = "🎉 阶段达成！\n" + text
        if text:
            return text
    except Exception:
        logger.exception("阶段奖励生成失败，使用默认文案")
    return (
        "🎉 阶段达成！\n"
        f"「{point['name']}」这个知识点你已经拿下啦，为认真学习的你鼓掌 👏\n"
        "📋 阶段小结：这个阶段的要点你已经基本理解，不过真正的掌握还差一次实战巩固。\n"
        f"🎯 巩固练习：来一道真实场景题——假设你要在的实际项目里用到「{point['name']}」，"
        "你会怎么应用它解决具体问题？说说你的思路。"
    )


def _state_event(sid: int, status: str) -> dict:
    points = db.list_points(sid)
    return {
        "type": "state",
        "phase": status,
        "current_point": _pick_point(sid, status),
        "points": points,
        "progress": _avg_progress(points),
    }


# ---------- 对外接口 ----------

def make_plan(sid: int, topic: str, spec: Optional[MethodSpec] = None) -> list[dict]:
    """按学习方法为主题生成 3-8 个有序知识点并入库；失败回退单点计划。"""
    spec = spec or get_method("socratic")
    user_content = f"学习主题：{topic}"
    refs = retrieve(sid, topic)[:3]
    if refs:
        user_content += "\n\n参考资料片段：\n" + "\n---\n".join(refs)

    data = chat_json(
        [
            {"role": "system", "content": build_plan_system(spec)},
            {"role": "user", "content": user_content},
        ],
        temperature=0.3,
        # 推理模型的思考 token 计入 max_tokens（与测评出题同坑）：
        # 默认 2048 可能被思考吃掉导致计划 JSON 截断 → 静默降级单点
        max_tokens=4000,
    )

    points: list[dict] = []
    if isinstance(data, dict) and isinstance(data.get("points"), list):
        for i, p in enumerate(data["points"]):
            if isinstance(p, dict) and str(p.get("name", "")).strip():
                points.append(
                    {
                        "idx": i,
                        "name": str(p["name"]).strip(),
                        "description": str(p.get("description", "")).strip(),
                    }
                )
    if not points:
        points = [{"idx": 0, "name": topic, "description": topic}]
    points = points[:8]

    db.add_points(sid, points)
    return points


def replan(sid: int) -> bool:
    """资料上传后重建学习计划（沿用会话的学习方法）；无既有知识点时返回 False。"""
    session = db.get_session(sid)
    if session is None or not db.list_points(sid):
        return False
    spec = get_method(session.get("method"))
    db.delete_points(sid)
    make_plan(sid, session.get("topic") or "", spec)
    if session["status"] != "planning":
        db.update_session(sid, status="learning")
    return True


def handle_chat(sid: int, user_text: str) -> Generator[dict, None, None]:
    """完整状态机：规划→学习→查漏补缺→总结，产出门事件字典序列。"""
    settings = get_settings()
    threshold = settings.mastery_threshold
    try:
        db.add_message(sid, "user", user_text)
        session = db.get_session(sid)
        if session is None:
            yield {"type": "error", "message": "会话不存在，请刷新后重试"}
            return

        status = session["status"] or "planning"
        spec = get_method(session.get("method"))
        is_opening = False

        # ---- 规划阶段：拆解知识点并生成开场白 ----
        if status == "planning" and not db.list_points(sid):
            topic = user_text.strip()[:80] or "综合学习"
            # 规划是非流式 JSON 调用，推理模型可能耗时 1-3 分钟，
            # 先推送状态文案让用户立刻看到"正在做什么"而不是干等
            yield {"type": "status", "text": "正在拆解知识点、制定学习计划…"}
            make_plan(sid, topic, spec)
            db.update_session(sid, topic=topic, status="learning")
            session = db.get_session(sid)
            status = "learning"
            is_opening = True
        elif status == "planning":
            # 异常防御：已有知识点却仍是 planning
            status = "learning"
            db.update_session(sid, status="learning")

        topic = session["topic"] or user_text.strip()[:80]
        current = _pick_point(sid, status)
        points = db.list_points(sid)

        common = dict(
            spec=spec,
            topic=topic,
            points=_fmt_points(points),
            current_point=_fmt_point(current),
            reference=_fmt_reference(sid, topic, current),
        )
        if is_opening:
            system = build_opening_system(**common)
        elif status in ("review", "done"):
            system = build_review_system(**common)
        else:
            system = build_tutor_system(**common)

        if is_opening:
            # 计划已生成，先推送一次状态（右栏立即显示知识点清单）
            yield _state_event(sid, status)
            current = db.get_current_point(sid)
            # 开场引导同样要等推理模型出首个 token，更新等待文案
            yield {"type": "status", "text": "学习计划已就绪，正在准备开场引导…"}

        # 历史以文本形式嵌入 system：库中 assistant 历史已剥离评估块，
        # 若作为 role 消息回喂，模型会模仿历史而省略评估块，导致评估失效。
        history_msgs = db.list_messages(sid, settings.history_limit)
        last_user_idx = next(
            (
                i
                for i in range(len(history_msgs) - 1, -1, -1)
                if history_msgs[i]["role"] == "user"
            ),
            None,
        )
        current_user_msg = history_msgs.pop(last_user_idx) if last_user_idx is not None else None
        if history_msgs:
            record = "\n".join(
                f"{'用户' if m['role'] == 'user' else spec.char_name}：{m['content']}"
                for m in history_msgs
            )
            system = f"{system}\n\n【历史对话记录】\n{record}"
        messages = [{"role": "system", "content": system}]
        if current_user_msg:
            messages.append({"role": "user", "content": current_user_msg["content"]})

        # ---- 流式生成 + 评估块过滤 ----
        emitted = ""
        pending = ""
        for piece in chat_stream(messages):
            pending += piece
            safe, pending = _safe_split(pending)
            if safe:
                emitted += safe
                yield {"type": "delta", "text": safe}

        display, eval_raw = _split_eval(emitted, pending)
        ev = _parse_eval(eval_raw)
        action = str(ev.get("action") or "")

        # ---- 评估落地：掌握度 ----
        new_mastery: Optional[int] = None
        if current is not None:
            delta = 0 if is_opening else _clamp(_as_int(ev.get("mastery_delta")), -20, 30)
            new_mastery = _clamp(int(current["mastery"]) + delta, 0, 100)
            if new_mastery != int(current["mastery"]):
                db.update_point(current["id"], mastery=new_mastery)

        summary_text: Optional[str] = None
        reward_text: Optional[str] = None

        if action == "finish":
            _normalize_points(sid)
            summary_text = _make_summary(sid, topic, spec)
            db.update_session(sid, status="done")
            status = "done"
        elif status == "learning":
            go_next = (action == "next_point" or ev.get("mastered") is True) and current is not None
            if go_next:
                if current["status"] == "consolidating":
                    # 巩固轮验收通过 → 真正掌握，进入下一阶段
                    db.update_point(current["id"], status="mastered")
                elif new_mastery is not None and new_mastery >= threshold:
                    # 首次达标 → 进入巩固轮：正反馈奖励（鼓励+阶段小结+巩固问题）
                    db.update_point(current["id"], status="consolidating")
                    reward_text = _make_stage_reward(sid, topic, current, spec)
                else:
                    # 未达标但跳点 → 待加强（沿用原逻辑，留给查漏补缺阶段）
                    db.update_point(current["id"], status="weak")
                # 本知识点处理完毕；若没有下一个可学/可巩固知识点 → 收尾
                if db.get_current_point(sid) is None:
                    if all(p["mastery"] >= threshold for p in db.list_points(sid)):
                        summary_text = _make_summary(sid, topic, spec)
                        db.update_session(sid, status="done")
                        status = "done"
                    else:
                        _enter_review(sid)
                        status = "review"
        else:  # review / done
            if current is not None:
                if new_mastery is not None and new_mastery >= threshold:
                    db.update_point(current["id"], status="mastered")
                elif current["status"] != "weak":
                    db.update_point(current["id"], status="weak")
            if all(p["mastery"] >= threshold for p in db.list_points(sid)):
                summary_text = _make_summary(sid, topic, spec)
                db.update_session(sid, status="done")
                status = "done"

        # ---- 总结 / 阶段奖励作为展示文本追加 ----
        if summary_text is not None:
            yield {"type": "delta", "text": ("\n\n" if display else "") + summary_text}
            # 入库保留"回复 + 总结"全文，与流式展示一致，刷新恢复后内容完整
            final_text = f"{display}\n\n{summary_text}".strip() if display else summary_text
        elif reward_text is not None:
            yield {"type": "delta", "text": ("\n\n" if display else "") + reward_text}
            final_text = f"{display}\n\n{reward_text}".strip() if display else reward_text
        else:
            final_text = display

        msg_id = db.add_message(sid, "assistant", final_text)
        db.touch_session(sid)

        emotion = (
            "happy"
            if reward_text is not None
            else _map_emotion(ev, is_summary=summary_text is not None)
        )
        yield _state_event(sid, status)
        if reward_text is not None:
            # 阶段奖励事件：前端触发庆祝动画与奖励卡片高亮
            yield {"type": "reward", "point": current["name"] if current else ""}
        yield {"type": "emotion", "emotion": emotion}
        yield {"type": "done", "message_id": msg_id, "emotion": emotion}
    except Exception as exc:  # noqa: BLE001
        logger.exception("handle_chat 处理失败")
        try:
            char_name = spec.char_name
        except NameError:
            char_name = "思小诘"
        yield {"type": "error", "message": f"{char_name}走神了，请稍后再试（{exc}）"}
