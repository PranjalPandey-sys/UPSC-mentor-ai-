"""
storage/database.py — Storage Layer (SQLite for testing, Postgres-ready)
============================================================================
This bot ships with SQLite so you can run it standalone with zero infra —
appropriate for "test all the AI features" per the brief. The schema below
mirrors storage/migrations/001_init.sql field-for-field. When you're ready
for production, set DB_ENGINE=postgres + DATABASE_URL and swap the driver
calls in this file for asyncpg — the function signatures above this layer
(context_builder.py, memory_extractor.py, handlers/*) do not change.
"""
import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone

import config

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(config.SQLITE_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
    return _conn


def init_db() -> None:
    conn = _get_conn()
    with _lock:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT DEFAULT '',
                full_name TEXT DEFAULT '',
                level TEXT DEFAULT 'beginner',
                timeline_months INTEGER DEFAULT 6,
                phase TEXT DEFAULT '',
                optional_subject TEXT DEFAULT '',
                weak_subjects TEXT DEFAULT '[]',
                turn_counter INTEGER DEFAULT 0,
                main_bot_linked INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT,
                last_active TEXT
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                feature TEXT DEFAULT 'doubt',
                created_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_chat_user_time ON chat_messages(user_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS user_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                category TEXT NOT NULL,
                fact TEXT NOT NULL,
                confidence REAL DEFAULT 1.0,
                active INTEGER DEFAULT 1,
                created_at TEXT,
                updated_at TEXT,
                UNIQUE(user_id, category, fact)
            );

            CREATE TABLE IF NOT EXISTS user_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                period TEXT NOT NULL,
                summary TEXT NOT NULL,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS mentor_insights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                insight_type TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS study_progress (
                user_id INTEGER PRIMARY KEY,
                streak INTEGER DEFAULT 0,
                best_streak INTEGER DEFAULT 0,
                days_done INTEGER DEFAULT 0,
                answers_written INTEGER DEFAULT 0,
                mocks_taken INTEGER DEFAULT 0,
                last_active TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS performance_trends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                metric TEXT NOT NULL,
                value REAL NOT NULL,
                subject TEXT DEFAULT '',
                recorded_at TEXT
            );

            CREATE TABLE IF NOT EXISTS uploaded_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                doc_type TEXT DEFAULT 'photo',
                extracted_text TEXT,
                related_feature TEXT DEFAULT '',
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS news_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                topic TEXT NOT NULL,
                summary TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id INTEGER PRIMARY KEY,
                language TEXT DEFAULT 'en',
                response_length TEXT DEFAULT 'standard',
                notify_weekly INTEGER DEFAULT 1,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                recorded_at TEXT
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                event_type TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS ai_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                feature TEXT NOT NULL,
                prompt_tokens INTEGER DEFAULT 0,
                completion_tokens INTEGER DEFAULT 0,
                finish_reason TEXT DEFAULT '',
                latency_ms INTEGER DEFAULT 0,
                success INTEGER DEFAULT 1,
                created_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_ai_sessions_feature ON ai_sessions(feature, created_at DESC);
            """
        )
        conn.commit()
    logger.info("✅ DB initialised (SQLite testing store) at %s", config.SQLITE_PATH)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Users ───────────────────────────────────────────────────────────────────

async def ensure_user(user_id: int, username: str = "", full_name: str = "") -> None:
    conn = _get_conn()
    with _lock:
        row = conn.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,)).fetchone()
        if row:
            conn.execute("UPDATE users SET last_active=? WHERE user_id=?", (_now(), user_id))
        else:
            conn.execute(
                "INSERT INTO users (user_id, username, full_name, created_at, updated_at, last_active) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, username, full_name, _now(), _now(), _now()),
            )
            conn.execute(
                "INSERT OR IGNORE INTO study_progress (user_id, updated_at) VALUES (?, ?)",
                (user_id, _now()),
            )
        conn.commit()


async def get_user_profile(user_id: int) -> dict | None:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    return dict(row) if row else None


async def update_user_profile(user_id: int, **fields) -> None:
    if not fields:
        return
    conn = _get_conn()
    cols = ", ".join(f"{k}=?" for k in fields)
    with _lock:
        conn.execute(
            f"UPDATE users SET {cols}, updated_at=? WHERE user_id=?",
            (*fields.values(), _now(), user_id),
        )
        conn.commit()


async def increment_turn_counter(user_id: int) -> int:
    conn = _get_conn()
    with _lock:
        conn.execute("UPDATE users SET turn_counter = turn_counter + 1 WHERE user_id=?", (user_id,))
        conn.commit()
        row = conn.execute("SELECT turn_counter FROM users WHERE user_id=?", (user_id,)).fetchone()
    return row["turn_counter"] if row else 0


# ── Chat messages (rolling window) ─────────────────────────────────────────

async def log_message(user_id: int, role: str, content: str, feature: str = "doubt") -> None:
    conn = _get_conn()
    with _lock:
        conn.execute(
            "INSERT INTO chat_messages (user_id, role, content, feature, created_at) VALUES (?,?,?,?,?)",
            (user_id, role, content, feature, _now()),
        )
        # Keep only the most recent 50 per user — chat_messages is a rolling
        # window, not permanent storage. Durable facts go to user_memories.
        conn.execute(
            """DELETE FROM chat_messages WHERE user_id=? AND id NOT IN (
                   SELECT id FROM chat_messages WHERE user_id=? ORDER BY id DESC LIMIT 50
               )""",
            (user_id, user_id),
        )
        conn.commit()


async def get_recent_messages(user_id: int, limit: int = 8) -> list[str]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT role, content FROM chat_messages WHERE user_id=? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    return [f"{r['role']}: {r['content']}" for r in reversed(rows)]


# ── Memories ────────────────────────────────────────────────────────────────

async def upsert_memory(user_id: int, category: str, fact: str) -> None:
    conn = _get_conn()
    with _lock:
        conn.execute(
            """INSERT INTO user_memories (user_id, category, fact, active, created_at, updated_at)
               VALUES (?,?,?,1,?,?)
               ON CONFLICT(user_id, category, fact) DO UPDATE SET
                   active=1, updated_at=excluded.updated_at""",
            (user_id, category, fact, _now(), _now()),
        )
        conn.commit()


async def get_active_memories(user_id: int, limit: int = 25) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT category, fact FROM user_memories WHERE user_id=? AND active=1 "
        "ORDER BY updated_at DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


async def deactivate_memory(memory_id: int) -> None:
    conn = _get_conn()
    with _lock:
        conn.execute("UPDATE user_memories SET active=0 WHERE id=?", (memory_id,))
        conn.commit()


# ── Summaries / progress ───────────────────────────────────────────────────

async def get_latest_summary(user_id: int) -> str | None:
    conn = _get_conn()
    row = conn.execute(
        "SELECT summary FROM user_summaries WHERE user_id=? ORDER BY id DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    return row["summary"] if row else None


async def save_summary(user_id: int, period: str, summary: str) -> None:
    conn = _get_conn()
    with _lock:
        conn.execute(
            "INSERT INTO user_summaries (user_id, period, summary, created_at) VALUES (?,?,?,?)",
            (user_id, period, summary, _now()),
        )
        conn.commit()


async def get_study_progress(user_id: int) -> dict | None:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM study_progress WHERE user_id=?", (user_id,)).fetchone()
    return dict(row) if row else None


async def record_performance(user_id: int, metric: str, value: float, subject: str = "") -> None:
    conn = _get_conn()
    with _lock:
        conn.execute(
            "INSERT INTO performance_trends (user_id, metric, value, subject, recorded_at) VALUES (?,?,?,?,?)",
            (user_id, metric, value, subject, _now()),
        )
        conn.commit()


# ── AI session logging (this is your truncation-bug tripwire) ─────────────

async def log_ai_session(
    user_id: int,
    feature: str,
    completion_tokens: int,
    finish_reason: str,
    latency_ms: int,
    success: bool,
) -> None:
    conn = _get_conn()
    with _lock:
        conn.execute(
            """INSERT INTO ai_sessions
               (user_id, feature, completion_tokens, finish_reason, latency_ms, success, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (user_id, feature, completion_tokens, finish_reason, latency_ms, int(success), _now()),
        )
        conn.commit()


async def get_truncation_rate(hours: int = 24) -> dict:
    """Admin panel metric: how often responses are hitting max_tokens."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT finish_reason, COUNT(*) as n FROM ai_sessions "
        "WHERE created_at >= datetime('now', ?) GROUP BY finish_reason",
        (f"-{hours} hours",),
    ).fetchall()
    return {r["finish_reason"]: r["n"] for r in rows}


# ── Admin / analytics ───────────────────────────────────────────────────────

async def get_admin_stats() -> dict:
    conn = _get_conn()
    total_users = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
    active_today = conn.execute(
        "SELECT COUNT(*) c FROM users WHERE last_active >= datetime('now', '-1 day')"
    ).fetchone()["c"]
    ai_requests_today = conn.execute(
        "SELECT COUNT(*) c FROM ai_sessions WHERE created_at >= datetime('now', '-1 day')"
    ).fetchone()["c"]
    errors_today = conn.execute(
        "SELECT COUNT(*) c FROM ai_sessions WHERE created_at >= datetime('now', '-1 day') AND success=0"
    ).fetchone()["c"]
    truncation = await get_truncation_rate(24)
    return {
        "total_users": total_users,
        "active_today": active_today,
        "ai_requests_today": ai_requests_today,
        "errors_today": errors_today,
        "finish_reason_breakdown_24h": truncation,
    }


# ── Integration hook: import a user from the main UPSC bot's DB ───────────

async def import_user_from_main_bot(user_id: int, level: str, timeline_months: int,
                                     weak_subjects: list[str]) -> None:
    """
    Optional bridge: call this once you decide to wire the two bots
    together (see README §5 Integration Plan). Not called automatically —
    this testing bot stays fully isolated until you invoke it.
    """
    await ensure_user(user_id)
    await update_user_profile(
        user_id,
        level=level,
        timeline_months=timeline_months,
        weak_subjects=json.dumps(weak_subjects),
        main_bot_linked=1,
    )
