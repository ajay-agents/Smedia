import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from src.config import get_secret

DB_PATH = get_secret("DB_PATH", "data/smedia.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS generations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    mode TEXT NOT NULL,
    platform TEXT NOT NULL,
    variant_index INTEGER NOT NULL,
    content_type TEXT NOT NULL,       -- 'text' or 'image'
    content TEXT NOT NULL,            -- text body or image file path
    edited_content TEXT,              -- user edit, if any
    provider_used TEXT,
    approval_status TEXT NOT NULL DEFAULT 'pending',  -- pending|approved|rejected
    created_at TEXT NOT NULL
);
"""


@contextmanager
def get_conn():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute(SCHEMA)


def save_generation(topic, mode, platform, variant_index, content_type, content, provider_used, approval_status="pending"):
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO generations
               (topic, mode, platform, variant_index, content_type, content, provider_used, approval_status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                topic,
                mode,
                platform,
                variant_index,
                content_type,
                content,
                provider_used,
                approval_status,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        return cur.lastrowid


def update_generation(row_id, approval_status=None, edited_content=None):
    with get_conn() as conn:
        if approval_status is not None:
            conn.execute("UPDATE generations SET approval_status = ? WHERE id = ?", (approval_status, row_id))
        if edited_content is not None:
            conn.execute("UPDATE generations SET edited_content = ? WHERE id = ?", (edited_content, row_id))


def get_history(platform=None, approval_status=None, limit=200):
    query = "SELECT * FROM generations WHERE 1=1"
    params = []
    if platform:
        query += " AND platform = ?"
        params.append(platform)
    if approval_status:
        query += " AND approval_status = ?"
        params.append(approval_status)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_distinct_topics(limit=50):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT topic FROM generations ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [r["topic"] for r in rows]
