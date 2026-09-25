from __future__ import annotations

import numpy as np

from infra_pulse.config import UNCERTAIN_VISION
from infra_pulse.models import IntegrityClaim, SegmentObservation, VisionResult


def vision_needs_second_pass(vision: VisionResult) -> bool:
    """YOLO is unsure — that is when a vision LLM is allowed to look, not before."""
    lo, hi = UNCERTAIN_VISION
    if not vision.detections:
        return False
    return lo <= vision.confidence <= hi


def layer_scores(obs: SegmentObservation, deterioration: float) -> dict[str, float]:
    """Four independent integrity layers. High = more distressed."""
    surface = float(obs.vision.severity)
    geometry = float(obs.lidar.severity)
    dynamics = float(
        np.clip(
            0.55 * obs.imu.severity + 0.45 * obs.imu.modal_score,
            0,
            100,
        )
    )
    history = float(deterioration)
    return {
        "surface": surface,
        "geometry": geometry,
        "dynamics": dynamics,
        "history": history,
    }


def integrity_index(layers: dict[str, float]) -> float:
    """100 = no screened distress. Not remaining structural life."""
    distress = (
        0.34 * layers["surface"]
        + 0.31 * layers["geometry"]
        + 0.25 * layers["dynamics"]
        + 0.10 * layers["history"]
    )
    return float(np.clip(100.0 - distress, 0, 100))


def classify_claim(obs: SegmentObservation, layers: dict[str, float], agreeing: list[str]) -> IntegrityClaim:
    surface, geometry, dynamics = layers["surface"], layers["geometry"], layers["dynamics"]
    if obs.imu.modal_score >= 48 and surface < 18 and geometry < 22:
        return IntegrityClaim.POSSIBLE_INTERNAL
    if dynamics >= 45 and surface < 18 and geometry < 20:
        return IntegrityClaim.POSSIBLE_INTERNAL
    if len(agreeing) >= 3 and (surface >= 25 or geometry >= 25):
        return IntegrityClaim.MULTIMODAL_DISTRESS
    if obs.imu.modal_score >= 40 and not obs.imu.impact_event:
        return IntegrityClaim.DYNAMIC_SHIFT
    if geometry >= 25:
        return IntegrityClaim.GEOMETRY_CHANGE
    if surface >= 15:
        return IntegrityClaim.SURFACE_ONLY
    return IntegrityClaim.HEALTHY_SCREEN
