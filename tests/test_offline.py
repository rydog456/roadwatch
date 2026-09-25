from pathlib import Path
import time

from infra_pulse.hub import accept_records
from infra_pulse.offline import DELAYED_AFTER_S, Outbox, drain


def test_offline_scan_is_queued_not_dropped(tmp_path: Path):
    box = Outbox(tmp_path / "outbox.sqlite")
    rid = box.enqueue({"kind": "impact", "az": 2.4}, online=False, captured_at=time.time())
    stats = box.stats()
    assert stats["pending"] == 1
    assert rid
    # Radio still down: drain must not delete the row
    result = drain(box, "http://hub.invalid", online=False)
    assert result["reason"] == "offline"
    assert box.stats()["pending"] == 1


def test_reconnect_marks_delayed(tmp_path: Path):
    box = Outbox(tmp_path / "outbox.sqlite")
    old = time.time() - (DELAYED_AFTER_S + 5)
    rid = box.enqueue({"kind": "heartbeat"}, online=False, captured_at=old)
    ingested = []

    def poster(_hub, items):
        ingested.extend(items)

    result = drain(box, "local", poster=poster, online=True)
    assert result["synced"] == 1
    assert result["pending"] == 0
    row = box.conn.execute("SELECT delayed, status FROM outbox WHERE id=?", (rid,)).fetchone()
    assert row == (1, "synced")
    assert ingested[0]["_meta"]["online_at_capture"] is False


def test_hub_accepts_delayed_batch(tmp_path: Path):
    db = tmp_path / "hub.sqlite"
    rec = {
        "id": "abc",
        "kind": "impact",
        "_meta": {"id": "abc", "captured_at": time.time() - 90, "online_at_capture": False},
    }
    out = accept_records([rec], db=db)
    assert out["accepted"] == 1
    assert out["delayed_in_batch"] == 1
    assert out["hub_delayed"] == 1
