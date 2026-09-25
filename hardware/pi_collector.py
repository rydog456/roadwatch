"""Edge logger: always write locally; sync later when a radio returns.

    python hardware/pi_collector.py --hub http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import csv
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from infra_pulse.offline import Outbox, RadioCache, sync_loop  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def collect(out: Path, hz: int = 100, hub: str | None = None) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "images").mkdir(exist_ok=True)
    imu_path = out / "imu.csv"
    gps_path = out / "gps.csv"
    new_imu = not imu_path.exists() or imu_path.stat().st_size == 0
    new_gps = not gps_path.exists() or gps_path.stat().st_size == 0
    box = Outbox(out / "outbox.sqlite")
    radio = RadioCache(hub, ttl_s=5.0)

    stop = threading.Event()
    if hub:
        threading.Thread(target=sync_loop, args=(box, hub, 15.0, stop), daemon=True).start()
        print(f"Background sync → {hub} (queues while offline).")

    try:
        from mpu6050 import mpu6050  # type: ignore

        imu = mpu6050(0x68)
    except Exception:
        imu = None
        print("MPU6050 not found; writing simulated IMU ticks.")

    try:
        from picamera2 import Picamera2  # type: ignore

        cam = Picamera2()
        cam.configure(cam.create_still_configuration())
        cam.start()
    except Exception:
        cam = None
        print("Pi camera not found; IMU events will be logged without images.")

    with imu_path.open("a", newline="") as f_imu, gps_path.open("a", newline="") as f_gps:
        imu_w = csv.writer(f_imu)
        gps_w = csv.writer(f_gps)
        if new_imu:
            imu_w.writerow(["t", "ax", "ay", "az", "gx", "gy", "gz", "trigger", "online"])
        if new_gps:
            gps_w.writerow(["t", "lat", "lon", "online"])
        print("Collecting (local-first). Ctrl+C to stop.")
        window: list[list[float]] = []
        last_heartbeat = 0.0
        np = None
        should_trigger_hires = None
        try:
            while True:
                t = time.time()
                online = radio.check()
                if imu:
                    a = imu.get_accel_data()
                    g = imu.get_gyro_data()
                    ax, ay, az = a["x"] / 9.81, a["y"] / 9.81, a["z"] / 9.81
                    gx, gy, gz = g["x"], g["y"], g["z"]
                else:
                    ax = ay = 0.0
                    az = 1.0
                    gx = gy = gz = 0.0
                window.append([ax, ay, az])
                if len(window) > max(hz, 16):
                    window.pop(0)
                trigger = False
                if len(window) >= 16:
                    if np is None:
                        import numpy as np  # type: ignore
                        from infra_pulse.imu import should_trigger_hires as _trig

                        should_trigger_hires = _trig
                    trigger = should_trigger_hires(np.array(window))
                imu_w.writerow([t, ax, ay, az, gx, gy, gz, int(trigger), int(online)])
                gps_w.writerow([t, "", "", int(online)])
                f_imu.flush()
                f_gps.flush()

                snapshot = None
                if trigger and cam:
                    snapshot = str(out / "images" / f"{int(t * 1000)}.jpg")
                    cam.capture_file(snapshot)

                if trigger or (t - last_heartbeat >= 5.0):
                    last_heartbeat = t
                    box.enqueue(
                        {
                            "kind": "impact" if trigger else "heartbeat",
                            "captured_at": t,
                            "iso": utc_now(),
                            "ax": ax,
                            "ay": ay,
                            "az": az,
                            "trigger": trigger,
                            "vehicle_online": online,
                        },
                        image_path=snapshot,
                        online=online,
                        captured_at=t,
                    )
                time.sleep(1.0 / max(hz, 1))
        except KeyboardInterrupt:
            print("Stopped. Outbox:", json.dumps(box.stats()))
        finally:
            stop.set()
            box.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=Path("data/pi_run"))
    p.add_argument("--hz", type=int, default=100)
    p.add_argument("--hub", default="http://127.0.0.1:8000")
    p.add_argument("--no-hub", action="store_true", help="log only; never attempt sync")
    args = p.parse_args()
    collect(args.out, args.hz, hub=None if args.no_hub else args.hub)


if __name__ == "__main__":
    main()
