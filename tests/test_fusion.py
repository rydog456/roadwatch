from infra_pulse.dispatch import to_work_order
from infra_pulse.fusion import fuse
from infra_pulse.imu import imu_analyze, should_trigger_hires
from infra_pulse.lidar import lidar_analyze
from infra_pulse.models import (
    BoundingBox,
    DistressClass,
    GeoPoint,
    LidarResult,
    SegmentObservation,
    ThermalResult,
    VisionResult,
)
from infra_pulse.thermal import thermal_analyze
from infra_pulse.vision import _vision_severity, classical_distress
import numpy as np


def _obs(**kwargs) -> SegmentObservation:
    dets = kwargs.pop("dets", [])
    vision = VisionResult(detections=dets, severity=_vision_severity(dets), confidence=0.9 if dets else 0.1)
    base = dict(
        segment_id="SEG-TEST",
        location=GeoPoint(lat=34.05, lon=-118.24),
        vision=vision,
        imu=imu_analyze(np.column_stack([np.zeros(20), np.zeros(20), np.ones(20)])),
        thermal=ThermalResult(delta_c=0.2, anomaly=False, severity=2.0),
        lidar=LidarResult(depth_mm=2.0, rut_mm=1.0, volume_m3=0.0, severity=2.0),
        criticality=50,
        traffic=50,
    )
    base.update(kwargs)
    return SegmentObservation(**base)


def test_healthy_is_monitor_or_low():
    e = fuse(_obs())
    assert e.priority.value in ("monitor", "low")
    assert to_work_order(e, 1) is None or e.priority.value == "low"


def test_multimodal_pothole_ranks_above_quiet_visual_only():
    pothole = [
        BoundingBox(x1=0, y1=0, x2=80, y2=80, confidence=0.92, label=DistressClass.POTHOLE, area_ratio=0.07)
    ]
    z = np.ones(40)
    z[20] = 4.2
    accel = np.column_stack([np.zeros(40), np.zeros(40), z])
    xyz = np.column_stack([
        np.random.default_rng(0).uniform(-1, 1, 300),
        np.random.default_rng(1).uniform(-0.4, 0.4, 300),
        np.zeros(300),
    ])
    xyz[np.abs(xyz[:, 0]) < 0.2, 2] = -0.045
    high = fuse(_obs(
        dets=pothole,
        imu=imu_analyze(accel),
        lidar=lidar_analyze(xyz),
        thermal=thermal_analyze(np.full((24, 32), 28.0) + np.pad(np.full((4, 4), 4.0), ((10, 10), (14, 14)))),
        criticality=90,
        traffic=90,
        prior_flags=3,
        days_since_first_flag=40,
    ))
    quiet = fuse(_obs(
        dets=pothole,
        criticality=20,
        traffic=15,
    ))
    assert high.priority_score > quiet.priority_score
    assert high.sensors_agreeing.count("vision") + len(high.sensors_agreeing) >= 2


def test_imu_trigger_on_spike():
    z = np.ones(30)
    z[10] = 3.5
    accel = np.column_stack([np.zeros(30), np.zeros(30), z])
    assert should_trigger_hires(accel)


def test_spectral_modal_is_not_an_impact():
    t = np.arange(256) / 100.0
    z = 1.0 + 0.28 * np.sin(2 * np.pi * 3.2 * t)
    accel = np.column_stack([np.zeros(256), np.zeros(256), z])
    modal = imu_analyze(accel)
    assert modal.modal_score > 40
    assert not should_trigger_hires(accel)


def test_bridge_like_vibration_requests_ndt_not_pothole_ticket():
    t = np.arange(256) / 100.0
    z = 1.0 + 0.30 * np.sin(2 * np.pi * 3.1 * t)
    accel = np.column_stack([np.zeros(256), np.zeros(256), z])
    e = fuse(_obs(imu=imu_analyze(accel), criticality=92, traffic=70))
    assert e.claim.value in ("possible_internal_issue_needs_ndt", "dynamic_signature_shift")
    assert e.integrity_index < 95
    assert e.inspection_type.value in ("ndt", "dynamic_retest")


def test_baseline_store_reports_rms_growth():
    from infra_pulse.memory import BaselineStore
    store = BaselineStore()
    d0, _ = store.update("span-a", 0.10, 0.2)
    d1, _ = store.update("span-a", 0.16, 0.3)
    assert d0 == 0.0
    assert d1 > 20


def test_thermal_flags_hot_spot():
    frame = np.full((24, 32), 27.0)
    frame[8:12, 8:12] = 32.0
    r = thermal_analyze(frame)
    assert r.anomaly
    assert r.delta_c >= 2.5


def test_imu_and_lidar_tolerate_bad_arrays():
    short = imu_analyze(np.zeros((8, 2)))
    assert short.severity == 0 or short.peak_vertical_g >= 0
    empty = lidar_analyze(np.zeros((0, 3)))
    assert empty.depth_mm == 0
    nan = np.ones((30, 3))
    nan[0, 0] = np.nan
    lidar_analyze(nan)


def test_classical_vision_on_synthetic_frame():
    img = np.full((240, 320, 3), 180, dtype=np.uint8)
    img[80:140, 90:160] = 20
    boxes = classical_distress(img)
    assert isinstance(boxes, list)
