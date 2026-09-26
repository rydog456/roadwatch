"""City map of scanned defects. GPS + LiDAR dimensions + cost live here."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

STORE = Path("data/city_map.json")


def _path(path: Path | None) -> Path:
    return path or STORE


def load_defects(path: Path | None = None) -> list[dict[str, Any]]:
    dest = _path(path)
    if not dest.exists():
        return []
    data = json.loads(dest.read_text(encoding="utf-8"))
    return list(data.get("defects") or [])


def defect_record(
    lidar: Any,
    lat: float,
    lon: float,
    contributor_id: str,
    cost: dict[str, Any],
    notes: str = "",
    pose_quality: float = 50,
    heading_deg: float = 0,
) -> dict[str, Any]:
    return {
        "scene_id": lidar.scene_id,
        "lat": lat,
        "lon": lon,
        "heading_deg": heading_deg,
        "contributor_id": contributor_id,
        "contributors": lidar.contributors,
        "depth_mm": round(float(lidar.depth_mm), 1),
        "length_m": round(float(lidar.length_m), 3),
        "width_m": round(float(lidar.width_m), 3),
        "point_count": int(lidar.point_count),
        "pose_quality": round(float(pose_quality), 1),
        "cost": cost,
        "notes": notes,
    }


def upsert_defect(record: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    dest = _path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    defects = load_defects(dest)
    sid = record.get("scene_id")
    kept = [d for d in defects if d.get("scene_id") != sid]
    kept.append(record)
    dest.write_text(json.dumps({"defects": kept}, indent=2), encoding="utf-8")
    return record
