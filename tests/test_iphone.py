from pathlib import Path

import numpy as np

from infra_pulse.iphone import IPhoneMotion, cloud_to_scene, pose_quality
from infra_pulse.la_priors import la_boost
from infra_pulse.lidar import read_ply, voxel_merge, write_ply
from infra_pulse.llm_detect import apply_llm
from infra_pulse.models import BoundingBox, DistressClass, GeoPoint, VisionResult
from infra_pulse.scene_store import ingest_scan
from infra_pulse.vision import _vision_severity


def test_la_alligator_outranks_generic_crack():
    generic = la_boost([DistressClass.CRACK])
    la = la_boost([DistressClass.ALLIGATOR_CRACK])
    assert la > generic


def test_llm_offline_maps_alligator_from_notes():
    vis = VisionResult(
        detections=[
            BoundingBox(x1=0, y1=0, x2=10, y2=10, confidence=0.6, label=DistressClass.CRACK, area_ratio=0.04)
        ],
        severity=20,
        confidence=0.6,
        source="demo",
    )
    vis.severity = _vision_severity(vis.detections)
    out = apply_llm(vis, notes="alligator fatigue cracks in the wheel path, July heat")
    assert out.detections[0].label == DistressClass.ALLIGATOR_CRACK


def test_two_iphones_merge_same_scene(tmp_path: Path):
    loc = GeoPoint(lat=34.0522, lon=-118.2437)
    a = np.column_stack([np.linspace(0, 1, 80), np.zeros(80), np.zeros(80)])
    b = a.copy()
    b[:10, 2] = -0.04
    r1 = ingest_scan(loc, a, "alice", root=tmp_path)
    r2 = ingest_scan(loc, b, "bob", root=tmp_path)
    assert r1.scene_id == r2.scene_id
    assert r2.contributors == 2
    merged = read_ply(tmp_path / r2.scene_id / "merged.ply")
    assert len(merged) > 20
    assert r2.depth_mm >= r1.depth_mm


def test_pose_quality_drops_when_gyro_is_wild():
    calm = IPhoneMotion(gyro_xyz=[[0.05, 0.02, 0.01]] * 20, arkit_tracking="normal")
    wild = IPhoneMotion(gyro_xyz=[[2.0, 1.5, 1.2]] * 20, arkit_tracking="limited")
    assert pose_quality(calm) > pose_quality(wild)


def test_ply_roundtrip(tmp_path: Path):
    pts = np.array([[0.0, 0.0, 0.0], [0.1, 0.0, -0.02]])
    path = tmp_path / "t.ply"
    write_ply(path, pts)
    back = read_ply(path)
    assert len(back) == 2
    merged = voxel_merge(pts, pts)
    assert len(merged) <= 2


def test_heading_aligns_opposite_walks():
    pts = np.array([[1.0, 0.0, 0.0]])
    flipped = cloud_to_scene(pts, heading_deg=180, ref_heading_deg=0)
    assert flipped[0, 0] < 0
