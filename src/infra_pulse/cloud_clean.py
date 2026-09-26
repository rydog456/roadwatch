"""Point-cloud cleanup before pothole measurement.

Open3D is the processor when it is installed: statistical outlier removal,
then a RANSAC ground plane. Without it, a voxel-density filter and a small
numpy RANSAC do the same job so a phone upload still prices.
"""

from __future__ import annotations

import numpy as np

# Open3D defaults that match a phone LiDAR walk of a few metres.
SOR_NEIGHBORS = 20
SOR_STD_RATIO = 2.0
PLANE_DISTANCE_M = 0.015
RANSAC_ITERATIONS = 400


def _open3d():
    try:
        import open3d as o3d

        return o3d
    except ImportError:
        return None


def remove_statistical_outliers(xyz: np.ndarray) -> np.ndarray:
    """Drop points whose neighbor distance is an outlier. Isolated spikes go first."""
    pts = np.asarray(xyz, dtype=float)
    if pts.ndim != 2 or pts.shape[-1] < 3 or len(pts) < SOR_NEIGHBORS + 1:
        return pts
    pts = pts[:, :3]
    o3d = _open3d()
    if o3d is not None:
        cloud = o3d.geometry.PointCloud()
        cloud.points = o3d.utility.Vector3dVector(np.ascontiguousarray(pts, dtype=np.float64))
        _, index = cloud.remove_statistical_outlier(nb_neighbors=SOR_NEIGHBORS, std_ratio=SOR_STD_RATIO)
        kept = pts[np.asarray(index, dtype=int)]
        if len(kept) >= 20:
            return kept
    return _density_filter(pts)


def _density_filter(pts: np.ndarray, voxel_m: float = 0.05, min_count: int = 4) -> np.ndarray:
    """Keep points that share a neighbourhood. Stand-in for Open3D's statistic."""
    keys = np.floor(pts / voxel_m).astype(np.int64)
    buckets: dict[tuple[int, int, int], int] = {}
    for key in keys:
        cell = (int(key[0]), int(key[1]), int(key[2]))
        buckets[cell] = buckets.get(cell, 0) + 1
    keep = np.zeros(len(pts), dtype=bool)
    for i, key in enumerate(keys):
        total = 0
        x, y, z = int(key[0]), int(key[1]), int(key[2])
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    total += buckets.get((x + dx, y + dy, z + dz), 0)
                    if total >= min_count:
                        break
                if total >= min_count:
                    break
            if total >= min_count:
                break
        keep[i] = total >= min_count
    kept = pts[keep]
    return kept if len(kept) >= 20 else pts


def ground_plane(xyz: np.ndarray) -> tuple[np.ndarray, float]:
    """Unit normal and d for n·x + d = 0 on the pavement, not on the hole."""
    pts = np.asarray(xyz, dtype=float)
    if pts.ndim != 2 or len(pts) < 3:
        return np.array([0.0, 0.0, 1.0]), 0.0
    pts = pts[:, :3]
    o3d = _open3d()
    if o3d is not None and len(pts) >= 20:
        cloud = o3d.geometry.PointCloud()
        cloud.points = o3d.utility.Vector3dVector(np.ascontiguousarray(pts, dtype=np.float64))
        model, inliers = cloud.segment_plane(
            distance_threshold=PLANE_DISTANCE_M,
            ransac_n=3,
            num_iterations=RANSAC_ITERATIONS,
        )
        if len(inliers) >= 20:
            normal = np.asarray(model[:3], dtype=float)
            scale = float(np.linalg.norm(normal))
            if scale > 1e-8:
                return normal / scale, float(model[3]) / scale
    return _ransac_plane(pts)


def _ransac_plane(pts: np.ndarray) -> tuple[np.ndarray, float]:
    rng = np.random.default_rng(0)
    best_n = 0
    best_normal = np.array([0.0, 0.0, 1.0])
    best_d = 0.0
    best_mask = None
    trials = min(RANSAC_ITERATIONS, 120)
    for _ in range(trials):
        sample = pts[rng.choice(len(pts), 3, replace=False)]
        normal = np.cross(sample[1] - sample[0], sample[2] - sample[0])
        scale = float(np.linalg.norm(normal))
        if scale < 1e-8:
            continue
        normal = normal / scale
        d = -float(np.dot(normal, sample[0]))
        mask = np.abs(pts @ normal + d) < PLANE_DISTANCE_M
        count = int(mask.sum())
        if count > best_n:
            best_n = count
            best_normal = normal
            best_d = d
            best_mask = mask
    if best_mask is None or best_n < 3:
        return best_normal, best_d
    inliers = pts[best_mask]
    centroid = inliers.mean(axis=0)
    _, _, vh = np.linalg.svd(inliers - centroid, full_matrices=False)
    normal = vh[-1]
    if np.dot(normal, best_normal) < 0:
        normal = -normal
    return normal, -float(np.dot(normal, centroid))
