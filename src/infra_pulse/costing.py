"""Pothole repair cost: Asphapro base, then LA external-factor uplift.

Base matches the published Asphapro 2026 method (same numbers as their embed):
  area_ft2 = length_ft * width_ft
  pounds = area_ft2 * (depth_in / 12) * 145 lb/ft3 * 1.20 waste
  DIY = ceil(pounds / 50) * $20 per bag (mid of their $15-25)
  Professional low/high from their size table, scaled by depth vs a 3 inch hole.

External factors (weights sum to 1) raise only the professional midpoint.
They come from the LA notes: traffic, seismic, weather, stormwater, ground
movement, wildfire. Each factor is a 0-1 severity. Uplift is capped.
"""

from __future__ import annotations

import json
import math
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from urllib import parse, request

from pydantic import BaseModel, Field

from infra_pulse.models import LidarResult

M_TO_FT = 3.280839895
MM_TO_IN = 1.0 / 25.4
DENSITY_LB_FT3 = 145.0
WASTE = 1.20
BAG_LB = 50.0
BAG_USD = 20.0

# Share of the cost uplift. From the LA brief: congestion and the first storm
# change what a patch actually costs; stormwater, quakes, and hillsides are
# the other five-star problems; wildfire is real but rarely prices one patch.
FACTOR_WEIGHTS = {
    "traffic": 0.26,
    "weather": 0.22,
    "drainage": 0.18,
    "seismic": 0.18,
    "ground": 0.12,
    "wildfire": 0.04,
}
UPLIFT_CAP = 0.85

_HIGHWAY_SEVERITY = {
    "motorway": 0.95,
    "trunk": 0.85,
    "primary": 0.70,
    "secondary": 0.45,
    "tertiary": 0.30,
    "residential": 0.12,
    "living_street": 0.08,
    "service": 0.05,
    "unclassified": 0.20,
}


class RepairEstimate(BaseModel):
    length_ft: float = 0.0
    width_ft: float = 0.0
    depth_in: float = 0.0
    area_ft2: float = 0.0
    material_lb: float = 0.0
    diy_usd: float = 0.0
    professional_low_usd: float = 0.0
    professional_high_usd: float = 0.0
    base_usd: float = 0.0
    adjusted_usd: float = 0.0
    uplift: float = 0.0
    factors: dict[str, Any] = Field(default_factory=dict)
    note: str = ""


def _get_json(url: str, timeout_s: float = 12.0) -> Any:
    req = request.Request(url, headers={"User-Agent": "InfraPulse/0.2 (pavement screening)"})
    with request.urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode("utf-8"))


def asphapro_base(length_ft: float, width_ft: float, depth_in: float) -> dict[str, float]:
    """Simple calculator: rectangular patch, no external factors."""
    length_ft = max(0.0, float(length_ft))
    width_ft = max(0.0, float(width_ft))
    depth_in = max(0.0, float(depth_in))
    area = length_ft * width_ft
    pounds = area * (depth_in / 12.0) * DENSITY_LB_FT3 * WASTE
    bags = math.ceil(pounds / BAG_LB) if pounds > 0 else 0
    diy = bags * BAG_USD
    if area <= 0 or depth_in <= 0:
        return dict(area_ft2=0, material_lb=0, diy_usd=0, professional_low_usd=0, professional_high_usd=0, base_usd=0)
    if area < 1:
        pro_low, pro_high = 50.0, 100.0
    elif area < 3:
        pro_low, pro_high = 75.0, 200.0
    elif area < 6:
        pro_low, pro_high = 150.0, 350.0
    else:
        pro_low, pro_high = 250.0, 500.0
        extra = area - 6.0
        pro_low += extra * 8.0
        pro_high += extra * 15.0
    depth_scale = min(2.0, max(0.7, depth_in / 3.0))
    pro_low *= depth_scale
    pro_high *= depth_scale
    return dict(
        area_ft2=round(area, 2),
        material_lb=round(pounds, 1),
        diy_usd=round(diy, 2),
        professional_low_usd=round(pro_low, 2),
        professional_high_usd=round(pro_high, 2),
        base_usd=round((pro_low + pro_high) / 2.0, 2),
    )


def _traffic_severity(lat: float, lon: float, fetch: Callable[[str], Any]) -> dict[str, Any]:
    key = os.environ.get("INFRA_PULSE_TOMTOM_KEY", "").strip()
    if key:
        q = parse.urlencode({"key": key, "point": f"{lat},{lon}"})
        url = f"https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json?{q}"
        body = fetch(url)
        flow = (body or {}).get("flowSegmentData") or {}
        current = float(flow.get("currentSpeed") or 0)
        free = float(flow.get("freeFlowSpeed") or 0)
        ratio = current / free if free > 1 else 1.0
        congestion = min(1.0, max(0.0, 1.0 - ratio))
        return {"severity": round(congestion, 3), "source": "tomtom", "speed_ratio": round(ratio, 2)}
    query = f"[out:json][timeout:8];way(around:35,{lat},{lon})[highway];out tags 8;"
    url = "https://overpass-api.de/api/interpreter?" + parse.urlencode({"data": query})
    body = fetch(url)
    best = 0.0
    kind = "none"
    for el in (body or {}).get("elements") or []:
        hw = str((el.get("tags") or {}).get("highway") or "")
        sev = _HIGHWAY_SEVERITY.get(hw, 0.15 if hw else 0.0)
        if sev > best:
            best, kind = sev, hw
    return {"severity": round(best, 3), "source": "openstreetmap", "highway": kind}


def _seismic_severity(lat: float, lon: float, fetch: Callable[[str], Any]) -> dict[str, Any]:
    start = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    q = parse.urlencode(
        {
            "format": "geojson",
            "latitude": lat,
            "longitude": lon,
            "maxradiuskm": 50,
            "starttime": start,
            "minmagnitude": 2.5,
            "orderby": "magnitude",
            "limit": 5,
        }
    )
    body = fetch("https://earthquake.usgs.gov/fdsnws/event/1/query?" + q)
    feats = (body or {}).get("features") or []
    mag = 0.0
    if feats:
        mag = float((feats[0].get("properties") or {}).get("mag") or 0)
    if mag >= 4.5:
        sev = 1.0
    elif mag >= 3.5:
        sev = 0.65
    elif mag >= 2.5:
        sev = 0.30
    else:
        sev = 0.0
    return {"severity": sev, "source": "usgs", "max_mag_30d": mag, "events": len(feats)}


def _weather_severity(lat: float, lon: float, fetch: Callable[[str], Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    q = parse.urlencode(
        {
            "latitude": lat,
            "longitude": lon,
            "daily": "precipitation_sum,temperature_2m_max",
            "past_days": 7,
            "forecast_days": 1,
            "timezone": "America/Los_Angeles",
        }
    )
    body = fetch("https://api.open-meteo.com/v1/forecast?" + q)
    daily = (body or {}).get("daily") or {}
    rain = [float(x) for x in (daily.get("precipitation_sum") or []) if x is not None]
    temps = [float(x) for x in (daily.get("temperature_2m_max") or []) if x is not None]
    rain_mm = sum(rain)
    heat_c = max(temps) if temps else 0.0
    if rain_mm >= 25:
        rain_sev = 1.0
    elif rain_mm >= 10:
        rain_sev = 0.55
    elif rain_mm >= 2:
        rain_sev = 0.25
    else:
        rain_sev = 0.0
    heat_sev = min(1.0, max(0.0, (heat_c - 32.0) / 10.0))
    weather = min(1.0, 0.75 * rain_sev + 0.25 * heat_sev)
    drainage = min(1.0, rain_sev)
    return (
        {
            "severity": round(weather, 3),
            "source": "open-meteo",
            "rain_7d_mm": round(rain_mm, 1),
            "max_c": round(heat_c, 1),
        },
        {"severity": round(drainage, 3), "source": "open-meteo", "note": "stormwater proxy from 7-day rain"},
    )


def _alerts(lat: float, lon: float, fetch: Callable[[str], Any]) -> dict[str, float]:
    """NWS point alerts: flood raises drainage, fire weather raises wildfire."""
    url = f"https://api.weather.gov/alerts/active?point={lat},{lon}"
    body = fetch(url)
    flood = fire = 0.0
    for feat in (body or {}).get("features") or []:
        event = str((feat.get("properties") or {}).get("event") or "").lower()
        if "flood" in event:
            flood = max(flood, 0.75)
        if "fire" in event or "red flag" in event:
            fire = max(fire, 0.7)
    return {"drainage": flood, "wildfire": fire}


def load_external(
    lat: float,
    lon: float,
    fetch: Callable[[str], Any] | None = None,
    landslide_risk: float = 0.0,
    wildfire_risk: float = 0.0,
) -> dict[str, Any]:
    """Pull traffic, USGS, and weather. Missing APIs stay at severity 0."""
    getter = fetch or _get_json
    out: dict[str, Any] = {}
    try:
        out["traffic"] = _traffic_severity(lat, lon, getter)
    except Exception as exc:
        out["traffic"] = {"severity": 0.0, "source": "unavailable", "error": type(exc).__name__}
    try:
        out["seismic"] = _seismic_severity(lat, lon, getter)
    except Exception as exc:
        out["seismic"] = {"severity": 0.0, "source": "unavailable", "error": type(exc).__name__}
    try:
        weather, drainage = _weather_severity(lat, lon, getter)
        out["weather"] = weather
        out["drainage"] = drainage
    except Exception as exc:
        out["weather"] = {"severity": 0.0, "source": "unavailable", "error": type(exc).__name__}
        out["drainage"] = {"severity": 0.0, "source": "unavailable", "error": type(exc).__name__}
    try:
        alerts = _alerts(lat, lon, getter)
        if alerts["drainage"] > float(out["drainage"].get("severity") or 0):
            out["drainage"]["severity"] = alerts["drainage"]
            out["drainage"]["source"] = "weather.gov"
        alert_fire = alerts["wildfire"]
    except Exception:
        alert_fire = 0.0
    ground = min(1.0, max(0.0, float(landslide_risk)))
    if ground == 0.0 and float(out["seismic"].get("severity") or 0) >= 0.65:
        ground = 0.25
    out["ground"] = {
        "severity": round(ground, 3),
        "source": "caller" if landslide_risk else "seismic-proxy",
    }
    fire = max(float(wildfire_risk), alert_fire)
    out["wildfire"] = {
        "severity": round(min(1.0, max(0.0, fire)), 3),
        "source": "caller" if wildfire_risk else ("weather.gov" if alert_fire else "none"),
    }
    return out


def uplift_from(factors: dict[str, Any]) -> float:
    total = 0.0
    for name, weight in FACTOR_WEIGHTS.items():
        block = factors.get(name) or {}
        sev = float(block.get("severity") or 0.0)
        total += weight * min(1.0, max(0.0, sev))
    return float(min(UPLIFT_CAP, total))


def estimate_repair(
    lidar: LidarResult,
    lat: float,
    lon: float,
    factors: dict[str, Any] | None = None,
    fetch_live: bool = True,
    landslide_risk: float = 0.0,
    wildfire_risk: float = 0.0,
) -> RepairEstimate:
    length_ft = lidar.length_m * M_TO_FT
    width_ft = lidar.width_m * M_TO_FT
    depth_in = lidar.depth_mm * MM_TO_IN
    base = asphapro_base(length_ft, width_ft, depth_in)
    if factors is None and fetch_live and base["base_usd"] > 0:
        factors = load_external(lat, lon, landslide_risk=landslide_risk, wildfire_risk=wildfire_risk)
    factors = factors or {}
    lift = uplift_from(factors) if base["base_usd"] > 0 else 0.0
    adjusted = round(base["base_usd"] * (1.0 + lift), 2)
    note = "Screening estimate from LiDAR dimensions plus public traffic, USGS, and weather. Not a bid."
    if base["base_usd"] <= 0:
        note = "No measurable depression in the merged cloud yet."
    return RepairEstimate(
        length_ft=round(length_ft, 2),
        width_ft=round(width_ft, 2),
        depth_in=round(depth_in, 2),
        uplift=round(lift, 3),
        adjusted_usd=adjusted,
        factors=factors,
        note=note,
        **base,
    )
