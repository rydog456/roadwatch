"""iPhone Pro / Pro Max capture: LiDAR + Core Motion + GNSS.

No Raspberry Pi. ARKit-aligned PLY + motion sidecar is the native packet.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from pydantic import BaseModel, Field

from infra_pulse.imu import imu_analyze
from infra_pulse.models import GeoPoint, ImuResult


class IPhoneMotion(BaseModel):
    """Core Motion window. accel in g, gyro in rad/s, attitude in radians."""

    accel_xyz: list[list[float]] = Field(default_factory=list)
    gyro_xyz: list[list[float]] = Field(default_factory=list)
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0
    heading_deg: Optional[float] = None
    baro_hpa: Optional[float] = None
    mag_heading_deg: Optional[float] = None
    arkit_tracking: str = "normal"  # normal | limited | unavailable


def _rot_x(a: float) -> np.ndarray:
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def _rot_y(a: float) -> np.ndarray:
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def _rot_z(a: float) -> np.ndarray:
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def cloud_to_scene(
    xyz: np.ndarray,
    heading_deg: float,
    ref_heading_deg: float,
    pitch: float = 0.0,
    roll: float = 0.0,
    z_offset_m: float = 0.0,
) -> np.ndarray:
    """Put a phone-frame PLY into the scene frame using Core Motion + compass.

    Pitch/roll level the pavement plane; heading difference aligns walks that
    went opposite directions over the same GPS cell. Barometer supplies a
    clipped Z offset (overpasses), not millimetre depth.
    """
    pts = np.asarray(xyz, dtype=float)
    if pts.ndim != 2 or pts.shape[-1] < 3 or len(pts) == 0:
        return np.zeros((0, 3))
    pts = pts[:, :3].copy()
    pts = pts @ _rot_x(-pitch).T @ _rot_y(-roll).T
    dpsi = np.deg2rad(float(heading_deg) - float(ref_heading_deg))
    pts = pts @ _rot_z(-dpsi).T
    pts[:, 2] += float(z_offset_m)
    return pts


def baro_z_offset_m(ref_hpa: float | None, hpa: float | None) -> float:
    if ref_hpa is None or hpa is None:
        return 0.0
    return float(np.clip((ref_hpa - hpa) * 8.3, -1.5, 1.5))


def scan_trust(pose: float, contributors: int, point_count: int) -> float:
    """0-100 trust in this phone pass. A second walker and a dense cloud help."""
    score = float(pose)
    if contributors >= 2:
        score += 10
    if point_count < 80:
        score -= 25
    elif point_count < 200:
        score -= 10
    return float(np.clip(score, 0, 100))


def pose_quality(motion: IPhoneMotion, sample_hz: float = 100.0) -> float:
    """How much to trust this LiDAR pass. Low if the phone was whipping around."""
    score = 70.0
    if motion.arkit_tracking == "limited":
        score -= 25
    if motion.arkit_tracking == "unavailable":
        score -= 50
    gyro = np.asarray(motion.gyro_xyz, dtype=float) if motion.gyro_xyz else np.zeros((0, 3))
    if len(gyro) >= 8:
        rate = float(np.sqrt(np.mean(np.sum(gyro**2, axis=1))))
        # ~0.3 rad/s rms is a careful scan; >1.5 is a swing
        score -= min(40.0, max(0.0, (rate - 0.35) * 28.0))
    tilt = abs(motion.pitch) + abs(motion.roll)
    if tilt > 0.7:
        score -= 10
    if motion.heading_deg is not None and motion.mag_heading_deg is not None:
        dh = abs((motion.heading_deg - motion.mag_heading_deg + 180) % 360 - 180)
        if dh > 25:
            score -= 8
    return float(np.clip(score, 0, 100))


def motion_to_imu(motion: IPhoneMotion) -> ImuResult:
    accel = np.asarray(motion.accel_xyz, dtype=float) if motion.accel_xyz else np.zeros((16, 3))
    if accel.ndim != 2 or accel.shape[-1] < 3:
        accel = np.zeros((16, 3))
    return imu_analyze(accel)


class IPhoneScan(BaseModel):
    """One contributor's pass over a scene (export from the phone app)."""

    contributor_id: str
    device: str = "iPhone17,1"
    location: GeoPoint
    motion: IPhoneMotion = Field(default_factory=IPhoneMotion)
    ply_path: Optional[str] = None
    image_path: Optional[str] = None
    notes: str = ""
