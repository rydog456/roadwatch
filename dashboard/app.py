from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from infra_pulse.city_store import defect_record, load_defects, upsert_defect
from infra_pulse.costing import estimate_repair
from infra_pulse.hub import accept_records, list_recent
from infra_pulse.iphone import IPhoneMotion
from infra_pulse.models import GeoPoint
from infra_pulse.offline import Outbox, drain
from infra_pulse.scene_store import ingest_scan
from infra_pulse.simulate import run_demo

DATA = ROOT / "data" / "demo_run.json"
CITY = ROOT / "data" / "city_map.json"
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
    return {"ok": True, "product": "InfraPulse", "capture": "iphone-pro-max", "online": True}


class SceneIngest(BaseModel):
    contributor_id: str
    lat: float
    lon: float
    heading_deg: float = 0.0
    xyz: list[list[float]]
    pitch: float = 0.0
    roll: float = 0.0
    baro_hpa: float | None = None
    notes: str = ""
    live_factors: bool = True
    landslide_risk: float = 0.0
    wildfire_risk: float = 0.0


@app.post("/api/scene")
def scene_ingest(body: SceneIngest):
    loc = GeoPoint(lat=body.lat, lon=body.lon, heading_deg=body.heading_deg)
    motion = IPhoneMotion(pitch=body.pitch, roll=body.roll, baro_hpa=body.baro_hpa)
    result = ingest_scan(
        loc,
        np.asarray(body.xyz, dtype=float),
        body.contributor_id,
        extra={"notes": body.notes} if body.notes else None,
        motion=motion,
    )
    estimate = estimate_repair(
        result,
        body.lat,
        body.lon,
        fetch_live=body.live_factors,
        landslide_risk=body.landslide_risk,
        wildfire_risk=body.wildfire_risk,
    )
    record = upsert_defect(
        defect_record(result, body.lat, body.lon, body.contributor_id, estimate.model_dump(), body.notes),
        CITY,
    )
    return {"lidar": result.model_dump(), "cost": estimate.model_dump(), "map": record}


@app.get("/api/city")
def city_map():
    return {"defects": load_defects(CITY)}


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
