"""Los Angeles weighted distress taxonomy for LLM + fusion priors.

Heat, UV, stop-and-go traffic, utility cuts, irrigation, trees, and
occasional seismic/wildfire stress show up more often than freeze-thaw
potholes of the Midwest. Scores are relative multipliers, not probabilities.
"""

from __future__ import annotations

from infra_pulse.models import DistressClass

# 1.0 = baseline. Higher = more common / higher consequence on LA streets.
LA_CLASS_WEIGHT: dict[DistressClass, float] = {
    DistressClass.ALLIGATOR_CRACK: 1.55,
    DistressClass.POTHOLE: 1.45,
    DistressClass.RUTTING: 1.40,
    DistressClass.SHOVING: 1.35,
    DistressClass.RAVELING: 1.30,
    DistressClass.UTILITY_SETTLEMENT: 1.35,
    DistressClass.ROOT_UPLIFT: 1.25,
    DistressClass.EDGE_CRACK: 1.20,
    DistressClass.PONDING: 1.25,
    DistressClass.JOINT_FAULT: 1.15,
    DistressClass.SPALLING: 1.20,
    DistressClass.CRACK: 1.10,
    DistressClass.PATCH: 0.95,
    DistressClass.OTHER_DISTRESS: 1.00,
}

LA_FEW_SHOT = [
    {
        "text": "Blocky interconnected cracks in the wheel path on a Santa Monica Blvd asphalt lane in July heat.",
        "label": DistressClass.ALLIGATOR_CRACK.value,
        "why": "Fatigue cracking is the dominant LA asphalt failure under heat + traffic.",
    },
    {
        "text": "Bowl-shaped hole at a utility trench patch, Downtown, after first rain of the season.",
        "label": DistressClass.POTHOLE.value,
        "why": "Cuts + water, not freeze-thaw, drive many LA potholes.",
    },
    {
        "text": "Longitudinal depression in the number-one lane of the 110, buses and cars tracking the same line.",
        "label": DistressClass.RUTTING.value,
        "why": "Rutting is a first-class LADOT/Caltrans measure, not a generic 'crack'.",
    },
    {
        "text": "Asphalt shoved into a wave at a Sunset Blvd stop bar.",
        "label": DistressClass.SHOVING.value,
        "why": "Intersection shoving is common in stop-and-go heat.",
    },
    {
        "text": "Parkway sidewalk lifted in a line toward a ficus, adjacent gutter cracked.",
        "label": DistressClass.ROOT_UPLIFT.value,
        "why": "Tree-root damage is an LA sidewalk/parkway staple.",
    },
    {
        "text": "Circular dish around a manhole on a recently trenched Hollywood block.",
        "label": DistressClass.UTILITY_SETTLEMENT.value,
        "why": "Utility density is extreme; settlement is its own class.",
    },
    {
        "text": "Raveled, oxidized surface on a south-facing valley lane with UV and little shade.",
        "label": DistressClass.RAVELING.value,
        "why": "LA UV and heat strip binder; raveling is not Midwest freeze-thaw.",
    },
    {
        "text": "Water standing at a clogged catch basin after a Santa Ana-to-storm swing.",
        "label": DistressClass.PONDING.value,
        "why": "Drainage failure after rare heavy rain, not snowmelt.",
    },
]


def la_boost(labels: list[DistressClass]) -> float:
    """0-100 prior: how LA-typical and high-consequence the labels are."""
    if not labels:
        return 0.0
    w = [LA_CLASS_WEIGHT.get(x, 1.0) for x in labels]
    return float(min(100.0, (max(w) - 1.0) * 140.0 + (sum(w) / len(w) - 1.0) * 40.0))


def system_prompt() -> str:
    shots = "\n".join(
        f"- {s['text']} => {s['label']} ({s['why']})" for s in LA_FEW_SHOT
    )
    return f"""You classify pavement and nearby street-structure screening observations for Los Angeles.
You are not an engineer of record. Never say an asset is safe or has failed.

Prefer these LA-weighted classes when evidence fits:
alligator_crack, pothole, rutting, shoving, raveling, utility_settlement,
root_uplift, edge_crack, ponding, joint_fault, spalling, crack, patch, other_distress.

Los Angeles priors (use them; do not invent freeze-thaw stories):
{shots}

Return JSON only:
{{"label": "<class>", "confidence": 0-1, "rationale": "<one sentence>"}}
"""
