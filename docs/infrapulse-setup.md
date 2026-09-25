# InfraPulse — Python prototype

From the repository root, use Python 3.11+ and install `requirements.txt` in your preferred local Python environment. On a standalone machine, for example, run `python -m pip install -r requirements.txt`. On Replit, use its package management flow rather than creating a virtual environment. Large model weights and pavement datasets are not included.

```sh
python run.py demo       # synthetic screening demonstration; no vehicle required
python run.py offline    # local queue and delayed-sync demonstration
python run.py serve      # FastAPI dashboard at http://127.0.0.1:8000
python run.py test       # Python tests
# Or directly: python -m pytest -q
```

`run.py` configures `src` on the Python import path. `hardware/pi_collector.py` is a separate optional Raspberry Pi collector; follow `hardware/PARTS.md` and `docs/TESTING_PLAN.md` before using real hardware. See the root [InfraPulse README](../README.md) for its architecture and screening limits. Do not treat simulated events or illustrative detections as verified road conditions or structural safety findings.

Keep Python dependencies, hardware captures, SQLite data, datasets, and model weights out of Git. Roadwatch's `pnpm` packages and Replit artifact workflows are independent of this prototype.