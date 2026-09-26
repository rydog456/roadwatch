"""Collaborative iPhone LiDAR scenes.

On-disk layout per scene_id (geohash-ish folder):
  data/scenes/<scene_id>/
    scene.ipulse.json
    merged.ply
    contrib_<id>_<ts>.ply

Multiple people scanning the same GPS cluster append PLY files; we voxel-merge
into merged.ply so coverage and deterioration densify over time.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from infra_pulse.iphone import IPhoneMotion, baro_z_offset_m, cloud_to_scene, pose_quality
from infra_pulse.lidar import lidar_analyze, read_ply, voxel_merge, write_ply
from infra_pulse.models import GeoPoint, LidarResult

SCENES = Path("data/scenes")
FORMAT = "ipulse-scene/v1"


def _root(root: Path | None) -> Path:
    return root or SCENES


def scene_id_for(lat: float, lon: float) -> str:
    """~20 m cell so nearby scans of the same block share a folder."""
    return f"la_{round(lat * 5000)}_{round(lon * 5000)}"


def _meta_path(sid: str, root: Path | None = None) -> Path:
    return _root(root) / sid / "scene.ipulse.json"


def load_meta(sid: str, root: Path | None = None) -> dict[str, Any]:
    path = _meta_path(sid, root)
    if not path.exists():
        return {
            "format": FORMAT,
            "scene_id": sid,
            "contributors": [],
            "scans": [],
            "merged_ply": "merged.ply",
        }
    return json.loads(path.read_text(encoding="utf-8"))


def save_meta(sid: str, meta: dict[str, Any], root: Path | None = None) -> None:
    path = _meta_path(sid, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def ingest_scan(
    location: GeoPoint,
    xyz: np.ndarray,
    contributor_id: str,
    extra: dict[str, Any] | None = None,
    root: Path | None = None,
    motion: IPhoneMotion | None = None,
) -> LidarResult:
    sid = scene_id_for(location.lat, location.lon)
    folder = _root(root) / sid
    folder.mkdir(parents=True, exist_ok=True)
    meta = load_meta(sid, root)
    heading = float(location.heading_deg)
    if meta.get("ref_heading_deg") is None:
        meta["ref_heading_deg"] = heading
    motion = motion or IPhoneMotion()
    if meta.get("ref_baro_hpa") is None and motion.baro_hpa is not None:
        meta["ref_baro_hpa"] = motion.baro_hpa
    aligned = cloud_to_scene(
        xyz,
        heading_deg=heading,
        ref_heading_deg=float(meta["ref_heading_deg"]),
        pitch=motion.pitch,
        roll=motion.roll,
        z_offset_m=baro_z_offset_m(meta.get("ref_baro_hpa"), motion.baro_hpa),
    )
    stamp = int(time.time() * 1000)
    ply_name = f"contrib_{contributor_id}_{stamp}.ply"
    write_ply(folder / ply_name, aligned)

    merged_path = folder / "merged.ply"
    existing = read_ply(merged_path) if merged_path.exists() else np.zeros((0, 3))
    merged = voxel_merge(existing, aligned)
    write_ply(merged_path, merged)

    pq = pose_quality(motion)
    meta["scans"].append(
        {
            "contributor_id": contributor_id,
            "ply": ply_name,
            "lat": location.lat,
            "lon": location.lon,
            "heading_deg": heading,
            "pose_quality": pq,
            "arkit_tracking": motion.arkit_tracking,
            "t": stamp,
            **(extra or {}),
        }
    )
    if contributor_id not in meta["contributors"]:
        meta["contributors"].append(contributor_id)
    save_meta(sid, meta, root)

    result = lidar_analyze(merged)
    result.point_count = int(len(merged))
    result.contributors = len(meta["contributors"])
    result.scene_id = sid
    return result


def analyze_scene(sid: str, root: Path | None = None) -> LidarResult:
    merged_path = _root(root) / sid / "merged.ply"
    pts = read_ply(merged_path) if merged_path.exists() else np.zeros((0, 3))
    result = lidar_analyze(pts)
    meta = load_meta(sid, root)
    result.point_count = int(len(pts))
    result.contributors = len(meta.get("contributors") or [])
    result.scene_id = sid
    return result
