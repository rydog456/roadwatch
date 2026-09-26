"""Export LA few-shot JSONL for LLM fine-tune / system-prompt training.

    python scripts/prepare_llm_training.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from infra_pulse.la_priors import LA_FEW_SHOT, system_prompt  # noqa: E402


def main() -> None:
    out = ROOT / "datasets" / "la_distress.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for row in LA_FEW_SHOT:
            rec = {
                "messages": [
                    {"role": "system", "content": system_prompt()},
                    {"role": "user", "content": row["text"]},
                    {
                        "role": "assistant",
                        "content": json.dumps(
                            {"label": row["label"], "confidence": 0.8, "rationale": row["why"]}
                        ),
                    },
                ]
            }
            f.write(json.dumps(rec) + "\n")
    (ROOT / "datasets" / "la_system_prompt.txt").write_text(system_prompt(), encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()
