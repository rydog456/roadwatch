from __future__ import annotations

import numpy as np

from infra_pulse.config import LIDAR_POTHOLE_MM, LIDAR_RUT_MM
from infra_pulse.models import LidarResult


def _fit_plane(xyz: np.ndarray) -> tuple[np.ndarray, float]:
    """Least-squares plane n·x + d = 0 with n unit, z-up preferred."""
    pts = np.asarray(xyz, dtype=float)
    centroid = pts.mean(axis=0)
    _, _, vh = np.linalg.svd(pts - centroid, full_matrices=False)
    normal = vh[-1]
    if normal[2] < 0:
        normal = -normal
    d = -float(np.dot(normal, centroid))
    return normal, d


def lidar_analyze(xyz: np.ndarray) -> LidarResult:
    """Estimate pothole/rut depth as deviation below the fitted road plane.

    xyz: Nx3 metres, vehicle or world frame. Positive Z is up.
    """
    pts = np.asarray(xyz, dtype=float)
    empty = LidarResult(depth_mm=0.0, rut_mm=0.0, volume_m3=0.0, severity=0.0)
    if pts.ndim != 2 or pts.shape[-1] != 3:
        return empty
    pts = pts[np.isfinite(pts).all(axis=1)]
    if len(pts) < 20:
        return empty
    try:
        normal, d = _fit_plane(pts)
    except np.linalg.LinAlgError:
        return empty
    signed = pts @ normal + d  # metres above plane
    below = -signed
    depth_m = float(np.percentile(below, 95)) if np.any(below > 0) else 0.0
    depth_m = max(0.0, depth_m)
    # Cross-track bins for rut: use Y as lateral if available
    y = pts[:, 1]
    bins = np.linspace(y.min(), y.max(), 8)
    rut = 0.0
    if bins[-1] > bins[0]:
        idx = np.digitize(y, bins)
        means = []
        for i in range(1, len(bins)):
            mask = idx == i
            if mask.sum() > 3:
                means.append(float(np.mean(below[mask])))
        if means:
            rut = max(0.0, float(np.max(means)))
    depth_mm = depth_m * 1000.0
    rut_mm = rut * 1000.0
    # Approximate depressed volume using mean negative deviation * footprint
    neg = below[below > 0.005]
    volume = float(np.mean(neg) * (len(neg) / max(len(pts), 1)) * 2.0) if len(neg) else 0.0
    sev = 0.0
    if depth_mm >= LIDAR_POTHOLE_MM:
        sev = min(100.0, 40 + (depth_mm - LIDAR_POTHOLE_MM) * 1.2)
    elif rut_mm >= LIDAR_RUT_MM:
        sev = min(80.0, 25 + (rut_mm - LIDAR_RUT_MM) * 1.5)
    else:
        sev = min(40.0, depth_mm * 1.1)
    return LidarResult(depth_mm=depth_mm, rut_mm=rut_mm, volume_m3=volume, severity=sev)
