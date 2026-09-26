from __future__ import annotations

import numpy as np

from infra_pulse.config import IMU_FUSION_PEAK_G, FusionWeights, PRIORITY_THRESHOLDS
from infra_pulse.explainer import explain
from infra_pulse.integrity import classify_claim, integrity_index, layer_scores, vision_needs_second_pass
from infra_pulse.la_priors import la_boost
from infra_pulse.models import (
    DistressClass,
    FusedEvent,
    InspectionType,
    IntegrityClaim,
    PriorityLevel,
    SegmentObservation,
)


def _level(score: float) -> PriorityLevel:
    if score >= PRIORITY_THRESHOLDS["emergency"]:
        return PriorityLevel.EMERGENCY
    if score >= PRIORITY_THRESHOLDS["high"]:
        return PriorityLevel.HIGH
    if score >= PRIORITY_THRESHOLDS["medium"]:
        return PriorityLevel.MEDIUM
    if score >= PRIORITY_THRESHOLDS["low"]:
        return PriorityLevel.LOW
    return PriorityLevel.MONITOR


def _inspection(
    obs: SegmentObservation,
    labels: list[DistressClass],
    agreeing: int,
    claim: IntegrityClaim,
    second_pass: bool,
) -> InspectionType:
    if claim == IntegrityClaim.POSSIBLE_INTERNAL:
        return InspectionType.NDT
    if claim == IntegrityClaim.DYNAMIC_SHIFT:
        return InspectionType.MODAL
    if agreeing >= 3 and obs.lidar.depth_mm >= 30:
        return InspectionType.ENGINEER
    if obs.thermal.anomaly and obs.lidar.depth_mm < 15 and not labels:
        return InspectionType.NDT
    if obs.weather_risk >= 70 and obs.thermal.anomaly:
        return InspectionType.DRAINAGE
    if second_pass:
        return InspectionType.VISION_LLM
    if labels or obs.imu.impact_event:
        return InspectionType.VISUAL
    return InspectionType.NONE


def deterioration_index(obs: SegmentObservation) -> float:
    """0-100 growth signal from repeat visits. Not remaining structural life."""
    if obs.prior_flags <= 0:
        return 0.0
    recency = min(obs.days_since_first_flag / 90.0, 1.0)
    return float(np.clip(obs.prior_flags * 18.0 + recency * 25.0, 0, 100))


def fuse(obs: SegmentObservation, weights: FusionWeights | None = None) -> FusedEvent:
    weights = weights or FusionWeights()
    labels = [d.label for d in obs.vision.detections]
    det = deterioration_index(obs)
    la = obs.la_boost if obs.la_boost else la_boost(labels)
    layers = layer_scores(obs, det)
    layers["la_prior"] = la
    idx = integrity_index(layers)
    second_pass = vision_needs_second_pass(obs.vision)

    agreeing: list[str] = []
    if obs.vision.severity >= 12 or obs.vision.detections:
        agreeing.append("vision")
    if obs.lidar.depth_mm >= 10 or obs.lidar.rut_mm >= 8:
        agreeing.append("lidar")
    if obs.imu.impact_event or obs.imu.peak_vertical_g >= IMU_FUSION_PEAK_G or obs.imu.severity >= 18:
        agreeing.append("imu")
    if obs.imu.modal_score >= 38 and not obs.imu.impact_event:
        if "dynamics" not in agreeing:
            agreeing.append("dynamics")
    if obs.thermal.anomaly:
        agreeing.append("thermal")

    multimodal = (
        weights.vision * obs.vision.severity
        + weights.lidar * obs.lidar.severity
        + weights.imu * obs.imu.severity
        + weights.thermal * obs.thermal.severity
        + weights.deterioration * det
        + weights.la_prior * la
    )
    agreement_boost = 1.0 + 0.12 * max(0, len(agreeing) - 1)
    confidence = float(
        np.clip(
            0.35 * obs.vision.confidence
            + 0.20 * (1.0 if "lidar" in agreeing else 0.3)
            + 0.15 * (1.0 if "imu" in agreeing else 0.3)
            + 0.10 * (1.0 if "thermal" in agreeing else 0.4)
            + 0.20 * min(len(agreeing) / 3.0, 1.0),
            0,
            1,
        )
    )
    severity = float(np.clip(multimodal * agreement_boost, 0, 100))
    # Context only matters when sensors already see something.
    context = (
        0.28 * (obs.criticality / 100.0) * max(severity, 8.0)
        + 0.18 * (obs.traffic / 100.0) * max(severity, 6.0)
        + 0.10 * (obs.weather_risk / 100.0) * severity
        + 0.08 * (det / 100.0) * severity
    )
    priority_score = float(np.clip(0.72 * severity + context, 0, 100))
    if len(agreeing) >= 3 and severity >= 55:
        priority_score = max(priority_score, 62)
    if obs.criticality >= 90 and severity >= 50:
        priority_score = max(priority_score, 75)
    if layers["dynamics"] >= 50 and layers["surface"] < 18:
        priority_score = max(priority_score, 48)
    rms_delta = 0.0
    if obs.baseline_rms_g and obs.baseline_rms_g > 1e-6:
        rms_delta = 100.0 * (obs.imu.rms_vertical_g - obs.baseline_rms_g) / obs.baseline_rms_g
        if rms_delta >= 25:
            priority_score = min(100.0, priority_score + 8)
    if obs.lidar.contributors >= 2:
        if "crowd_lidar" not in agreeing:
            agreeing.append("crowd_lidar")
        priority_score = min(100.0, priority_score + 4)
    if obs.pose_quality < 35:
        confidence = float(np.clip(confidence * 0.85, 0, 1))
    claim = classify_claim(obs, layers, agreeing)
    level = _level(priority_score)
    itype = _inspection(obs, labels, len(agreeing), claim, second_pass)
    event = FusedEvent(
        segment_id=obs.segment_id,
        location=obs.location,
        labels=labels,
        multimodal_score=float(multimodal),
        confidence=confidence,
        severity=severity,
        deterioration=det,
        priority_score=priority_score,
        priority=level,
        inspection_type=itype,
        sensors_agreeing=agreeing,
        explanation="",
        recommended_action=_action(level, itype, claim),
        integrity_index=idx,
        layers=layers,
        claim=claim,
        needs_second_pass=second_pass,
        rms_delta_pct=float(rms_delta),
        la_boost=la,
        scene_id=obs.scene_id or obs.lidar.scene_id,
        contributor_count=obs.contributor_count or obs.lidar.contributors,
        pose_quality=obs.pose_quality,
    )
    event.explanation = _explain(obs, labels, agreeing, det, confidence, event)
    event.explanation = explain(event)
    return event


def _explain(obs, labels, agreeing, det, confidence, event) -> str:
    label_txt = ", ".join(sorted({x.value for x in labels})) or "no visual class"
    parts = [
        f"Vision={obs.vision.severity:.0f} ({label_txt}, {obs.vision.source}, conf={obs.vision.confidence:.2f}).",
        f"iPhone LiDAR depth={obs.lidar.depth_mm:.0f} mm, rut={obs.lidar.rut_mm:.0f} mm, pts={obs.lidar.point_count}, scanners={obs.lidar.contributors}.",
        f"Core Motion peak={obs.imu.peak_vertical_g:.2f} g (pose={obs.pose_quality:.0f}, modal={obs.imu.modal_score:.0f}).",
        f"LA prior boost={event.la_boost:.0f}. Sensors agreeing: {', '.join(agreeing) or 'none'}.",
        f"Repeat flags={obs.prior_flags}, deterioration index={det:.0f}, RMS Δ={event.rms_delta_pct:.0f}%.",
        f"Fusion confidence={confidence:.2f}. Screening only — not a structural capacity rating.",
    ]
    return " ".join(parts)


def _action(level: PriorityLevel, itype: InspectionType, claim: IntegrityClaim) -> str:
    if claim == IntegrityClaim.POSSIBLE_INTERNAL:
        return "No surface box explains the vibration shift — schedule NDT / structure-mounted sensors, do not certify from the dashcam."
    if itype == InspectionType.VISION_LLM:
        return "YOLO/LLM is uncertain; run a vision-LLM second pass on the crop, then a human if still ambiguous."
    if level == PriorityLevel.EMERGENCY:
        return "Escalate immediately; restrict lane if needed and dispatch engineer."
    if level == PriorityLevel.HIGH:
        return f"Create work order within 24h ({itype.value})."
    if level == PriorityLevel.MEDIUM:
        return f"Queue targeted inspection this week ({itype.value})."
    if level == PriorityLevel.LOW:
        return "Add to routine maintenance list; recapture on next fleet pass."
    return "Monitor automatically; no human inspection required."
