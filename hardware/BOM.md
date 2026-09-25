# Hardware ladder

Buy list with quantities: **[PARTS.md](PARTS.md)**. Weekend tests: **[../docs/TESTING_PLAN.md](../docs/TESTING_PLAN.md)**.

Do **not** try to certify structural capacity from a dashcam. Buy sensors that match the *layer* you want to observe.

## Use this weekend (competition)

| Part | Why | Skip if |
|---|---|---|
| Phone (best camera you have) or Pi Camera Module 3 | Surface distress for YOLO11 | — |
| MPU-6050 @ 100 Hz | Impact trigger + roughness + crude spectrum | — |
| Phone GPS | Geotag | — |
| Pi Zero 2 W as logger only | YOLO runs on the laptop | You are phone-only |

## Best upgrades, in order of integrity payoff

1. **Better IMU, faster** — ICM-42688-P or Bosch BMI088, 200–400 Hz, rigid mount on the chassis not the dash. MPU-6050 is noisy; spectrum on a bridge needs cleaner low-frequency data.
2. **Metric depth** — iPhone Pro LiDAR or Intel RealSense D435. This is how you get millimetres of rut/pothole instead of a YOLO box. Highest “wow” per dollar after the camera.
3. **Global-shutter camera** (OV9281 / Arducam) if the van is moving; rolling shutter smears cracks.
4. **GNSS** — u-blox ZED-F9P RTK so repeat visits hit the same 10 m segment.
5. **Thermal** — FLIR Lepton or MLX90640 for moisture/delamination *cues*, not proofs.
6. **Structure-mounted sensors** (only if the pitch is bridges) — geophone or PCB accelerometer on the girder. Vehicle IMUs cannot replace this.
7. **True NDT later** — GPR cart, ultrasonic pulse velocity, impact-echo. Not a $3 HC-SR04.

## Do not buy for this contest

Cheap ultrasonic rangefinders “as NDT”, custom spinning LiDAR, a drone you will not fly safely, a $90 Pi Zero from a reseller.

## Data flow

```
Vehicle drive
    → logger @ ≥100 Hz IMU + GPS
    → |az| spike or spectral shift → high-res frame
    → laptop: YOLO11 + FFT layers + fusion + map
```
