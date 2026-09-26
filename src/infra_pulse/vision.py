from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

import cv2
import numpy as np

from infra_pulse.config import YOLO_CONF, YOLO_IMGSZ, YOLO_LABEL_MAP
from infra_pulse.models import BoundingBox, DistressClass, VisionResult

ImageLike = Union[str, Path, np.ndarray]


def _load_bgr(image: ImageLike) -> np.ndarray:
    if isinstance(image, np.ndarray):
        return image
    img = cv2.imread(str(image))
    if img is None:
        raise FileNotFoundError(image)
    return img


def classical_distress(image: ImageLike) -> list[BoundingBox]:
    """Fallback crack/pothole cues when a custom YOLO11 weight is not trained yet."""
    bgr = _load_bgr(image)
    h, w = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    boxes: list[BoundingBox] = []

    # Dark blobs → pothole candidates
    _, dark = cv2.threshold(gray, 70, 255, cv2.THRESH_BINARY_INV)
    dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    contours, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in contours:
        area = cv2.contourArea(c)
        if area < 0.004 * w * h or area > 0.25 * w * h:
            continue
        x, y, bw, bh = cv2.boundingRect(c)
        boxes.append(
            BoundingBox(
                x1=x, y1=y, x2=x + bw, y2=y + bh,
                confidence=min(0.65, area / (0.08 * w * h)),
                label=DistressClass.POTHOLE,
                area_ratio=area / (w * h),
            )
        )

    # Morphological crack-like lines
    edges = cv2.Canny(gray, 60, 160)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 3))
    lines = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in contours:
        x, y, bw, bh = cv2.boundingRect(c)
        if bw < 40 or bh > bw * 0.6:
            continue
        area = bw * bh
        boxes.append(
            BoundingBox(
                x1=x, y1=y, x2=x + bw, y2=y + bh,
                confidence=0.45,
                label=DistressClass.CRACK,
                area_ratio=area / (w * h),
            )
        )
    return boxes


class Yolo11Detector:
    """YOLO11 pavement detector.

    Use a custom-trained weight (`pothole`, `crack`, ...) when you have it.
    Until then, COCO YOLO11n still runs; pavement-relevant boxes are kept
    and classical OpenCV cues fill the gap for the 3-day demo.
    """

    def __init__(self, weights: str = "yolo11n.pt", device: Optional[str] = None):
        self.weights = weights
        self.device = device
        self._model = None

    def _load(self):
        if self._model is None:
            from ultralytics import YOLO

            self._model = YOLO(self.weights)
        return self._model

    def detect(self, image: ImageLike, conf: float = YOLO_CONF) -> VisionResult:
        bgr = _load_bgr(image)
        h, w = bgr.shape[:2]
        boxes: list[BoundingBox] = []
        source = "classical"
        try:
            model = self._load()
            results = model.predict(
                bgr, conf=conf, imgsz=YOLO_IMGSZ, verbose=False, device=self.device
            )
            names = results[0].names
            if results[0].boxes is not None:
                for box in results[0].boxes:
                    cls_id = int(box.cls[0])
                    if isinstance(names, dict):
                        raw = str(names.get(cls_id, cls_id)).lower()
                    else:
                        raw = str(names[cls_id]).lower()
                    mapped = YOLO_LABEL_MAP.get(raw)
                    if mapped is None:
                        continue
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    area = max(0.0, (x2 - x1) * (y2 - y1))
                    boxes.append(
                        BoundingBox(
                            x1=x1, y1=y1, x2=x2, y2=y2,
                            confidence=float(box.conf[0]),
                            label=DistressClass(mapped),
                            area_ratio=area / (w * h),
                        )
                    )
            source = "yolo11"
        except Exception:
            boxes = []
            source = "classical"

        if not boxes:
            boxes = classical_distress(bgr)
            source = "classical" if source != "yolo11" else "yolo11+classical"

        severity = _vision_severity(boxes)
        conf_mean = float(np.mean([b.confidence for b in boxes])) if boxes else 0.0
        return VisionResult(
            detections=boxes,
            severity=severity,
            confidence=conf_mean,
            source=source,
        )


def _vision_severity(boxes: list[BoundingBox]) -> float:
    if not boxes:
        return 0.0
    weight = {
        DistressClass.POTHOLE: 1.0,
        DistressClass.ALLIGATOR_CRACK: 0.85,
        DistressClass.RUTTING: 0.8,
        DistressClass.SHOVING: 0.75,
        DistressClass.UTILITY_SETTLEMENT: 0.75,
        DistressClass.SPALLING: 0.7,
        DistressClass.ROOT_UPLIFT: 0.65,
        DistressClass.JOINT_FAULT: 0.65,
        DistressClass.PONDING: 0.55,
        DistressClass.CRACK: 0.55,
        DistressClass.EDGE_CRACK: 0.5,
        DistressClass.RAVELING: 0.45,
        DistressClass.PATCH: 0.35,
        DistressClass.OTHER_DISTRESS: 0.4,
    }
    score = 0.0
    for b in boxes:
        w = weight.get(b.label, 0.4)
        score += 100.0 * b.area_ratio * 10.0 * w * b.confidence
        if b.label == DistressClass.POTHOLE:
            score += 40 * b.confidence
        elif b.label in (DistressClass.ALLIGATOR_CRACK, DistressClass.RUTTING):
            score += 30 * b.confidence
        elif b.label == DistressClass.CRACK:
            score += 22 * b.confidence
        else:
            score += 14 * b.confidence
    return float(np.clip(score, 0, 100))
