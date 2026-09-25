from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

HUB_DB = Path("data/hub.sqlite")


def _conn(path: Path = HUB_DB) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(path), check_same_thread=False, timeout=30)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS ingest (
            id TEXT PRIMARY KEY,
            received_at REAL NOT NULL,
            captured_at REAL,
            delayed INTEGER NOT NULL DEFAULT 0,
            payload TEXT NOT NULL
        )
        """
    )
    c.commit()
    return c


def accept_records(records: list[dict[str, Any]], db: Path = HUB_DB) -> dict[str, Any]:
    c = _conn(db)
    now = time.time()
    n = 0
    delayed = 0
    for rec in records:
        meta = rec.get("_meta") or {}
        rec_id = meta.get("id") or rec.get("id")
        if not rec_id:
            continue
        captured = float(meta.get("captured_at") or rec.get("captured_at") or now)
        is_delayed = int(not meta.get("online_at_capture", True) or (now - captured >= 20))
        delayed += is_delayed
        c.execute(
            """
            INSERT OR REPLACE INTO ingest (id, received_at, captured_at, delayed, payload)
            VALUES (?, ?, ?, ?, ?)
            """,
            (rec_id, now, captured, is_delayed, json.dumps(rec)),
        )
        n += 1
    c.commit()
    total = c.execute("SELECT COUNT(*) FROM ingest").fetchone()[0]
    delayed_total = c.execute("SELECT COUNT(*) FROM ingest WHERE delayed=1").fetchone()[0]
    c.close()
    return {"accepted": n, "delayed_in_batch": delayed, "hub_total": total, "hub_delayed": delayed_total}


def list_recent(limit: int = 50, db: Path = HUB_DB) -> list[dict[str, Any]]:
    if not db.exists():
        return []
    c = _conn(db)
    rows = c.execute(
        "SELECT id, received_at, captured_at, delayed, payload FROM ingest ORDER BY captured_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    c.close()
    out = []
    for rid, recv, cap, delayed, payload in rows:
        body = json.loads(payload)
        body["hub"] = {
            "id": rid,
            "received_at": recv,
            "captured_at": cap,
            "delay_s": round((recv or cap) - (cap or recv), 1),
            "delayed": bool(delayed),
        }
        out.append(body)
    return out
