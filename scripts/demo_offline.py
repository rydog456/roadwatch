"""Competition demo: scan while 'in a tunnel', then flush when radio returns.

    $env:PYTHONPATH="src"
    $env:INFRA_PULSE_FORCE_OFFLINE="1"
    python scripts/demo_offline.py
"""

from __future__ import annotations

import os
import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from infra_pulse.hub import accept_records
from infra_pulse.offline import Outbox, drain

DB = ROOT / "data" / "device_outbox.sqlite"
HUB = ROOT / "data" / "hub.sqlite"


def main() -> None:
    os.environ["INFRA_PULSE_FORCE_OFFLINE"] = "1"
    box = Outbox(DB)
    t0 = time.time()
    for i in range(5):
        box.enqueue(
            {
                "kind": "impact" if i % 2 else "heartbeat",
                "note": f"tunnel sample {i}",
                "lat": 34.052 + i * 0.0004,
                "lon": -118.244 - i * 0.0003,
            },
            online=False,
            captured_at=t0 - 40 + i,
        )
        print("queued offline", i)
    os.environ.pop("INFRA_PULSE_FORCE_OFFLINE", None)

    def poster(_hub, items):
        print("flushing", len(items), "records to hub")
        accept_records(items, db=HUB)

    print(drain(box, "local-hub", poster=poster, online=True))
    print("device", box.stats())


if __name__ == "__main__":
    main()
