"""批次狀態機 + SQLite 持久化。

狀態流轉:
    GENERATING ─────────────► AWAITING_REVIEW
    AWAITING_REVIEW ─(修改)─► AWAITING_EDIT ─(收到文字)─► GENERATING ─► AWAITING_REVIEW
    AWAITING_REVIEW ─(重生)─► GENERATING ─► AWAITING_REVIEW
    AWAITING_REVIEW ─(發布)─► SENDING ─► SENT / FAILED

user_context 記住「某位使用者現在正等著改哪一批」,webhook 收到純文字時靠它判斷。
"""
import json
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Optional

from .config import get_settings

# ── 狀態常數 ─────────────────────────────────────────────
GENERATING = "GENERATING"
AWAITING_REVIEW = "AWAITING_REVIEW"
AWAITING_EDIT = "AWAITING_EDIT"
SENDING = "SENDING"
SENT = "SENT"
FAILED = "FAILED"


@dataclass
class Batch:
    id: int
    status: str
    source_ref: str = ""            # 對應來源分頁的列(例如 row index 或自訂鍵)
    subject: str = ""
    body_html: str = ""
    recipients: list = field(default_factory=list)   # 已解析出的 email
    results: list = field(default_factory=list)       # [{email, ok, error}]
    created_at: float = 0.0
    updated_at: float = 0.0


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(get_settings().database_path)
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    with _conn() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                status TEXT NOT NULL,
                source_ref TEXT DEFAULT '',
                subject TEXT DEFAULT '',
                body_html TEXT DEFAULT '',
                recipients TEXT DEFAULT '[]',
                results TEXT DEFAULT '[]',
                created_at REAL,
                updated_at REAL
            )"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS user_context (
                user_id TEXT PRIMARY KEY,
                batch_id INTEGER,
                updated_at REAL
            )"""
        )


def _row_to_batch(r: sqlite3.Row) -> Batch:
    return Batch(
        id=r["id"],
        status=r["status"],
        source_ref=r["source_ref"],
        subject=r["subject"],
        body_html=r["body_html"],
        recipients=json.loads(r["recipients"]),
        results=json.loads(r["results"]),
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def create_batch(source_ref: str) -> Batch:
    now = time.time()
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO batches (status, source_ref, created_at, updated_at) VALUES (?,?,?,?)",
            (GENERATING, source_ref, now, now),
        )
        new_id = cur.lastrowid
    # with 區塊結束才會 commit,故離開後再查
    return get_batch(new_id)  # type: ignore[arg-type]


def get_batch(batch_id: int) -> Optional[Batch]:
    with _conn() as c:
        r = c.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()
        return _row_to_batch(r) if r else None


def update_batch(batch_id: int, **fields) -> None:
    if not fields:
        return
    fields["updated_at"] = time.time()
    for k in ("recipients", "results"):
        if k in fields:
            fields[k] = json.dumps(fields[k], ensure_ascii=False)
    cols = ", ".join(f"{k}=?" for k in fields)
    with _conn() as c:
        c.execute(f"UPDATE batches SET {cols} WHERE id=?", (*fields.values(), batch_id))


# ── 使用者對話情境 ────────────────────────────────────────
def set_user_context(user_id: str, batch_id: int) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO user_context (user_id, batch_id, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET batch_id=excluded.batch_id, updated_at=excluded.updated_at",
            (user_id, batch_id, time.time()),
        )


def get_user_context(user_id: str) -> Optional[int]:
    with _conn() as c:
        r = c.execute("SELECT batch_id FROM user_context WHERE user_id=?", (user_id,)).fetchone()
        return r["batch_id"] if r else None


def clear_user_context(user_id: str) -> None:
    with _conn() as c:
        c.execute("DELETE FROM user_context WHERE user_id=?", (user_id,))
