from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from infra_pulse.dispatch import crew_coverage, greedy_route, recovery_rank, to_work_order
from infra_pulse.fusion import fuse
from infra_pulse.imu import imu_analyze, should_trigger_hires
from infra_pulse.memory import BaselineStore
from infra_pulse.lidar import lidar_analyze
from infra_pulse.models import (
    FusedEvent,
    GeoPoint,
    LidarResult,
    SegmentObservation,
    ThermalResult,
    VisionResult,
    WorkOrder,
)
from infra_pulse.thermal import thermal_analyze
from infra_pulse.vision import Yolo11Detector
from infra_pulse.iphone import IPhoneScan, pose_quality
from infra_pulse.llm_detect import apply_llm, labels_boost
from infra_pulse.scene_store import ingest_scan


@dataclass
class PipelineResult:
    events: list[FusedEvent]
    orders: list[WorkOrder]
    route: list[WorkOrder]
    coverage: dict


class InfraPulsePipeline:
    def __init__(self, yolo_weights: str = "yolo11n.pt", depot: tuple[float, float] = (34.05, -118.24)):
        self.detector = Yolo11Detector(yolo_weights)
        self.depot = depot
        self._seq = 1
        self.memory = BaselineStore()

    def observe_segment(
        self,
        segment_id: str,
        location: GeoPoint,
        image: Optional[str | Path | np.ndarray] = None,
        accel_xyz: Optional[np.ndarray] = None,
        thermal_frame: Optional[np.ndarray] = None,
        lidar_xyz: Optional[np.ndarray] = None,
        criticality: float = 50,
        traffic: float = 50,
        weather_risk: float = 0,
        prior_flags: int = 0,
        days_since_first_flag: int = 0,
        vision: Optional[VisionResult] = None,
        lidar: Optional[LidarResult] = None,
        thermal: Optional[ThermalResult] = None,
        notes: str = "",
        pose_quality_score: float = 50,
        scene_id: Optional[str] = None,
        contributor_count: int = 1,
    ) -> FusedEvent:
        if vision is None:
            if image is None:
                vision = VisionResult()
            else:
                vision = self.detector.detect(image)
        lidar_depth = float(lidar.depth_mm) if lidar is not None else 0.0
        vision = apply_llm(vision, notes=notes, lidar_mm=lidar_depth)
        imu = imu_analyze(accel_xyz if accel_xyz is not None else np.zeros((16, 3)))
        prev_rms = self.memory.rms.get(segment_id)
        prev_low = self.memory.low_band.get(segment_id)
        self.memory.update(segment_id, imu.rms_vertical_g, imu.low_band_frac)
        if thermal is None:
            thermal = thermal_analyze(thermal_frame if thermal_frame is not None else np.zeros((24, 32)))
        if lidar is None:
            lidar = lidar_analyze(lidar_xyz if lidar_xyz is not None else np.zeros((0, 3)))
        obs = SegmentObservation(
            segment_id=segment_id,
            location=location,
            vision=vision,
            imu=imu,
            thermal=thermal,
            lidar=lidar,
            criticality=criticality,
            traffic=traffic,
            weather_risk=weather_risk,
            prior_flags=prior_flags,
            days_since_first_flag=days_since_first_flag,
            image_path=str(image) if isinstance(image, (str, Path)) else None,
            baseline_rms_g=prev_rms,
            baseline_low_band=prev_low,
            pose_quality=pose_quality_score,
            la_boost=labels_boost(vision),
            scene_id=scene_id or (lidar.scene_id if lidar else None),
            contributor_count=contributor_count if lidar is None else max(contributor_count, lidar.contributors),
        )
        return fuse(obs)

    def run(self, observations: list[dict], n_crews: int = 3) -> PipelineResult:
        events = [self.observe_segment(**o) for o in observations]
        orders: list[WorkOrder] = []
        for e in events:
            wo = to_work_order(e, self._seq)
            if wo:
                orders.append(wo)
                self._seq += 1
        route = greedy_route(orders, self.depot)
        cov = crew_coverage(orders, n_crews)
        return PipelineResult(events=events, orders=orders, route=route, coverage=cov)

    def ingest_iphone(self, scan: IPhoneScan, xyz: np.ndarray, notes: str = "", root=None) -> FusedEvent:
        lidar = ingest_scan(
            scan.location,
            xyz,
            scan.contributor_id,
            extra={"device": scan.device},
            root=root,
            motion=scan.motion,
        )
        pq = pose_quality(scan.motion)
        vision = None
        if scan.image_path:
            vision = self.detector.detect(scan.image_path)
        return self.observe_segment(
            segment_id=lidar.scene_id or scan.contributor_id,
            location=scan.location,
            accel_xyz=np.asarray(scan.motion.accel_xyz, dtype=float) if scan.motion.accel_xyz else None,
            vision=vision,
            lidar=lidar,
            notes=notes,
            pose_quality_score=pq,
            scene_id=lidar.scene_id,
            contributor_count=lidar.contributors,
        )

    def disaster_queue(
        self, events: list[FusedEvent], epicenter: tuple[float, float], radius_km: float = 15.0
    ) -> list[FusedEvent]:
        return recovery_rank(events, epicenter, radius_km)

    @staticmethod
    def imu_should_snapshot(accel_xyz: np.ndarray) -> bool:
        return should_trigger_hires(accel_xyz)
