from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
os.chdir(ROOT)


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="InfraPulse local runner")
    p.add_argument("cmd", nargs="?", default="demo", choices=["demo", "serve", "offline", "test"])
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args()
    if args.cmd == "demo":
        from infra_pulse.simulate import run_demo

        data = run_demo()
        print(data["summary"])
        return
    if args.cmd == "offline":
        import runpy

        runpy.run_path(str(ROOT / "scripts" / "demo_offline.py"), run_name="__main__")
        return
    if args.cmd == "test":
        import pytest

        raise SystemExit(pytest.main(["tests", "-q"]))
    import uvicorn

    uvicorn.run("dashboard.app:app", host="127.0.0.1", port=args.port, reload=False)


if __name__ == "__main__":
    main()
