"""SQLite 连接管理与建表。"""

import sqlite3
from datetime import datetime

from app.config import get_paths

# 全部表结构（幂等建表）
_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'planning',
    replan_pending INTEGER DEFAULT 0,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS knowledge_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    idx INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    mastery REAL DEFAULT 0,
    status TEXT DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    filename TEXT,
    stored_path TEXT,
    chunks INTEGER DEFAULT 0,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS prefs (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def get_conn() -> sqlite3.Connection:
    """获取新的数据库连接，调用方负责关闭。"""
    conn = sqlite3.connect(get_paths()["db_path"], check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def now_str() -> str:
    """当前时间戳（秒级 ISO 字符串）。"""
    return datetime.now().isoformat(timespec="seconds")


def init_db() -> None:
    """初始化数据库：建表（幂等，可重复调用）。"""
    conn = get_conn()
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()
