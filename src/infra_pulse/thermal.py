from __future__ import annotations

import numpy as np

from infra_pulse.config import THERMAL_DELTA_C
from infra_pulse.models import ThermalResult


def thermal_analyze(frame: np.ndarray, delta_c: float = THERMAL_DELTA_C) -> ThermalResult:
    """Flag local hot/cold spots vs surrounding pavement.

    frame: 2D array of temperatures in Celsius (e.g. 24x32 MLX90640).
    """
    arr = np.asarray(frame, dtype=float)
    if arr.size == 0:
        return ThermalResult(delta_c=0.0, anomaly=False, severity=0.0)
    med = float(np.median(arr))
    local = float(np.max(np.abs(arr - med)))
    anomaly = local >= delta_c
    severity = float(np.clip(local / 8.0 * 100.0, 0, 100))
    return ThermalResult(delta_c=local, anomaly=anomaly, severity=severity)
