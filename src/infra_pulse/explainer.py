from __future__ import annotations

import json
import os
from typing import Optional
from urllib import request

from infra_pulse.models import FusedEvent

SYSTEM = """You are a Los Angeles pavement screening assistant, not an engineer of record.
Never say an asset is safe or has failed. Prefer LA-typical classes (alligator, rutting,
utility settlement, root uplift, shoving) when the evidence fits. Mention iPhone LiDAR
depth, crowd-merged PLY contributors, and Core Motion pose quality. Output 4 short sentences max."""


def template_explain(event: FusedEvent) -> str:
    layers = event.layers or {}
    return (
        f"Integrity index {event.integrity_index:.0f}/100 (screening only; claim={event.claim.value}). "
        f"Layers — surface {layers.get('surface', 0):.0f}, geometry {layers.get('geometry', 0):.0f}, "
        f"dynamics {layers.get('dynamics', 0):.0f}, history {layers.get('history', 0):.0f}. "
        f"{event.explanation} Next: {event.recommended_action}"
    )


def llm_explain(event: FusedEvent, timeout_s: float = 12.0) -> Optional[str]:
    """Optional second-voice explanation. Detection still comes from YOLO + fusion.

    Set INFRA_PULSE_LLM_URL to an OpenAI-compatible /chat/completions endpoint
    and INFRA_PULSE_LLM_KEY if needed. Example models that are useful here:
    - GPT-4.1 / GPT-4o for work-order language
    - Claude Sonnet for careful 'do not overclaim' wording
    - Gemini 2.5 Pro or GPT-4o for uncertain image crops only (not every frame)
    Do not send the whole drive to an LLM.
    """
    url = os.environ.get("INFRA_PULSE_LLM_URL")
    if not url:
        return None
    key = os.environ.get("INFRA_PULSE_LLM_KEY", "")
    model = os.environ.get("INFRA_PULSE_LLM_MODEL", "gpt-4o-mini")
    payload = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": json.dumps(event.model_dump(mode="json"), indent=2)[:8000],
            },
        ],
    }
    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {key}"} if key else {})},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout_s) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


def explain(event: FusedEvent) -> str:
    return llm_explain(event) or template_explain(event)
