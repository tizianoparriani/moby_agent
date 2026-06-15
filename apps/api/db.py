from __future__ import annotations
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager

from apps.api.settings import settings


@contextmanager
def _conn():
    con = sqlite3.connect(settings.DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db() -> None:
    db_dir = os.path.dirname(settings.DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT    UNIQUE NOT NULL,
                password_hash TEXT    NOT NULL,
                is_admin      INTEGER NOT NULL DEFAULT 0,
                created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS queries (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id        INTEGER NOT NULL REFERENCES users(id),
                endpoint       TEXT    NOT NULL,
                query          TEXT    NOT NULL,
                answer         TEXT,
                citations_json TEXT,
                created_at     TEXT    NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS invite_codes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                code        TEXT    UNIQUE NOT NULL,
                created_by  INTEGER NOT NULL REFERENCES users(id),
                used_by     INTEGER REFERENCES users(id),
                used_at     TEXT,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            );
        """)


def get_user_by_username(username: str) -> dict | None:
    with _conn() as con:
        row = con.execute(
            "SELECT id, username, password_hash, is_admin FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    return dict(row) if row else None


def create_user(username: str, password_hash: str, is_admin: bool = False) -> dict | None:
    try:
        with _conn() as con:
            con.execute(
                "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)",
                (username, password_hash, int(is_admin)),
            )
        return get_user_by_username(username)
    except sqlite3.IntegrityError:
        return None  # username taken


def upsert_admin(username: str, password_hash: str) -> None:
    with _conn() as con:
        row = con.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if row:
            con.execute(
                "UPDATE users SET password_hash = ?, is_admin = 1 WHERE id = ?",
                (password_hash, row["id"]),
            )
        else:
            con.execute(
                "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, 1)",
                (username, password_hash),
            )


def count_today_queries(user_id: int) -> int:
    with _conn() as con:
        row = con.execute(
            "SELECT COUNT(*) FROM queries WHERE user_id = ? AND date(created_at) = date('now')",
            (user_id,),
        ).fetchone()
    return row[0] if row else 0


def save_query(
    user_id: int,
    endpoint: str,
    query: str,
    answer: str | None = None,
    citations_json: str | None = None,
) -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO queries (user_id, endpoint, query, answer, citations_json) VALUES (?, ?, ?, ?, ?)",
            (user_id, endpoint, query, answer, citations_json),
        )


def get_user_history(user_id: int, limit: int = 50) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            """SELECT id, endpoint, query, answer, citations_json, created_at
               FROM queries WHERE user_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["citations"] = json.loads(d.pop("citations_json")) if d.get("citations_json") else []
        result.append(d)
    return result


def get_all_usage() -> list[dict]:
    with _conn() as con:
        rows = con.execute("""
            SELECT
                u.username,
                u.is_admin,
                COUNT(q.id) AS total_queries,
                SUM(CASE WHEN date(q.created_at) = date('now') THEN 1 ELSE 0 END) AS today_queries
            FROM users u
            LEFT JOIN queries q ON q.user_id = u.id
            GROUP BY u.id
            ORDER BY total_queries DESC
        """).fetchall()
    return [dict(r) for r in rows]


# ── invite codes ──────────────────────────────────────────────────────────────

def create_invite_code(created_by: int) -> str:
    code = secrets.token_urlsafe(12)
    with _conn() as con:
        con.execute(
            "INSERT INTO invite_codes (code, created_by) VALUES (?, ?)",
            (code, created_by),
        )
    return code


def consume_invite_code(code: str, used_by: int) -> bool:
    """Mark the code as used. Returns False if code is invalid or already used."""
    with _conn() as con:
        row = con.execute(
            "SELECT id FROM invite_codes WHERE code = ? AND used_by IS NULL",
            (code,),
        ).fetchone()
        if not row:
            return False
        con.execute(
            "UPDATE invite_codes SET used_by = ?, used_at = datetime('now') WHERE id = ?",
            (used_by, row["id"]),
        )
    return True


def get_invite_codes(created_by: int) -> list[dict]:
    with _conn() as con:
        rows = con.execute("""
            SELECT ic.code, ic.created_at, ic.used_at,
                   u.username AS used_by_username
            FROM invite_codes ic
            LEFT JOIN users u ON u.id = ic.used_by
            WHERE ic.created_by = ?
            ORDER BY ic.created_at DESC
        """, (created_by,)).fetchall()
    return [dict(r) for r in rows]
