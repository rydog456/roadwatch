from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class DistressClass(str, Enum):
    CRACK = "crack"
    POTHOLE = "pothole"
    OTHER_DISTRESS = "other_distress"
    PATCH = "patch"
    RAVELING = "raveling"


class PriorityLevel(str, Enum):
    MONITOR = "monitor"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EMERGENCY = "emergency"


class InspectionType(str, Enum):
    VISUAL = "visual_cv"
    ENGINEER = "engineer_inspection"
    NDT = "ndt"
    DRAINAGE = "drainage_assessment"
    MODAL = "dynamic_retest"
    VISION_LLM = "vision_llm_second_pass"
    NONE = "monitor_only"


class IntegrityClaim(str, Enum):
    SURFACE_ONLY = "surface_condition_only"
    GEOMETRY_CHANGE = "geometry_deviation"
    DYNAMIC_SHIFT = "dynamic_signature_shift"
    MULTIMODAL_DISTRESS = "multimodal_distress"
    POSSIBLE_INTERNAL = "possible_internal_issue_needs_ndt"
    HEALTHY_SCREEN = "no_screened_anomaly"


class BoundingBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float = Field(ge=0, le=1)
    label: DistressClass
    area_ratio: float = 0.0


class VisionResult(BaseModel):
    detections: list[BoundingBox] = Field(default_factory=list)
    severity: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    source: str = "yolo11"


class ImuResult(BaseModel):
    rms_vertical_g: float
    peak_vertical_g: float
    z_score: float
    roughness_iri_proxy: float
    impact_event: bool
    severity: float = Field(ge=0, le=100)
    low_band_frac: float = 0.0
    mid_band_frac: float = 0.0
    high_band_frac: float = 0.0
    spectral_peakiness: float = 0.0
    modal_score: float = Field(default=0.0, ge=0, le=100)
    dominant_hz: float = 0.0


class ThermalResult(BaseModel):
    delta_c: float
    anomaly: bool
    severity: float = Field(ge=0, le=100)


class LidarResult(BaseModel):
    depth_mm: float
    rut_mm: float
    volume_m3: float
    severity: float = Field(ge=0, le=100)


class GeoPoint(BaseModel):
    lat: float
    lon: float
    heading_deg: float = 0.0
    speed_mps: float = 0.0
    timestamp_s: float = 0.0


class SegmentObservation(BaseModel):
    segment_id: str
    location: GeoPoint
    vision: VisionResult
    imu: ImuResult
    thermal: ThermalResult
    lidar: LidarResult
    criticality: float = Field(default=50, ge=0, le=100)
    traffic: float = Field(default=50, ge=0, le=100)
    weather_risk: float = Field(default=0, ge=0, le=100)
    prior_flags: int = 0
    days_since_first_flag: int = 0
    image_path: Optional[str] = None
    baseline_rms_g: Optional[float] = None
    baseline_low_band: Optional[float] = None


class FusedEvent(BaseModel):
    segment_id: str
    location: GeoPoint
    labels: list[DistressClass]
    multimodal_score: float
    confidence: float
    severity: float
    deterioration: float
    priority_score: float
    priority: PriorityLevel
    inspection_type: InspectionType
    sensors_agreeing: list[str]
    explanation: str
    recommended_action: str
    integrity_index: float = Field(default=100, ge=0, le=100)
    layers: dict[str, float] = Field(default_factory=dict)
    claim: IntegrityClaim = IntegrityClaim.HEALTHY_SCREEN
    needs_second_pass: bool = False
    rms_delta_pct: float = 0.0


class WorkOrder(BaseModel):
    order_id: str
    segment_id: str
    priority: PriorityLevel
    inspection_type: InspectionType
    lat: float
    lon: float
    deadline_hours: int
    reason: str
    status: str = "open"
