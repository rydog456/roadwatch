from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from infra_pulse.hub import accept_records, list_recent
from infra_pulse.offline import Outbox, drain
from infra_pulse.simulate import run_demo

DATA = ROOT / "data" / "demo_run.json"
STATIC = Path(__file__).resolve().parent / "static"
DEVICE_DB = ROOT / "data" / "device_outbox.sqlite"
HUB_DB = ROOT / "data" / "hub.sqlite"

app = FastAPI(title="InfraPulse")
if STATIC.exists():
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

_outbox: Outbox | None = None


def device_outbox() -> Outbox:
    global _outbox
    if _outbox is None:
        _outbox = Outbox(DEVICE_DB)
    return _outbox


class IngestBody(BaseModel):
    records: list[dict]


@app.get("/", response_class=HTMLResponse)
def index():
    index_path = STATIC / "index.html"
    if not index_path.exists():
        return HTMLResponse("<p>Dashboard static files missing.</p>", status_code=500)
    return FileResponse(index_path)


@app.get("/api/run")
def api_run(refresh: bool = False):
    if refresh or not DATA.exists():
        return run_demo(DATA)
    return json.loads(DATA.read_text(encoding="utf-8"))


@app.get("/api/health")
def health():
    return {"ok": True, "product": "InfraPulse", "online": True}


@app.post("/api/ingest")
def ingest(body: IngestBody):
    return accept_records(body.records, db=HUB_DB)


@app.get("/api/hub")
def hub_feed():
    return {"records": list_recent(80, db=HUB_DB)}


@app.get("/api/outbox")
def outbox_stats():
    stats = device_outbox().stats(probe_radio=True)
    stats["force_offline"] = os.environ.get("INFRA_PULSE_FORCE_OFFLINE", "").strip() in {
        "1",
        "true",
        "yes",
    }
    return stats


@app.post("/api/sync-now")
def sync_now():
    """Flush device outbox into this hub without a nested HTTP call (avoids deadlock)."""
    box = device_outbox()

    def poster(_hub, items):
        accept_records(items, db=HUB_DB)

    return drain(box, "local-hub", poster=poster, online=True)
