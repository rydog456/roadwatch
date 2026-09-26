from infra_pulse.costing import FACTOR_WEIGHTS, asphapro_base, estimate_repair
from infra_pulse.lidar import lidar_analyze
from infra_pulse.models import LidarResult
import numpy as np


def _hole(depth_m: float = 0.05) -> np.ndarray:
    rng = np.random.default_rng(2)
    x = rng.uniform(-1.2, 1.2, 500)
    y = rng.uniform(-0.6, 0.6, 500)
    z = rng.normal(0, 0.002, 500)
    mask = (np.abs(x) < 0.4) & (np.abs(y) < 0.25)
    z[mask] -= depth_m
    return np.column_stack([x, y, z])


def test_asphapro_medium_hole_matches_size_table():
    base = asphapro_base(1.5, 1.2, 2.5)
    assert 1 < base["area_ft2"] < 3
    assert base["diy_usd"] > 0
    assert 75 <= base["professional_low_usd"] or base["professional_low_usd"] > 0
    assert base["professional_high_usd"] >= base["professional_low_usd"]
    assert base["base_usd"] == round((base["professional_low_usd"] + base["professional_high_usd"]) / 2, 2)


def test_factor_weights_sum_to_one():
    assert abs(sum(FACTOR_WEIGHTS.values()) - 1.0) < 1e-9


def test_traffic_uplift_raises_professional_midpoint():
    lidar = LidarResult(
        depth_mm=50, rut_mm=10, volume_m3=0.01, severity=40,
        length_m=0.6, width_m=0.4,
    )
    plain = estimate_repair(lidar, 34.05, -118.24, factors={}, fetch_live=False)
    busy = estimate_repair(
        lidar,
        34.05,
        -118.24,
        factors={"traffic": {"severity": 1.0}},
        fetch_live=False,
    )
    assert plain.adjusted_usd == plain.base_usd
    assert busy.adjusted_usd > plain.base_usd
    assert abs(busy.uplift - FACTOR_WEIGHTS["traffic"]) < 1e-6


def test_lidar_hole_has_plan_dimensions():
    result = lidar_analyze(_hole())
    assert result.depth_mm > 20
    assert result.length_m > 0.2
    assert result.width_m > 0.2
    est = estimate_repair(result, 34.05, -118.24, factors={}, fetch_live=False)
    assert est.base_usd > 0
    assert est.depth_in > 0


def test_city_map_keeps_one_row_per_scene(tmp_path):
    from infra_pulse.city_store import defect_record, load_defects, upsert_defect

    lidar = LidarResult(
        depth_mm=40, rut_mm=0, volume_m3=0.01, severity=30,
        scene_id="la_1", length_m=0.5, width_m=0.4, contributors=2,
    )
    path = tmp_path / "city.json"
    upsert_defect(defect_record(lidar, 34.05, -118.24, "a", {"base_usd": 10}), path)
    upsert_defect(defect_record(lidar, 34.05, -118.24, "b", {"base_usd": 12}), path)
    rows = load_defects(path)
    assert len(rows) == 1
    assert rows[0]["cost"]["base_usd"] == 12
    assert rows[0]["lat"] == 34.05


def test_scene_api_stores_gps_and_both_costs(monkeypatch, tmp_path):
    import dashboard.app as appmod
    from fastapi.testclient import TestClient

    monkeypatch.setattr(appmod, "CITY", tmp_path / "city.json")
    client = TestClient(appmod.app)
    r = client.post(
        "/api/scene",
        json={
            "contributor_id": "ryan",
            "lat": 34.0522,
            "lon": -118.2437,
            "xyz": _hole().round(4).tolist(),
            "live_factors": False,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["cost"]["base_usd"] > 0
    assert body["cost"]["adjusted_usd"] == body["cost"]["base_usd"]
    assert body["map"]["lat"] == 34.0522
    assert body["lidar"]["depth_mm"] > 20

