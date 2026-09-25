from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BaselineStore:
    """Per-segment running baseline. Repeat drives are the real product.

    First pass writes the baseline. Later passes report percent change in
    vertical RMS and low-band energy — the cheapest proxy for 'this span
    is not behaving like last month.'
    """

    rms: dict[str, float] = field(default_factory=dict)
    low_band: dict[str, float] = field(default_factory=dict)
    alpha: float = 0.25

    def update(self, segment_id: str, rms: float, low_band: float) -> tuple[float, float]:
        prev_rms = self.rms.get(segment_id)
        prev_low = self.low_band.get(segment_id)
        if prev_rms is None:
            self.rms[segment_id] = rms
            self.low_band[segment_id] = low_band
            return 0.0, 0.0
        d_rms = 100.0 * (rms - prev_rms) / max(prev_rms, 1e-4)
        d_low = 100.0 * (low_band - prev_low) / max(prev_low, 1e-4) if prev_low is not None else 0.0
        self.rms[segment_id] = (1 - self.alpha) * prev_rms + self.alpha * rms
        self.low_band[segment_id] = (1 - self.alpha) * (prev_low or low_band) + self.alpha * low_band
        return d_rms, d_low
