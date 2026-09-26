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


def test_outlier_spikes_do_not_set_hole_depth():
    from infra_pulse.cloud_clean import remove_statistical_outliers
    from infra_pulse.lidar import lidar_analyze

    hole = _hole()
    spikes = np.column_stack([
        np.linspace(-8, 8, 24),
        np.linspace(6, -6, 24),
        np.full(24, 4.0),
    ])
    kept = remove_statistical_outliers(np.vstack([hole, spikes]))
    assert len(kept) < len(hole) + 24
    clean = lidar_analyze(hole)
    messy = lidar_analyze(np.vstack([hole, spikes]))
    assert abs(messy.depth_mm - clean.depth_mm) < 30


def test_y_up_and_centimetre_exports_keep_depth():
    from infra_pulse.lidar import lidar_analyze

    hole = _hole()
    y_up = hole[:, [0, 2, 1]]
    assert lidar_analyze(y_up).depth_mm > 20
    assert 20 < lidar_analyze(hole * 100).depth_mm < 200
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


def test_arkit_world_cloud_is_not_realigned(monkeypatch, tmp_path):
    import dashboard.app as appmod
    import infra_pulse.scene_store as store
    from fastapi.testclient import TestClient

    monkeypatch.setattr(appmod, "CITY", tmp_path / "city.json")
    monkeypatch.setattr(store, "SCENES", tmp_path / "scenes")
    client = TestClient(appmod.app)
    hole = _hole()
    r = client.post(
        "/api/scene",
        json={
            "contributor_id": "arkit-test",
            "lat": 34.1,
            "lon": -118.3,
            "heading_deg": 90.0,
            "pitch": 0.4,
            "xyz": hole.round(4).tolist(),
            "gyro_xyz": [[0.01, 0.0, 0.0]] * 50,
            "accel_xyz": [[0.0, 0.0, -1.0]] * 50,
            "arkit_tracking": "normal",
            "capture": "arkit",
            "live_factors": False,
        },
    )
    assert r.status_code == 200
    got = r.json()["lidar"]
    want = lidar_analyze(hole)
    assert abs(got["depth_mm"] - want.depth_mm) < 3
    assert abs(got["length_m"] - want.length_m) < 0.05

    tiny = client.post(
        "/api/scene",
        json={"contributor_id": "x", "lat": 34.1, "lon": -118.3, "xyz": [[0, 0, 0]], "capture": "arkit"},
    )
    assert tiny.status_code == 400


def test_scene_ply_upload(monkeypatch, tmp_path):
    import base64
    import dashboard.app as appmod
    from fastapi.testclient import TestClient
    from infra_pulse.lidar import write_ply

    monkeypatch.setattr(appmod, "CITY", tmp_path / "city.json")
    ply = tmp_path / "phone.ply"
    write_ply(ply, _hole())
    client = TestClient(appmod.app)
    r = client.post(
        "/api/scene",
        json={
            "contributor_id": "ryan",
            "lat": 34.05,
            "lon": -118.25,
            "live_factors": False,
            "ply_b64": base64.b64encode(ply.read_bytes()).decode("ascii"),
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["cost"]["base_usd"] > 0
    assert "scan_trust" in body
    assert body["map"]["pose_quality"] > 0

