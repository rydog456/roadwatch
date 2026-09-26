from __future__ import annotations

from pathlib import Path

import numpy as np

from infra_pulse.config import LIDAR_POTHOLE_MM, LIDAR_RUT_MM
from infra_pulse.models import LidarResult


def to_meters(xyz: np.ndarray) -> np.ndarray:
    """Phone apps export metres, centimetres, or millimetres. LiDAR range is a few metres."""
    pts = np.asarray(xyz, dtype=float)
    if pts.ndim != 2 or len(pts) < 5:
        return pts
    span = float(np.ptp(pts[:, :3], axis=0).max())
    if span >= 1000:
        return pts / 1000.0
    if span >= 30:
        return pts / 100.0
    return pts


def cap_points(xyz: np.ndarray, limit: int = 50000) -> np.ndarray:
    pts = np.asarray(xyz, dtype=float)
    if pts.ndim != 2 or len(pts) <= limit:
        return pts
    pick = np.random.default_rng(0).choice(len(pts), limit, replace=False)
    return pts[pick]


def read_ply(path: Path) -> np.ndarray:
    """Vertex xyz from an ASCII or binary PLY (3D Scanner, Polycam, ARKit)."""
    if not path.exists():
        return np.zeros((0, 3))
    return read_ply_bytes(path.read_bytes())


_PLY_SIZE = {
    "char": 1, "uchar": 1, "int8": 1, "uint8": 1,
    "short": 2, "ushort": 2, "int16": 2, "uint16": 2,
    "int": 4, "uint": 4, "int32": 4, "uint32": 4,
    "float": 4, "float32": 4,
    "double": 8, "float64": 8,
}
_PLY_FLOAT = {"float": "f4", "float32": "f4", "double": "f8", "float64": "f8"}


def read_ply_bytes(raw: bytes) -> np.ndarray:
    marker = raw.find(b"end_header")
    if marker < 0:
        return np.zeros((0, 3))
    header = raw[:marker].decode("ascii", errors="ignore")
    rest = raw[marker + len(b"end_header"):]
    if rest.startswith(b"\r\n"):
        rest = rest[2:]
    elif rest.startswith(b"\n"):
        rest = rest[1:]
    n = 0
    props: list[tuple[str, str]] = []
    in_vertex = False
    for line in header.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] == "element":
            in_vertex = parts[1] == "vertex"
            if in_vertex:
                n = int(parts[2])
            continue
        if in_vertex and len(parts) >= 3 and parts[0] == "property" and parts[1] != "list":
            props.append((parts[1], parts[-1]))
    if n <= 0 or not props:
        return np.zeros((0, 3))
    binary_le = "binary_little_endian" in header
    binary_be = "binary_big_endian" in header
    if not binary_le and not binary_be:
        pts = []
        for line in rest.decode("utf-8", errors="ignore").splitlines()[:n]:
            bits = line.split()
            if len(bits) >= 3:
                pts.append([float(bits[0]), float(bits[1]), float(bits[2])])
        return np.asarray(pts, dtype=float) if pts else np.zeros((0, 3))
    names = {name for _, name in props}
    if not {"x", "y", "z"} <= names:
        return np.zeros((0, 3))
    stride = 0
    offsets: dict[str, tuple[int, str]] = {}
    for typ, name in props:
        offsets[name] = (stride, typ)
        stride += _PLY_SIZE.get(typ, 4)
    count = min(n, len(rest) // max(stride, 1))
    if count <= 0:
        return np.zeros((0, 3))
    buf = rest[: count * stride]
    endian = "<" if binary_le else ">"
    out = np.zeros((count, 3), dtype=float)
    for axis, col in zip("xyz", range(3)):
        off, typ = offsets[axis]
        code = _PLY_FLOAT.get(typ)
        if code is None:
            return np.zeros((0, 3))
        view = np.ndarray(shape=(count,), dtype=endian + code, buffer=buf, offset=off, strides=(stride,))
        out[:, col] = view
    return out.copy()


def write_ply(path: Path, xyz: np.ndarray) -> None:
    pts = np.asarray(xyz, dtype=float)
    if pts.ndim != 2 or pts.shape[-1] < 3:
        pts = np.zeros((0, 3))
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(f"{p[0]:.5f} {p[1]:.5f} {p[2]:.5f}" for p in pts)
    path.write_text(
        f"ply\nformat ascii 1.0\nelement vertex {len(pts)}\n"
        f"property float x\nproperty float y\nproperty float z\nend_header\n{body}\n",
        encoding="utf-8",
    )


def voxel_merge(a: np.ndarray, b: np.ndarray, voxel_m: float = 0.02) -> np.ndarray:
    """Keep the lowest Z in each 2 cm cell so holes survive as people add scans."""
    stacked = []
    for arr in (a, b):
        pts = np.asarray(arr, dtype=float)
        if pts.ndim == 2 and pts.shape[-1] >= 3 and len(pts):
            stacked.append(pts[:, :3])
    if not stacked:
        return np.zeros((0, 3))
    pts = np.vstack(stacked)
    pts = pts[np.isfinite(pts).all(axis=1)]
    if len(pts) == 0:
        return pts
    keys = np.round(pts[:, :2] / voxel_m).astype(np.int64)
    buckets: dict[tuple[int, int], np.ndarray] = {}
    for p, k in zip(pts, keys):
        xy = (int(k[0]), int(k[1]))
        prev = buckets.get(xy)
        if prev is None or p[2] < prev[2]:
            buckets[xy] = p
    return np.vstack(list(buckets.values())) if buckets else np.zeros((0, 3))


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
    pts = to_meters(pts)
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
    signed = pts @ normal + d
    low, high = np.percentile(signed, [8, 92])
    if abs(low) >= abs(high):
        below = -signed
        normal = -normal
    else:
        below = signed
    depth_m = float(np.percentile(below, 95)) if np.any(below > 0) else 0.0
    depth_m = max(0.0, depth_m)
    up = int(np.argmax(np.abs(normal)))
    horiz = [i for i in range(3) if i != up]
    lateral = horiz[int(np.argmin([float(np.ptp(pts[:, i])) for i in horiz]))]
    y = pts[:, lateral]
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
    hole = below > max(0.008, 0.4 * depth_m)
    length_m = width_m = 0.0
    if int(hole.sum()) >= 3:
        hp = pts[hole]
        length_m = max(float(np.ptp(hp[:, horiz[0]])), 0.05)
        width_m = max(float(np.ptp(hp[:, horiz[1]])), 0.05)
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
    return LidarResult(
        depth_mm=depth_mm,
        rut_mm=rut_mm,
        volume_m3=volume,
        severity=sev,
        point_count=int(len(pts)),
        length_m=round(length_m, 3),
        width_m=round(width_m, 3),
    )
