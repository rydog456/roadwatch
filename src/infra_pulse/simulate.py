from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from infra_pulse.models import BoundingBox, DistressClass, GeoPoint, VisionResult
from infra_pulse.pipeline import InfraPulsePipeline
from infra_pulse.vision import _vision_severity


def _imu_modal(freq: float = 3.2, amp: float = 0.28, n: int = 256, hz: float = 100.0, seed: int = 0) -> np.ndarray:
    t = np.arange(n) / hz
    rng = np.random.default_rng(seed)
    z = 1.0 + amp * np.sin(2 * np.pi * freq * t) + rng.normal(0, 0.02, n)
    xy = rng.normal(0, 0.015, size=(n, 2))
    return np.column_stack([xy, z])


def _imu_window(peak_g: float, n: int = 50, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    z = rng.normal(1.0, 0.08, size=n)
    if peak_g > 0:
        z[n // 2] += peak_g
    xy = rng.normal(0, 0.05, size=(n, 2))
    return np.column_stack([xy, z])


def _lidar_flat(n: int = 400, hole_mm: float = 0.0, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    x = rng.uniform(-1.5, 1.5, n)
    y = rng.uniform(-0.6, 0.6, n)
    z = rng.normal(0, 0.003, n)
    if hole_mm > 0:
        mask = (np.abs(x) < 0.25) & (np.abs(y) < 0.25)
        z[mask] -= hole_mm / 1000.0
    return np.column_stack([x, y, z])


def _thermal(delta: float = 0.4, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    frame = rng.normal(28.0, 0.3, size=(24, 32))
    if delta >= 2.5:
        frame[10:14, 14:18] += delta
    return frame


def _vision(label: DistressClass | None, conf: float, area: float) -> VisionResult:
    dets: list[BoundingBox] = []
    if label is not None:
        dets = [
            BoundingBox(
                x1=120, y1=180, x2=280, y2=300,
                confidence=conf, label=label, area_ratio=area,
            )
        ]
    return VisionResult(
        detections=dets,
        severity=_vision_severity(dets),
        confidence=conf if dets else 0.1,
        source="demo",
    )


# Downtown-ish corridor used only so the map has real-looking pins.
START = (34.0522, -118.2437)

SEGMENTS = [
    dict(name="healthy", peak=0.2, hole=2, tdelta=0.4, crit=40, traf=45, weather=0, flags=0, days=0, label=None, conf=0.0, area=0.0, notes=""),
    dict(name="alligator_wilshire", peak=0.4, hole=8, tdelta=1.1, crit=55, traf=60, weather=10, flags=1, days=20, label=DistressClass.CRACK, conf=0.62, area=0.03, notes="alligator fatigue cracks in the wheel path, July heat, Wilshire"),
    dict(name="pothole", peak=2.4, hole=42, tdelta=3.4, crit=80, traf=90, weather=5, flags=3, days=45, label=DistressClass.POTHOLE, conf=0.91, area=0.06, notes="utility trench pothole after first rain"),
    dict(name="rut_110", peak=0.9, hole=18, tdelta=1.6, crit=70, traf=75, weather=20, flags=2, days=30, label=DistressClass.RUTTING, conf=0.55, area=0.02, notes="wheel-path rut on the 110"),
    dict(name="hospital_access", peak=1.6, hole=31, tdelta=2.2, crit=95, traf=88, weather=15, flags=4, days=60, label=DistressClass.POTHOLE, conf=0.84, area=0.05, notes=""),
    dict(name="after_storm", peak=0.7, hole=12, tdelta=4.1, crit=50, traf=40, weather=80, flags=2, days=10, label=DistressClass.PONDING, conf=0.70, area=0.04, notes="ponding at a blocked catch basin"),
    dict(name="quiet_street", peak=0.3, hole=28, tdelta=0.9, crit=25, traf=15, weather=0, flags=0, days=0, label=DistressClass.POTHOLE, conf=0.78, area=0.04, notes=""),
    dict(name="cleared", peak=0.15, hole=3, tdelta=0.5, crit=60, traf=70, weather=0, flags=0, days=0, label=None, conf=0.0, area=0.0, notes=""),
    dict(name="bridge_span", peak=0.0, hole=4, tdelta=0.5, crit=92, traf=70, weather=5, flags=1, days=14, label=None, conf=0.0, area=0.0, kind="modal", notes=""),
]


def demo_observations() -> list[dict]:
    segs = []
    for i, s in enumerate(SEGMENTS):
        lat = START[0] + i * 0.0018
        lon = START[1] - i * 0.0011
        accel = _imu_modal(seed=i) if s.get("kind") == "modal" else _imu_window(s["peak"], seed=i)
        segs.append(
            dict(
                segment_id=f"SEG-{i:03d}-{s['name']}",
                location=GeoPoint(lat=lat, lon=lon, timestamp_s=float(i * 8)),
                accel_xyz=accel,
                thermal_frame=_thermal(s["tdelta"], seed=i),
                lidar_xyz=_lidar_flat(hole_mm=s["hole"], seed=i),
                criticality=float(s["crit"]),
                traffic=float(s["traf"]),
                weather_risk=float(s["weather"]),
                prior_flags=int(s["flags"]),
                days_since_first_flag=int(s["days"]),
                vision=_vision(s["label"], s["conf"], s["area"]),
                notes=s.get("notes", ""),
            )
        )
    return segs


def run_demo(out_path: Path | None = None) -> dict:
    pipe = InfraPulsePipeline()
    result = pipe.run(demo_observations(), n_crews=3)
    disaster = pipe.disaster_queue(result.events, epicenter=(34.055, -118.246), radius_km=8.0)
    payload = {
        "events": [e.model_dump(mode="json") for e in result.events],
        "orders": [o.model_dump(mode="json") for o in result.orders],
        "route": [o.model_dump(mode="json") for o in result.route],
        "coverage": result.coverage,
        "disaster_queue": [e.model_dump(mode="json") for e in disaster],
        "summary": {
            "segments": len(result.events),
            "work_orders": len(result.orders),
            "high_or_worse": sum(1 for e in result.events if e.priority.value in ("high", "emergency")),
            "mean_integrity": round(sum(e.integrity_index for e in result.events) / max(len(result.events), 1), 1),
            "ndt_or_modal": sum(1 for e in result.events if e.inspection_type.value in ("ndt", "dynamic_retest")),
        },
    }
    dest = out_path or Path("data/demo_run.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    data = run_demo()
    print(json.dumps(data["summary"], indent=2))
    for e in data["events"]:
        print(f"{e['segment_id']:28} {e['priority']:10} pri={e['priority_score']:.0f}  I={e['integrity_index']:.0f}  {e['claim']}")
