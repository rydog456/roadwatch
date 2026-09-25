"""Drain the device outbox when a radio comes back.

    python -m infra_pulse.sync --hub http://127.0.0.1:8000 --once
    python -m infra_pulse.sync --hub http://127.0.0.1:8000 --loop
"""

from __future__ import annotations

import argparse
import json

from infra_pulse.offline import DEFAULT_DB, Outbox, drain, sync_loop
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser(description="InfraPulse delayed sync")
    p.add_argument("--db", default=str(DEFAULT_DB))
    p.add_argument("--hub", default="http://127.0.0.1:8000")
    p.add_argument("--once", action="store_true")
    p.add_argument("--loop", action="store_true")
    p.add_argument("--interval", type=float, default=15.0)
    args = p.parse_args()
    box = Outbox(Path(args.db))
    if args.loop:
        print(f"sync loop → {args.hub} every {args.interval}s (Ctrl+C to stop)")
        try:
            sync_loop(box, args.hub, interval_s=args.interval)
        except KeyboardInterrupt:
            print("stopped")
        return
    print(json.dumps(drain(box, args.hub), indent=2))


if __name__ == "__main__":
    main()
