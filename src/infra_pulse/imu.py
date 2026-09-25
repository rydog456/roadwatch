from __future__ import annotations

import math

import numpy as np

from infra_pulse.config import (
    IMU_BAND_HIGH,
    IMU_BAND_LOW,
    IMU_BAND_MID,
    IMU_IMPACT_G,
    IMU_SAMPLE_HZ,
    IMU_ZSCORE_TRIGGER,
)
from infra_pulse.models import ImuResult


def vertical_g(accel_xyz: np.ndarray) -> np.ndarray:
    """Return signed vertical acceleration in g. Assumes last axis is Z (MPU6050)."""
    arr = np.asarray(accel_xyz, dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    if arr.size == 0 or arr.shape[-1] < 3:
        return np.zeros(max(arr.shape[0] if arr.ndim == 2 else 1, 1))
    return arr[:, 2]


def _band_frac(power: np.ndarray, freqs: np.ndarray, band: tuple[float, float]) -> float:
    total = float(np.sum(power))
    if total <= 1e-18:
        return 0.0
    lo, hi = band
    mask = (freqs >= lo) & (freqs < hi)
    return float(np.sum(power[mask]) / total)


def spectral_features(z_dyn: np.ndarray, sample_hz: float) -> dict[str, float]:
    """Split vibration into structure-ish / roughness / impact bands.

    A pothole is usually a short broadband spike. A span whose motion changed
    often shows more energy in a narrow low-frequency peak. Neither is a modal
    test — vehicle-mounted IMUs are contaminated by suspension — but the split
    is the right next sensor feature without new hardware.
    """
    n = len(z_dyn)
    empty = dict(low=0.0, mid=0.0, high=0.0, peakiness=0.0, dominant_hz=0.0, modal=0.0)
    if n < 32 or sample_hz <= 0:
        return empty
    windowed = z_dyn * np.hanning(n)
    spec = np.abs(np.fft.rfft(windowed)) ** 2
    freqs = np.fft.rfftfreq(n, d=1.0 / sample_hz)
    # ignore DC
    if len(spec) > 1:
        spec[0] = 0.0
    low = _band_frac(spec, freqs, IMU_BAND_LOW)
    mid = _band_frac(spec, freqs, IMU_BAND_MID)
    high = _band_frac(spec, freqs, IMU_BAND_HIGH)
    usable = spec[freqs >= 0.5]
    peakiness = 0.0
    dominant = 0.0
    if usable.size:
        med = float(np.median(usable) + 1e-12)
        peakiness = float(np.max(usable) / med)
        dominant = float(freqs[freqs >= 0.5][int(np.argmax(usable))])
    # Tonal low-frequency energy without a huge time-domain hit → modal-ish
    modal = float(np.clip((low * 70.0) + min(peakiness / 12.0, 1.0) * 30.0, 0, 100))
    if high > 0.45 and low < 0.25:
        modal *= 0.35  # looks like an impact, not a tone
    return dict(low=low, mid=mid, high=high, peakiness=peakiness, dominant_hz=dominant, modal=modal)


def imu_analyze(
    accel_xyz: np.ndarray,
    baseline_rms: float = 0.12,
    sample_hz: float = IMU_SAMPLE_HZ,
) -> ImuResult:
    """Turn a short IMU window into roughness / impact / spectral features.

    accel_xyz: Nx3 array in g. Gravity should be removed or ~1g on Z.
    """
    z = vertical_g(accel_xyz)
    z_dyn = z - np.median(z)
    rms = float(np.sqrt(np.mean(z_dyn**2))) if len(z_dyn) else 0.0
    peak = float(np.max(np.abs(z_dyn))) if len(z_dyn) else 0.0
    z_score = (rms - baseline_rms) / max(baseline_rms * 0.5, 1e-3)
    iri_proxy = min(20.0, rms * 40.0)
    impact = peak >= IMU_IMPACT_G or z_score >= IMU_ZSCORE_TRIGGER
    spec = spectral_features(z_dyn, sample_hz)
    severity = float(
        np.clip(
            peak / 4.0 * 70.0 + max(z_score, 0) * 6.0 + spec["mid"] * 25.0 + spec["modal"] * 0.15,
            0,
            100,
        )
    )
    return ImuResult(
        rms_vertical_g=rms,
        peak_vertical_g=peak,
        z_score=float(z_score),
        roughness_iri_proxy=iri_proxy,
        impact_event=bool(impact),
        severity=severity,
        low_band_frac=spec["low"],
        mid_band_frac=spec["mid"],
        high_band_frac=spec["high"],
        spectral_peakiness=spec["peakiness"],
        modal_score=float(spec["modal"]),
        dominant_hz=spec["dominant_hz"],
    )


def should_trigger_hires(accel_xyz: np.ndarray, baseline_rms: float = 0.12) -> bool:
    return imu_analyze(accel_xyz, baseline_rms).impact_event


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
