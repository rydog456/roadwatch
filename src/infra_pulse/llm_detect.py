"""LLM structural-issue classifier with LA few-shot training baked in.

Without INFRA_PULSE_LLM_URL, uses label maps + LA priors (offline demo).
With a vision/chat endpoint, sends the taxonomy system prompt + evidence.
"""

from __future__ import annotations

import json
import os
from typing import Optional
from urllib import request

from infra_pulse.la_priors import LA_CLASS_WEIGHT, la_boost, system_prompt
from infra_pulse.models import BoundingBox, DistressClass, VisionResult
from infra_pulse.vision import _vision_severity


def _parse_label(raw: str) -> DistressClass | None:
    key = raw.strip().lower().replace(" ", "_")
    aliases = {
        "alligator": DistressClass.ALLIGATOR_CRACK,
        "fatigue": DistressClass.ALLIGATOR_CRACK,
        "rut": DistressClass.RUTTING,
        "manhole": DistressClass.UTILITY_SETTLEMENT,
        "tree": DistressClass.ROOT_UPLIFT,
    }
    if key in aliases:
        return aliases[key]
    try:
        return DistressClass(key)
    except ValueError:
        return None


def classify_offline(vision: VisionResult, notes: str = "") -> VisionResult:
    """Re-weight existing boxes with LA priors; map generic crack→alligator when notes say so."""
    boxes: list[BoundingBox] = []
    blob = notes.lower()
    for b in vision.detections:
        label = b.label
        if label == DistressClass.CRACK and any(w in blob for w in ("alligator", "fatigue", "blocky", "wheel path")):
            label = DistressClass.ALLIGATOR_CRACK
        if label == DistressClass.OTHER_DISTRESS and "rut" in blob:
            label = DistressClass.RUTTING
        w = LA_CLASS_WEIGHT.get(label, 1.0)
        boxes.append(b.model_copy(update={"label": label, "confidence": min(1.0, b.confidence * (0.85 + 0.15 * w))}))
    source = vision.source if "llm" in vision.source else f"{vision.source}+la_llm"
    return VisionResult(
        detections=boxes,
        severity=_vision_severity(boxes),
        confidence=vision.confidence,
        source=source,
    )


def classify_with_llm(evidence: dict, timeout_s: float = 12.0) -> Optional[DistressClass]:
    url = os.environ.get("INFRA_PULSE_LLM_URL")
    if not url:
        return None
    key = os.environ.get("INFRA_PULSE_LLM_KEY", "")
    model = os.environ.get("INFRA_PULSE_LLM_MODEL", "gpt-4o-mini")
    payload = {
        "model": model,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": json.dumps(evidence)[:6000]},
        ],
    }
    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {key}"} if key else {})},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout_s) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        text = body["choices"][0]["message"]["content"]
        parsed = json.loads(text)
        return _parse_label(str(parsed.get("label", "")))
    except Exception:
        return None


def apply_llm(vision: VisionResult, notes: str = "", lidar_mm: float = 0.0) -> VisionResult:
    tuned = classify_offline(vision, notes)
    label = classify_with_llm(
        {
            "notes": notes,
            "detections": [b.model_dump(mode="json") for b in tuned.detections],
            "lidar_depth_mm": lidar_mm,
        }
    )
    if label is None:
        return tuned
    if not tuned.detections:
        box = BoundingBox(x1=0, y1=0, x2=1, y2=1, confidence=0.55, label=label, area_ratio=0.02)
        boxes = [box]
    else:
        boxes = [tuned.detections[0].model_copy(update={"label": label})] + tuned.detections[1:]
    return VisionResult(
        detections=boxes,
        severity=_vision_severity(boxes),
        confidence=max(tuned.confidence, 0.55),
        source="la_llm",
    )


def labels_boost(vision: VisionResult) -> float:
    return la_boost([b.label for b in vision.detections])
