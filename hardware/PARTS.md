# Capture kit — iPhone only

Hardware boxes (Pi, MPU-6050, Pi camera) are **out of scope**. Capture is an **iPhone Pro / Pro Max**.

## What you need

| Qty | Item | Why |
|---|---|---|
| 1 | iPhone 12 Pro or newer (Pro Max preferred) | LiDAR + gyro + accel + GPS + barometer + magnetometer + ARKit |
| 1+ | People walking the same block | Each extra scan densifies `merged.ply` |
| 1 | Laptop | Fusion, LLM, dashboard |

Capture with **Polycam** or **Scaniverse** in LiDAR mode and export **PLY**. 3D Scanner App is acceptable. Photo mode and `.obj` meshes are not. On upload, Open3D removes statistical outliers and fits a RANSAC ground plane. If Open3D is not installed, the same two steps run in numpy. InfraPulse stores `scene.ipulse.json` + `merged.ply` per GPS cell.

## Phone sensors used

| Sensor | Role |
|---|---|
| LiDAR / scene mesh | Rut, pothole depth, settlement — stored and merged |
| Camera | LLM + optional YOLO surface class (LA-weighted) |
| Gyroscope | Pose quality (reject whip-pan scans) |
| Accelerometer | Roughness / impact |
| Magnetometer + heading | Align overlapping walks |
| GPS | Scene ID / same-place clustering |
| Barometer | Relative height on overpasses |
| ARKit tracking state | Trust / no-trust flag |

## Do not buy

Pi Zero kits, HC-SR04, drones, GPR for this version.
