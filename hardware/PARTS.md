# Parts list — buy this weekend

Prices are typical US street prices as of late 2026 planning; check current listings. **Buy the core kit first.** Optional rows only if they are already in the room or you have leftover budget after Day 1 works.

## Core kit (required)

| Qty | Part | Why | Approx |
|---|---|---|---|
| 1 | Raspberry Pi Zero 2 W | Logger only (not YOLO) | $15–30 |
| 1 | 32 GB microSD (A2) + USB reader | OS + local outbox | $10 |
| 1 | 5 V power bank 5,000–10,000 mAh | Untethered drive | $15–25 |
| 1 | MPU-6050 breakout (I2C 0x68) | Impact + 100 Hz vibration | $6–15 |
| 1 | Jumper wires + mini breadboard | Wire IMU without soldering Day 1 | $8 |
| 1 | Pi Camera Module 3 **or** use a phone camera | Pavement RGB for YOLO11 | $30–40 / $0 if phone |
| 1 | Rear suction / action-cam mount | Camera looks at the wake of the vehicle | $12–20 |
| 1 | USB GPS dongle **or** phone GPS | Stamp every event | $15–30 / $0 |
| 1 | Laptop (you already have) | YOLO11 + dashboard + delayed sync hub | — |

**Core total if you already have a phone + laptop: about $70–140.** With Pi camera + USB GPS: about **$120–210**.

## Strongly recommended (Day 2–3 if core is working)

| Qty | Part | Why | Approx |
|---|---|---|---|
| 1 | USB-C / micro-USB data cable | Pi serial / power | $8 |
| 1 | Velcro + zip ties + gaffer tape | Keep the box from bouncing (IMU noise) | $10 |
| 1 | Lens cloth + zip bag | Dust on the rear camera kills YOLO | $5 |
| 1 | Printed QR / notebook | Log start/stop GPS for each test loop | $0 |

## Integrity upgrades (only after the core demo works)

| Qty | Part | Why | Approx |
|---|---|---|---|
| 1 | ICM-42688-P or BMI088 IMU | Cleaner spectrum than MPU-6050 | $15–25 |
| 1 | iPhone Pro (LiDAR) or Intel RealSense D435 | Millimetre rut / pothole depth | $0 / ~$250–350 |
| 1 | u-blox ZED-F9P RTK (later) | Hit the same 10 m segment next week | $80–150 |
| 1 | MLX90640 thermal array | Moisture / patch cue | $70–100 |

## Do not buy this weekend

| Skip | Reason |
|---|---|
| HC-SR04 ultrasonic | Range finder, not NDT |
| Extra drones | You will not get a safe flight + CV pipeline in 3 days |
| GPR / professional ultrasound | Phase 2 |
| $90 reseller Pi Zero | Overpay; wait or use the phone logger |

## What the offline box actually stores

Even with **zero bars**, the Pi writes:

- `imu.csv` / `gps.csv` (append-only)
- `images/` on IMU trigger
- `outbox.sqlite` (pending heartbeats + impacts)

When Wi-Fi or LTE returns, `sync` drains the outbox. Events get a **delayed** flag if they were captured offline or sat >20 s. Scanning never blocks on the network.
