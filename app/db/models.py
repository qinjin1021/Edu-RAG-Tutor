"""函数式 DAO：会话、消息、知识点、学习材料的增删改查。

每个函数内部独立获取连接并在 finally 中关闭。
"""

import json

from app.db.database import get_conn, now_str

# update_session 允许修改的字段白名单（method 创建后原则上不可变，仅为防未来静默丢字段）
_SESSION_FIELDS = {"topic", "status", "method", "replan_pending"}


# ---------- 会话 ----------

def create_session(method: str = "socratic") -> int:
    """新建会话（指定学习方法），返回 id。"""
    conn = get_conn()
    try:
        ts = now_str()
        cur = conn.execute(
            "INSERT INTO sessions (topic, status, method, created_at, updated_at) "
            "VALUES ('', 'planning', ?, ?, ?)",
            (method, ts, ts),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_session(sid) -> dict | None:
    """按 id 查会话，不存在返回 None。"""
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_sessions() -> list[dict]:
    """列出全部会话（updated_at 倒序），附带 progress=知识点平均 mastery 四舍五入取整。"""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM sessions ORDER BY updated_at DESC"
        ).fetchall()
        result = []
        for row in rows:
            s = dict(row)
            avg = conn.execute(
                "SELECT AVG(mastery) FROM knowledge_points WHERE session_id = ?",
                (s["id"],),
            ).fetchone()[0]
            # 无知识点时进度为 0
            s["progress"] = int(avg + 0.5) if avg is not None else 0
            result.append(s)
        return result
    finally:
        conn.close()


def update_session(sid, **fields) -> None:
    """更新会话（仅 topic/status/replan_pending），并自动刷新 updated_at。"""
    valid = {k: v for k, v in fields.items() if k in _SESSION_FIELDS}
    if not valid:
        return
    conn = get_conn()
    try:
        sets = ", ".join(f"{k} = ?" for k in valid)
        conn.execute(
            f"UPDATE sessions SET {sets}, updated_at = ? WHERE id = ?",
            [*valid.values(), now_str(), sid],
        )
        conn.commit()
    finally:
        conn.close()


def touch_session(sid) -> None:
    """仅刷新会话的 updated_at。"""
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?", (now_str(), sid)
        )
        conn.commit()
    finally:
        conn.close()


def delete_session(sid) -> None:
    """删除会话，并级联清理其消息、知识点、材料与自测记录。
    错题本（wrong_questions）保留：靠冗余的 topic/method/source 字段继续显示来源。
    """
    conn = get_conn()
    try:
        conn.execute("DELETE FROM sessions WHERE id = ?", (sid,))
        conn.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
        conn.execute("DELETE FROM knowledge_points WHERE session_id = ?", (sid,))
        conn.execute("DELETE FROM materials WHERE session_id = ?", (sid,))
        conn.execute("DELETE FROM quizzes WHERE session_id = ?", (sid,))
        conn.commit()
    finally:
        conn.close()


# ---------- 消息 ----------

def add_message(sid, role: str, content: str) -> int:
    """追加一条消息，返回 id。"""
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (sid, role, content, now_str()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_messages(sid, limit=None) -> list[dict]:
    """列出会话消息（id 升序）；limit 给定时只取最近 N 条（仍按升序返回）。"""
    conn = get_conn()
    try:
        if limit is None:
            rows = conn.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY id ASC",
                (sid,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (sid, limit),
            ).fetchall()
            rows = list(reversed(rows))
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------- 知识点 ----------

def add_points(sid, points: list[dict]) -> list[int]:
    """批量写入知识点（dict 需含 idx/name，可选 description），返回 id 列表。"""
    conn = get_conn()
    try:
        ids = []
        for p in points:
            cur = conn.execute(
                "INSERT INTO knowledge_points (session_id, idx, name, description) "
                "VALUES (?, ?, ?, ?)",
                (sid, p.get("idx", 0), p.get("name", ""), p.get("description", "")),
            )
            ids.append(cur.lastrowid)
        conn.commit()
        return ids
    finally:
        conn.close()


def list_points(sid) -> list[dict]:
    """列出会话知识点（idx 升序）。"""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM knowledge_points WHERE session_id = ? ORDER BY idx ASC",
            (sid,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_points(sid) -> None:
    """删除会话的全部知识点。"""
    conn = get_conn()
    try:
        conn.execute("DELETE FROM knowledge_points WHERE session_id = ?", (sid,))
        conn.commit()
    finally:
        conn.close()


def update_point(pid, mastery=None, status=None) -> None:
    """按 id 更新知识点（仅传入的非 None 字段会被更新）。"""
    conn = get_conn()
    try:
        if mastery is not None:
            conn.execute(
                "UPDATE knowledge_points SET mastery = ? WHERE id = ?", (mastery, pid)
            )
        if status is not None:
            conn.execute(
                "UPDATE knowledge_points SET status = ? WHERE id = ?", (status, pid)
            )
        conn.commit()
    finally:
        conn.close()


def get_current_point(sid) -> dict | None:
    """取当前学习知识点：优先 status='consolidating'（巩固轮验收中）；
    其次 'learning'；否则取第一个 'pending' 并置为 'learning' 后返回；没有则返回 None。
    """
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM knowledge_points WHERE session_id = ? AND status = 'consolidating' "
            "ORDER BY idx ASC LIMIT 1",
            (sid,),
        ).fetchone()
        if row:
            return dict(row)
        row = conn.execute(
            "SELECT * FROM knowledge_points WHERE session_id = ? AND status = 'learning' "
            "ORDER BY idx ASC LIMIT 1",
            (sid,),
        ).fetchone()
        if row:
            return dict(row)
        row = conn.execute(
            "SELECT * FROM knowledge_points WHERE session_id = ? AND status = 'pending' "
            "ORDER BY idx ASC LIMIT 1",
            (sid,),
        ).fetchone()
        if row is None:
            return None
        conn.execute(
            "UPDATE knowledge_points SET status = 'learning' WHERE id = ?", (row["id"],)
        )
        conn.commit()
        point = dict(row)
        point["status"] = "learning"
        return point
    finally:
        conn.close()


# ---------- 学习材料 ----------

def add_material(sid, filename: str, stored_path: str, chunks: int) -> int:
    """登记一份学习材料，返回 id。"""
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO materials (session_id, filename, stored_path, chunks, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (sid, filename, stored_path, chunks, now_str()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_materials(sid) -> list[dict]:
    """列出会话的学习材料。"""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM materials WHERE session_id = ? ORDER BY id ASC",
            (sid,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_material(mid) -> None:
    """按 id 删除材料记录。"""
    conn = get_conn()
    try:
        conn.execute("DELETE FROM materials WHERE id = ?", (mid,))
        conn.commit()
    finally:
        conn.close()


# ---------- 学前测评 ----------

def create_assessment(topic: str, questions: str) -> int:
    """新建学前测评记录（questions 为含答案的题目 JSON 字符串），返回 id。"""
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO assessments (topic, questions, created_at) VALUES (?, ?, ?)",
            (topic, questions, now_str()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_assessment(aid) -> dict | None:
    """按 id 查测评记录，不存在返回 None。"""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM assessments WHERE id = ?", (aid,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_assessment_result(
    aid, answers: str, score: int, total: int, level: str, route: str
) -> None:
    """写入判分与路线规划结果。"""
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE assessments SET answers = ?, score = ?, total = ?, "
            "level = ?, route = ? WHERE id = ?",
            (answers, score, total, level, route, aid),
        )
        conn.commit()
    finally:
        conn.close()


# ---------- 阶段自测 ----------

def create_quiz(session_id, topic: str, questions: str) -> int:
    """新建阶段自测记录（questions 为含答案的题目 JSON 字符串），返回 id。"""
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO quizzes (session_id, topic, questions, created_at) VALUES (?, ?, ?, ?)",
            (session_id, topic, questions, now_str()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_quiz(qid) -> dict | None:
    """按 id 查自测记录，不存在返回 None。"""
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM quizzes WHERE id = ?", (qid,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_quiz_result(qid, answers: str, score: int, total: int) -> None:
    """写入自测判分结果。"""
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE quizzes SET answers = ?, score = ?, total = ? WHERE id = ?",
            (answers, score, total, qid),
        )
        conn.commit()
    finally:
        conn.close()


# ---------- 错题本 ----------

def add_wrong_questions(session_id, quiz_id, source: str, topic: str, method, items: list[dict]) -> int:
    """批量写入错题；同题干且未解决的错题只累加 wrong_count（防重复计数）。
    items 每项需含：question/options/answer/user_answer/point/explanation。
    返回新增条数。
    """
    conn = get_conn()
    try:
        ts = now_str()
        added = 0
        for it in items:
            row = conn.execute(
                "SELECT id FROM wrong_questions WHERE question = ? AND resolved = 0",
                (it["question"],),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE wrong_questions SET wrong_count = wrong_count + 1, "
                    "user_answer = ?, last_wrong_at = ? WHERE id = ?",
                    (it.get("user_answer", -1), ts, row["id"]),
                )
                continue
            conn.execute(
                "INSERT INTO wrong_questions (session_id, quiz_id, source, topic, method, "
                "question, options, answer, user_answer, point, explanation, "
                "wrong_count, resolved, created_at, last_wrong_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, ?, ?)",
                (
                    session_id, quiz_id, source, topic, method,
                    it["question"], json.dumps(it["options"], ensure_ascii=False),
                    it["answer"], it.get("user_answer", -1),
                    it.get("point", ""), it.get("explanation", ""),
                    ts, ts,
                ),
            )
            added += 1
        conn.commit()
        return added
    finally:
        conn.close()


def list_wrong_questions() -> list[dict]:
    """列出全部错题（未解决优先、最近做错的在前），options 反序列化为列表。"""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM wrong_questions ORDER BY resolved ASC, last_wrong_at DESC"
        ).fetchall()
        result = []
        for r in rows:
            w = dict(r)
            try:
                w["options"] = json.loads(w.get("options") or "[]")
            except (ValueError, TypeError):
                w["options"] = []
            result.append(w)
        return result
    finally:
        conn.close()


def get_wrong_question(wid) -> dict | None:
    """按 id 查错题，不存在返回 None。"""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM wrong_questions WHERE id = ?", (wid,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def practice_submit(results: list[dict]) -> int:
    """错题重练判分落库：results 每项含 id/ok/choice。
    答对 → resolved=1；答错 → wrong_count+1、更新 user_answer 与 last_wrong_at。
    返回答对（已标记掌握）条数。
    """
    conn = get_conn()
    try:
        ts = now_str()
        resolved_count = 0
        for r in results:
            if r["ok"]:
                conn.execute(
                    "UPDATE wrong_questions SET resolved = 1, last_wrong_at = ? WHERE id = ?",
                    (ts, r["id"]),
                )
                resolved_count += 1
            else:
                conn.execute(
                    "UPDATE wrong_questions SET wrong_count = wrong_count + 1, "
                    "user_answer = ?, last_wrong_at = ? WHERE id = ?",
                    (r.get("choice", -1), ts, r["id"]),
                )
        conn.commit()
        return resolved_count
    finally:
        conn.close()


def set_resolved(wid) -> bool:
    """手动标记错题为已掌握，成功返回 True（记录不存在返回 False）。"""
    conn = get_conn()
    try:
        cur = conn.execute(
            "UPDATE wrong_questions SET resolved = 1 WHERE id = ?", (wid,)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# ---------- 偏好设置（key-value） ----------

def get_pref(key: str) -> str | None:
    """读取偏好值，不存在返回 None。"""
    conn = get_conn()
    try:
        row = conn.execute("SELECT value FROM prefs WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None
    finally:
        conn.close()


def set_pref(key: str, value: str) -> None:
    """写入偏好值（UPSERT）。"""
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO prefs (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        conn.commit()
    finally:
        conn.close()
