# InfraPulse

This repository contains **two independent projects**, not one combined sensor pipeline:

| Project | Location | Start and validate |
| --- | --- | --- |
| InfraPulse | `src/infra_pulse/`, `dashboard/`, `hardware/`, `tests/` | [Python setup](docs/infrapulse-setup.md) |
| Roadwatch | `artifacts/`, `lib/`, `pnpm-workspace.yaml` | [Web, mobile, and API setup](docs/roadwatch-setup.md) |

InfraPulse is a Python pavement-screening prototype with an optional hardware collector. Roadwatch currently shows **illustrative** sensor-fusion detection on mobile, while its NWS weather/alerts and USGS earthquake context is **live** public data for selected demo cities; its web view shows environmental context without device detections. Neither project certifies structural safety. They do not share an ingestion API.

For collaboration, use a feature branch and pull request rather than pushing directly to `main`. See [branch and Cursor guidance](docs/collaboration.md).

Turn vehicles that already drive the network into **autonomous pavement inspectors**: detect distress, corroborate it with motion/geometry, score **inspection priority**, and emit a ranked recovery queue.

This is a **screening system**. Outputs are condition / priority scores, not a statement that a bridge or road is structurally safe.

Prompt D fit: everyday inspection on municipal and fleet vehicles; the same events re-rank after a wildfire, flood, or quake.

## How the pieces click together

```
 Camera (Pi or phone)     MPU6050 IMU          GPS              optional thermal / LiDAR
         │                     │                │                         │
         │              |az| spike? ─────────► snapshot                   │
         ▼                     ▼                ▼                         ▼
      YOLO11              roughness           lat/lon              depth / ΔT
   crack/pothole           IRI proxy            │                         │
         └─────────────────────┴────────────────┴─────────────────────────┘
                                   FUSION ENGINE
                    severity × confidence × criticality × traffic
                    + deterioration (repeat visits)
                                   │
                    work order + greedy crew route
                    disaster mode: rank inside blast radius
```

YOLO11 is the **vision specialist**. It is not an LLM. An LLM only explains fused events or reviews *uncertain* crops.

## Integrity layers (what “structural” can mean here)

| Layer | Sensor | Honest claim |
|---|---|---|
| Surface | YOLO11 + camera | Cracks, potholes, patches |
| Geometry | LiDAR / depth | Rut, hole depth, settlement |
| Dynamics | IMU spectrum | Vibration signature vs last drive |
| History | Repeat GPS visits | Getting worse, not a one-off |
| Internal | GPR / UPV / geophones | **Not on the van this weekend** |

`integrity_index` is `100 −` those distress layers. High is healthier. It is still a screen.

## Models — what to use where

| Job | Use | Do not |
|---|---|---|
| Find defects | **YOLO11** (seg if you have masks) | ChatGPT on every frame |
| Unsure crop (conf 0.35–0.72) | GPT-4o, Claude Sonnet, or Gemini 2.5 Pro vision | Send the whole video |
| Work-order wording | GPT-4o-mini / Claude via `INFRA_PULSE_LLM_URL` | Let the LLM change the score |
| Fine-tune later | YOLO11n → YOLO11s on RDD/your photos | Train a giant net in 3 days |
| Point clouds | Open3D on the laptop | Run Open3D on a Pi Zero |

## Hardware (short)

Weekend: phone + MPU-6050 + GPS. Next dollars: cleaner IMU (ICM-42688, 200 Hz+), then RealSense/iPhone LiDAR, then RTK GNSS. Bridges: sensors *on the structure*. Never treat HC-SR04 as NDT.

## 3-day build order

1. **Day 1 — sensing.** Pi Zero 2 W + MPU6050 + camera or phone. Prove IMU trigger + GPS stamp. Skip GPR/ultrasound.
2. **Day 2 — detectors.** YOLO11 on images (custom pavement weights if you have a dataset; classical OpenCV fills gaps). IMU roughness. Optional thermal/LiDAR.
3. **Day 3 — wow.** Fusion + map + work orders + “3 crews cover X% of high risk.” Drive a healthy stretch vs a fake pothole.

## Run the demo (laptop, no hardware)

From the repository root after [installing the Python requirements](docs/infrapulse-setup.md):

```sh
python run.py demo
python run.py offline
python run.py test
python run.py serve
```

Open http://127.0.0.1:8000  (`run.py` puts `src` on the path so you do not need PYTHONPATH).

Fine-tune YOLO11 later:

```powershell
python scripts/prepare_yolo_dataset.py
yolo detect train data=datasets/pavement.yaml model=yolo11n.pt epochs=50 imgsz=640
```

Then point `InfraPulsePipeline(yolo_weights="runs/detect/train/weights/best.pt")`.

Shopping list with qty/price: `hardware/PARTS.md`.  
Day-by-day tests (Fri–Sun): `docs/TESTING_PLAN.md`.  
Offline logging + delayed sync: `src/infra_pulse/offline.py` (scan never waits on cell service).

## Offline / delayed sync

The van keeps scanning in a tunnel or rural dead zone. IMU/GPS/images append locally. An SQLite **outbox** holds heartbeats and impact events as `pending`. When LTE/Wi-Fi returns, a background loop (or **Flush delayed outbox** on the dashboard) POSTs them to the hub. Records captured while radio-down, or sitting more than 20 s, are tagged **delayed**.

```powershell
$env:PYTHONPATH="src"
python scripts/demo_offline.py
python -m uvicorn dashboard.app:app --reload --app-dir .
# logger on the Pi:
python hardware/pi_collector.py --hub http://<laptop-ip>:8000
```

Force a dead zone: `$env:INFRA_PULSE_FORCE_OFFLINE="1"`

## Product positioning (from your canvas)

| Block | InfraPulse |
|---|---|
| Problem | Inspection is manual and reactive; failure is expensive; disasters multiply the queue |
| Solution | Camera + IMU + GPS on vehicles already moving; YOLO11 + fusion; auto-priority heat map |
| Value | Only keep the data you need (IMU-triggered frames); deterioration over repeat passes |
| Unfair advantage | Cheap rear-mount distribution on waste/bus/city fleets vs dedicated inspection trucks |
| Segments | Public works, city fleets, transit, utilities, insurers, inspection consultants |
| Alternatives | Blyncsy (crowdsourced / mostly stationary + LLM), FHWA camera+laser programs, manual drones |
| Revenue | $/mile, per-vehicle subscription, or data access for cities / insurers / owners |

Phone-app alternative: same algorithm, sensors already in the pocket. Hard part is getting drivers to leave it on — fleets beat consumers for the competition story.

## What we are not claiming

Surface RGB + IMU cannot see rebar, voids, or remaining structural life. NDT (ultrasound, GPR) is a later layer: *vision sees the surface, LiDAR sees movement, NDT sees what the surface cannot.*
