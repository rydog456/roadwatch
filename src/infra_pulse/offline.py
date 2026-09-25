from __future__ import annotations

import json
import os
import socket
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Optional
from urllib import error, request

DEFAULT_DB = Path("data/device_outbox.sqlite")
DELAYED_AFTER_S = 20.0


class RadioCache:
    """Do not probe the network at IMU rate — that stalls logging in a dead zone."""

    def __init__(self, hub_url: Optional[str] = None, ttl_s: float = 5.0):
        self.hub_url = hub_url
        self.ttl_s = ttl_s
        self._at = 0.0
        self._ok = False

    def check(self) -> bool:
        now = time.time()
        if now - self._at >= self.ttl_s:
            self._ok = is_online(self.hub_url)
            self._at = now
        return self._ok


def is_online(hub_url: Optional[str] = None, timeout_s: float = 2.0) -> bool:
    """True if we can reach the hub (or a public DNS fallback).

    Set INFRA_PULSE_FORCE_OFFLINE=1 to simulate tunnels / rural dead zones.
    """
    if os.environ.get("INFRA_PULSE_FORCE_OFFLINE", "").strip() in {"1", "true", "yes"}:
        return False
    if hub_url:
        try:
            health = hub_url.rstrip("/") + "/api/health"
            req = request.Request(health, method="GET")
            with request.urlopen(req, timeout=timeout_s) as resp:
                return 200 <= getattr(resp, "status", 200) < 500
        except Exception:
            return False
    try:
        socket.create_connection(("1.1.1.1", 443), timeout=timeout_s).close()
        return True
    except OSError:
        return False


class Outbox:
    """Crash-safe local queue. Scan/log never waits on the network."""

    def __init__(self, path: Path = DEFAULT_DB):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(str(path), check_same_thread=False, timeout=30)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS outbox (
                id TEXT PRIMARY KEY,
                captured_at REAL NOT NULL,
                online_at_capture INTEGER NOT NULL,
                payload TEXT NOT NULL,
                image_path TEXT,
                status TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                synced_at REAL,
                delayed INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        self.conn.commit()

    def enqueue(
        self,
        payload: dict[str, Any],
        image_path: Optional[str] = None,
        online: Optional[bool] = None,
        captured_at: Optional[float] = None,
    ) -> str:
        rec_id = payload.get("id") or str(uuid.uuid4())
        payload = {**payload, "id": rec_id}
        ts = captured_at if captured_at is not None else time.time()
        on = 1 if (is_online() if online is None else online) else 0
        with self._lock:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO outbox
                (id, captured_at, online_at_capture, payload, image_path, status, attempts, delayed)
                VALUES (?, ?, ?, ?, ?, 'pending', 0, 0)
                """,
                (rec_id, ts, on, json.dumps(payload), image_path),
            )
            self.conn.commit()
        return rec_id

    def pending(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT id, captured_at, online_at_capture, payload, image_path, attempts
                FROM outbox WHERE status IN ('pending', 'failed')
                ORDER BY captured_at ASC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        out = []
        for rid, cap, on, payload, image, attempts in rows:
            body = json.loads(payload)
            body["_meta"] = {
                "id": rid,
                "captured_at": cap,
                "online_at_capture": bool(on),
                "image_path": image,
                "attempts": attempts,
            }
            out.append(body)
        return out

    def mark_synced(self, rec_id: str, synced_at: Optional[float] = None) -> None:
        now = synced_at if synced_at is not None else time.time()
        with self._lock:
            row = self.conn.execute(
                "SELECT captured_at, online_at_capture FROM outbox WHERE id=?", (rec_id,)
            ).fetchone()
            if not row:
                return
            captured, online_cap = row
            delayed = 1 if (not online_cap) or (now - captured >= DELAYED_AFTER_S) else 0
            self.conn.execute(
                """
                UPDATE outbox SET status='synced', synced_at=?, delayed=?, last_error=NULL
                WHERE id=?
                """,
                (now, delayed, rec_id),
            )
            self.conn.commit()

    def mark_failed(self, rec_id: str, err: str) -> None:
        with self._lock:
            self.conn.execute(
                """
                UPDATE outbox SET status='failed', attempts=attempts+1, last_error=?
                WHERE id=?
                """,
                (err[:500], rec_id),
            )
            self.conn.commit()

    def stats(self, probe_radio: bool = False) -> dict[str, Any]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT status, COUNT(*), SUM(delayed) FROM outbox GROUP BY status"
            ).fetchall()
            delayed = self.conn.execute(
                "SELECT COUNT(*) FROM outbox WHERE delayed=1"
            ).fetchone()[0]
            pending = self.conn.execute(
                "SELECT COUNT(*) FROM outbox WHERE status IN ('pending','failed')"
            ).fetchone()[0]
        by_status = {s: {"count": c, "delayed": d or 0} for s, c, d in rows}
        return {
            "by_status": by_status,
            "pending": pending,
            "delayed_synced": delayed,
            "online_now": is_online() if probe_radio else None,
        }

    def close(self) -> None:
        self.conn.close()


def post_batch(hub_url: str, records: list[dict[str, Any]], timeout_s: float = 8.0) -> None:
    url = hub_url.rstrip("/") + "/api/ingest"
    body = json.dumps({"records": records}).encode("utf-8")
    req = request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with request.urlopen(req, timeout=timeout_s) as resp:
        if getattr(resp, "status", 200) >= 400:
            raise RuntimeError(f"hub {resp.status}")


def drain(
    outbox: Outbox,
    hub_url: str,
    batch: int = 25,
    poster=None,
    online: Optional[bool] = None,
) -> dict[str, Any]:
    """Push pending rows. No-op (not an error) while offline — logging already happened."""
    reachable = is_online(hub_url) if online is None else online
    if not reachable:
        return {"synced": 0, "pending": outbox.stats()["pending"], "reason": "offline"}
    items = outbox.pending(limit=batch)
    if not items:
        return {"synced": 0, "pending": 0, "reason": "empty"}
    send = poster or post_batch
    synced = 0
    try:
        send(hub_url, items)
        now = time.time()
        for item in items:
            outbox.mark_synced(item["_meta"]["id"], now)
            synced += 1
        return {"synced": synced, "pending": outbox.stats()["pending"], "reason": "ok"}
    except (error.URLError, TimeoutError, OSError, RuntimeError) as exc:
        for item in items:
            outbox.mark_failed(item["_meta"]["id"], str(exc))
        return {"synced": 0, "pending": outbox.stats()["pending"], "reason": str(exc)}


def sync_loop(outbox: Outbox, hub_url: str, interval_s: float = 15.0, stop: Optional[threading.Event] = None) -> None:
    halt = stop or threading.Event()
    while not halt.is_set():
        drain(outbox, hub_url)
        halt.wait(interval_s)
