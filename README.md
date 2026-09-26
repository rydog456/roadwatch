# InfraPulse

iPhone Pro / Pro Max **LiDAR + Core Motion** screening for pavement and nearby street structure. An **LLM** (few-shot trained on **Los Angeles** distress) classifies issues; fusion puts extra weight on alligator cracking, rutting, utility settlement, root uplift, shoving, and heat/UV raveling. Multiple people scanning the same GPS cell **merge ASCII PLY** files into a denser deterioration map.

This is a **screening system**. It is not a structural capacity rating.

## How it works

```
iPhone Pro Max
  LiDAR mesh (PLY)   camera   gyro / accel   magnetometer   GPS   barometer   ARKit
         │              │            │              │         │        │         │
         │              ▼            ▼              │         │        │         │
         │         LLM + LA taxonomy          pose quality    scene ID  Z hint  trust
         │         (YOLO optional)            (reject whip)      │        │
         ▼                                                      ▼        ▼
   contrib_*.ply  ──voxel merge (min Z)──►  merged.ply + scene.ipulse.json
                                   FUSION
              LiDAR geometry × LA prior × Core Motion × repeat visits
                                   │
                    work order + greedy crew route
```

Hardware kits (Pi, MPU-6050, Pi camera) are **out of scope**. Capture is the phone you already have.

## LA-weighted LLM training

Taxonomy and few-shots live in `src/infra_pulse/la_priors.py`. Offline, notes like “alligator … wheel path” remap generic `crack` to `alligator_crack`. With `INFRA_PULSE_LLM_URL` set, the same system prompt is sent to an OpenAI-compatible chat endpoint.

```powershell
python scripts/prepare_llm_training.py
```

Writes `datasets/la_distress.jsonl` and `datasets/la_system_prompt.txt` for fine-tune or RAG.

## Collaborative LiDAR

Each scan is stored as ASCII **PLY** (3D Scanner App, Polycam, or ARKit export). Same ~20 m GPS cell → same `data/scenes/<scene_id>/` folder. Voxel merge keeps the **lowest Z** so holes and ruts survive as coverage grows. Gyro / pitch / roll / compass heading rotate each cloud into the first contributor’s frame; barometer only supplies a clipped height hint (overpasses), not millimetre depth.

File layout:

```
data/scenes/la_<lat>_<lon>/
  scene.ipulse.json
  merged.ply
  contrib_<id>_<ts>.ply
```

## Run

```powershell
cd C:\Users\admin\infra-pulse
.\.venv\Scripts\Activate.ps1
python run.py demo
python run.py test
python run.py serve
python scripts/prepare_llm_training.py
```

Open http://127.0.0.1:8000

POST two walks of the same block: `POST /api/scene` with `contributor_id`, `lat`, `lon`, `heading_deg`, and `xyz` points.

Capture checklist: `hardware/PARTS.md`. Field tests: `docs/TESTING_PLAN.md`.

## Product positioning

| Block | InfraPulse |
|---|---|
| Problem | Inspection is manual; LA streets fail from heat, traffic, utilities, and trees more than freeze-thaw |
| Solution | Crowd LiDAR on iPhone Pro + LLM with LA priors + fusion queue |
| Value | Same place scanned by many people becomes a fuller 3D record |
| Unfair advantage | No custom van; Pro Max LiDAR is already in inspectors’ pockets |
| Segments | Public works, 311 follow-up, fleets, utilities |
| Alternatives | Dedicated inspection trucks, photo-only 311, Blyncsy-style reports |

## What we are not claiming

Phone LiDAR + RGB cannot see rebar, voids, or remaining structural life. NDT stays a later handoff.
