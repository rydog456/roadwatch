from __future__ import annotations

from infra_pulse.models import FusedEvent, PriorityLevel, WorkOrder


_DEADLINE = {
    PriorityLevel.EMERGENCY: 4,
    PriorityLevel.HIGH: 24,
    PriorityLevel.MEDIUM: 72,
    PriorityLevel.LOW: 168,
    PriorityLevel.MONITOR: 720,
}


def to_work_order(event: FusedEvent, seq: int) -> WorkOrder | None:
    if event.priority == PriorityLevel.MONITOR:
        return None
    return WorkOrder(
        order_id=f"WO-{seq:04d}",
        segment_id=event.segment_id,
        priority=event.priority,
        inspection_type=event.inspection_type,
        lat=event.location.lat,
        lon=event.location.lon,
        deadline_hours=_DEADLINE[event.priority],
        reason=event.recommended_action,
    )


def greedy_route(orders: list[WorkOrder], depot: tuple[float, float]) -> list[WorkOrder]:
    """Nearest-neighbor route, visiting higher priority first as a tie-break.

    Good enough for a 3-day demo; swap for OR-Tools later.
    """
    rank = {
        PriorityLevel.EMERGENCY: 0,
        PriorityLevel.HIGH: 1,
        PriorityLevel.MEDIUM: 2,
        PriorityLevel.LOW: 3,
        PriorityLevel.MONITOR: 4,
    }
    remaining = list(orders)
    lat, lon = depot
    route: list[WorkOrder] = []
    while remaining:
        remaining.sort(
            key=lambda o: (
                rank[o.priority],
                (o.lat - lat) ** 2 + (o.lon - lon) ** 2,
            )
        )
        nxt = remaining.pop(0)
        route.append(nxt)
        lat, lon = nxt.lat, nxt.lon
    return route


def recovery_rank(events: list[FusedEvent], epicenter: tuple[float, float], radius_km: float) -> list[FusedEvent]:
    """Disaster mode: keep assets near the event, rank by priority × criticality."""
    elat, elon = epicenter
    kept: list[FusedEvent] = []
    for e in events:
        dlat = (e.location.lat - elat) * 111.0
        dlon = (e.location.lon - elon) * 111.0 * max(0.2, abs(__import__("math").cos(__import__("math").radians(elat))))
        dist = (dlat**2 + dlon**2) ** 0.5
        if dist <= radius_km:
            kept.append(e)
    kept.sort(key=lambda x: x.priority_score, reverse=True)
    return kept


def crew_coverage(orders: list[WorkOrder], n_crews: int) -> dict:
    """What share of HIGH+ risk the first n crews can hit if each takes 1 job."""
    high = [o for o in orders if o.priority in (PriorityLevel.HIGH, PriorityLevel.EMERGENCY)]
    weight = {
        PriorityLevel.EMERGENCY: 3,
        PriorityLevel.HIGH: 2,
        PriorityLevel.MEDIUM: 1,
        PriorityLevel.LOW: 0.4,
        PriorityLevel.MONITOR: 0,
    }
    total = sum(weight[o.priority] for o in orders) or 1.0
    taken = greedy_route(orders, (orders[0].lat, orders[0].lon) if orders else (0, 0))[:n_crews]
    covered = sum(weight[o.priority] for o in taken)
    return {
        "crews": n_crews,
        "jobs_assigned": len(taken),
        "risk_share_pct": round(100.0 * covered / total, 1),
        "high_or_emergency_remaining": max(
            0,
            len(high) - sum(1 for o in taken if o.priority in (PriorityLevel.HIGH, PriorityLevel.EMERGENCY)),
        ),
        "assigned_ids": [o.order_id for o in taken],
    }
