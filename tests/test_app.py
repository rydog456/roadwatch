from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from infra_pulse.offline import RadioCache


def test_radio_cache_respects_force_offline(monkeypatch):
    monkeypatch.setenv("INFRA_PULSE_FORCE_OFFLINE", "1")
    cache = RadioCache(ttl_s=60)
    assert cache.check() is False
    assert cache.check() is False  # cached, still no extra probe required


def test_dashboard_health_and_run():
    from fastapi.testclient import TestClient
    from dashboard.app import app

    client = TestClient(app)
    h = client.get("/api/health")
    assert h.status_code == 200
    assert h.json()["ok"] is True
    page = client.get("/")
    assert page.status_code == 200
    run = client.get("/api/run")
    assert run.status_code == 200
    body = run.json()
    assert body["summary"]["segments"] >= 8
    assert "events" in body
