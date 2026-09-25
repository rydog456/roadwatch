# Testing plan — Fri 25 Sep through Sun 27 Sep 2026

Goal: one vehicle loop that **collects without cell service**, then **shows delayed pins** on the map when you get signal back. Do not add sensors until the previous day’s pass criteria are green.

## Day 1 — Friday 25 Sep — sensing + local log

**Morning (assemble)**

1. Flash Pi OS onto the 32 GB card; enable I2C + camera.
2. Wire MPU-6050: VCC 3.3 V, GND, SDA, SCL. Confirm `i2cdetect -y 1` shows `0x68`.
3. Mount camera **rear-facing**, slightly downward at pavement. Tape the IMU to the **chassis / box**, not a floppy breadboard hanging in air.
4. Power from the bank; confirm it survives 20 minutes.

**Afternoon (software on laptop + Pi)**

5. On the laptop: `python -m infra_pulse` then dashboard at http://127.0.0.1:8000 — fusion demo must run with no hardware.
6. On the Pi (or laptop sim): `python hardware/pi_collector.py --no-hub --out data/pi_run` for 2 minutes. Confirm `imu.csv` grows.
7. `python scripts/demo_offline.py` — 5 records queued offline, then flush. Pass = `pending: 0` and hub delayed count ≥ 1.

**Friday pass criteria**

- [ ] IMU numbers change when you tap the box
- [ ] CSV still writes if you turn on airplane mode / unplug Wi-Fi
- [ ] Outbox pending increases while offline

**Friday fail → do not buy thermal or LiDAR. Fix mount / I2C / power.**

## Day 2 — Saturday 26 Sep — detection + offline drive

**Morning**

1. Capture 20 stills: 10 healthy asphalt, 5 cracks, 5 pothole/bump (parking lot is fine).
2. Run YOLO11 on those stills (`Yolo11Detector`). If classes are empty, classical fallback must still box dark blobs.
3. Drive 0.5–1 mile **with Wi-Fi off / phone airplane**. Collector stays on. Do not look at the dashboard during the drive.

**Afternoon**

4. Re-enable radio. `python -m infra_pulse.sync --hub http://127.0.0.1:8000 --once` (laptop hub must be running) **or** dashboard **Flush delayed outbox**.
5. Confirm delayed badges and `delay_s` on ingested records.
6. Walk the same loop as a human: photo each flagged spot. Note false positives (shadows, manhole, rumble strips).

**Saturday pass criteria**

- [ ] At least one real distress is in the outbox with GPS (phone GPS is OK)
- [ ] Tunnel / garage / airplane-mode stretch still has heartbeats (no gaps > 15 s in csv)
- [ ] After sync, nothing in `pending` except new captures
- [ ] False-positive list written (you will say this to judges)

## Day 3 — Sunday 27 Sep — fusion demo + pitch loop

**Morning (controlled course, 20–30 min)**

Lay out four “stations” the judges can see:

| Station | What to drive over | Expected |
|---|---|---|
| A healthy | Smooth lot | monitor, integrity high |
| B crack | Tape or real crack | surface / maybe vision-LLM second pass |
| C pothole / plank gap | Real hole or 20–40 mm depression | multimodal, work order |
| D offline pocket | Underground garage / Faraday bag on the hotspot | scan continues, delayed sync at exit |

**Afternoon (story, not more sensors)**

1. Show dashboard: ranked queue + delayed ingest strip.
2. Show one **hospital-access vs quiet-street** comparison from the laptop demo if the lot is too small.
3. One slide: *we do not certify structural capacity; we screen and dispatch NDT when spectrum disagrees with the camera.*
4. Dry-run the 3-minute talk twice. Stop coding 90 minutes before judging.

**Sunday pass criteria**

- [ ] End-to-end: drive → local log → (optional dead zone) → sync → map pin
- [ ] You can unplug the laptop Wi-Fi, keep collecting, plug back in, flush
- [ ] You can explain integrity layers in 30 seconds

## Offline test protocol (repeat any day)

1. Start hub: `python -m uvicorn dashboard.app:app --app-dir .`
2. Start logger: `python hardware/pi_collector.py --hub http://<laptop-lan-ip>:8000`
3. Enable airplane mode **or** `$env:INFRA_PULSE_FORCE_OFFLINE="1"`
4. Drive / shake the IMU 60 seconds
5. Disable airplane mode / unset the env
6. Click **Flush delayed outbox** (or wait ≤15 s for the background loop)
7. Hub rows should show tag `delayed` and delay ≈ offline duration

If step 4 produces **no new csv lines**, the device died — that is a power/SD failure, not a network failure. Networking must never be on the critical path for logging.

## Roles if you have 2–3 people

| Person | Day 1 | Day 2 | Day 3 |
|---|---|---|---|
| Hardware | Wire, mount, power | Ride + GPS | Course setup |
| Software | Collector + outbox | YOLO + sync | Dashboard + backup laptop |
| Story | Parts cost slide | False-positive notes | Pitch + judge Q&A |
