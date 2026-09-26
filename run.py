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
    port = int(os.environ.get("PORT", args.port))
    import socket
    import uvicorn

    def _lan_ip() -> str:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            sock.close()
            return ip
        except OSError:
            return "this-pc"

    lan = _lan_ip()
    print(f"On this PC:  http://127.0.0.1:{port}", flush=True)
    print(f"On the iPhone (same Wi-Fi):  http://{lan}:{port}", flush=True)
    print("On Replit, open the HTTPS webview. That is the address that can use the phone GPS.", flush=True)
    uvicorn.run("dashboard.app:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
