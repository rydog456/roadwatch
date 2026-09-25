from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FusionWeights:
    vision: float = 0.30
    lidar: float = 0.25
    imu: float = 0.15
    thermal: float = 0.10
    deterioration: float = 0.20


# IMU trigger: capture high-res frames when |az| exceeds this (g)
IMU_IMPACT_G = 1.8
IMU_FUSION_PEAK_G = 0.7
IMU_ZSCORE_TRIGGER = 2.0
IMU_SAMPLE_HZ = 100.0
# Hz bands: body/structure vs pavement texture vs sharp impacts
IMU_BAND_LOW = (0.5, 8.0)
IMU_BAND_MID = (8.0, 40.0)
IMU_BAND_HIGH = (40.0, 200.0)
UNCERTAIN_VISION = (0.35, 0.72)

# Thermal anomaly vs neighborhood, Celsius
THERMAL_DELTA_C = 2.5

# LiDAR millimetres below fitted road plane
LIDAR_POTHOLE_MM = 25.0
LIDAR_RUT_MM = 12.0

YOLO_CONF = 0.25
YOLO_IMGSZ = 640

# Map COCO / custom names onto pavement classes
YOLO_LABEL_MAP = {
    "pothole": "pothole",
    "crack": "crack",
    "alligator crack": "crack",
    "longitudinal crack": "crack",
    "transverse crack": "crack",
    "patch": "patch",
    "raveling": "raveling",
    "distress": "other_distress",
}

# Priority score thresholds
PRIORITY_THRESHOLDS = {
    "emergency": 80,
    "high": 58,
    "medium": 36,
    "low": 15,
}

SEGMENT_LENGTH_M = 10.0
