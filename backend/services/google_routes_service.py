"""Real routing service for S.I.R.S.

Google Routes is still supported when a valid billing-enabled key exists, but
S.I.R.S now defaults to OpenStreetMap/OSRM real road routing so the hackathon demo
can run without Google billing.

Return shape is intentionally compatible with the previous Google service:
{
  source: "google_routes" | "osrm" | "fallback",
  normal: { path, distance_meters, duration_seconds, steps, ... },
  priority: { path, ... },
  alternatives: [...]
}
"""

from __future__ import annotations

import copy
import math
import os
from typing import Any

import httpx

from services import data_service

GOOGLE_ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
OSRM_URL = "https://router.project-osrm.org/route/v1/driving"
DEFAULT_TIMEOUT_SECONDS = float(os.getenv("ROUTING_TIMEOUT_SECONDS", "2.5"))

REAL_ROUTE_SOURCES = {"google_routes", "osrm"}
_ROUTE_CACHE: dict[tuple, dict[str, Any]] = {}
_OSRM_TEMP_DISABLED = False


# ── Settings helpers ─────────────────────────────────────────────────────────
def _settings() -> dict[str, Any]:
    try:
        return data_service.load_settings()
    except Exception:
        return {}


def get_server_key() -> str:
    settings = _settings()
    return (
        settings.get("google_routes_api_key")
        or settings.get("google_maps_server_key")
        or os.getenv("GOOGLE_ROUTES_API_KEY")
        or os.getenv("GOOGLE_MAPS_SERVER_KEY")
        or os.getenv("GOOGLE_MAPS_API_KEY")
        or ""
    ).strip()


def get_browser_key() -> str:
    settings = _settings()
    return (
        settings.get("google_maps_browser_key")
        or os.getenv("GOOGLE_MAPS_BROWSER_KEY")
        or os.getenv("GOOGLE_MAPS_API_KEY")
        or ""
    ).strip()


def google_maps_enabled() -> bool:
    settings = _settings()
    value = str(settings.get("google_maps_enabled", os.getenv("GOOGLE_MAPS_ENABLED", "true"))).lower()
    return value not in {"false", "0", "no", "off"}


def osrm_enabled() -> bool:
    settings = _settings()
    value = str(settings.get("osrm_enabled", os.getenv("OSRM_ENABLED", "true"))).lower()
    return value not in {"false", "0", "no", "off"}


def get_osrm_base_url() -> str:
    settings = _settings()
    return (settings.get("osrm_base_url") or os.getenv("OSRM_BASE_URL") or OSRM_URL).rstrip("/")


# ── Polyline helpers ─────────────────────────────────────────────────────────
def decode_polyline(encoded: str) -> list[list[float]]:
    """Decode Google encoded polyline into [[lat, lng], ...]."""
    if not encoded:
        return []

    points: list[list[float]] = []
    index = 0
    lat = 0
    lng = 0
    length = len(encoded)

    while index < length:
        result = 0
        shift = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += dlat

        result = 0
        shift = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlng = ~(result >> 1) if (result & 1) else (result >> 1)
        lng += dlng

        points.append([round(lat / 1e5, 6), round(lng / 1e5, 6)])

    return points


def _geojson_to_path(geometry: dict[str, Any] | None) -> list[list[float]]:
    coords = (geometry or {}).get("coordinates") or []
    path: list[list[float]] = []
    for point in coords:
        if len(point) >= 2:
            lng, lat = point[0], point[1]
            path.append([round(float(lat), 6), round(float(lng), 6)])
    return path


# ── Generic fallback ─────────────────────────────────────────────────────────
def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return round(radius * 2 * math.asin(math.sqrt(a)), 2)


def fallback_route(
    origin: tuple[float, float],
    destination: tuple[float, float],
    role: str = "primary",
    route_label: str = "fallback",
    error: str | None = None,
) -> dict[str, Any]:
    """Last-resort route used only if Google and OSRM are unavailable."""
    v_lat, v_lng = origin
    inc_lat, inc_lng = destination
    mid_lat = (v_lat + inc_lat) / 2
    mid_lng = (v_lng + inc_lng) / 2
    offsets = {"primary": 0.000, "secondary": 0.006, "tertiary": -0.006, "support": 0.010, "traffic": 0.004}
    off = offsets.get(role, 0.004)

    raw_path = [
        [round(v_lat, 6), round(v_lng, 6)],
        [round(v_lat, 6), round(mid_lng - off, 6)],
        [round(mid_lat + off, 6), round(mid_lng - off, 6)],
        [round(mid_lat + off, 6), round(inc_lng, 6)],
        [round(inc_lat, 6), round(inc_lng, 6)],
    ]
    path: list[list[float]] = []
    for point in raw_path:
        if not path or point != path[-1]:
            path.append(point)
    distance_km = haversine_km(v_lat, v_lng, inc_lat, inc_lng) * 1.35
    duration_min = max(3.5, round((distance_km / 38) * 60, 1))
    return {
        "source": "fallback",
        "label": route_label,
        "distance_meters": int(distance_km * 1000),
        "duration_seconds": int(duration_min * 60),
        "duration_min": duration_min,
        "encoded_polyline": "",
        "path": path,
        "steps": _fallback_steps(path),
        "error": error or "OSRM/Google routing unavailable; using deterministic emergency-corridor fallback.",
    }


def _fallback_steps(path: list[list[float]]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for i in range(max(0, len(path) - 1)):
        start = path[i]
        end = path[i + 1]
        if i == 0:
            instruction = "Depart and join the response corridor"
            maneuver = "DEPART"
        elif i == len(path) - 2:
            instruction = "Arrive at incident command point"
            maneuver = "ARRIVE"
        else:
            d_lat = end[0] - start[0]
            d_lng = end[1] - start[1]
            if abs(d_lat) > abs(d_lng):
                instruction = "Continue along corridor segment"
                maneuver = "STRAIGHT"
            else:
                instruction = "Turn toward next corridor segment"
                maneuver = "TURN"
        steps.append({"instruction": instruction, "maneuver": maneuver, "start": start, "end": end, "path": [start, end]})
    return steps


# ── Google Routes optional support ───────────────────────────────────────────
def _duration_to_seconds(value: str | int | float | None) -> int:
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    if text.endswith("s"):
        text = text[:-1]
    try:
        return int(float(text))
    except ValueError:
        return 0


def _extract_google_steps(route: dict[str, Any]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for leg in route.get("legs", []) or []:
        for step in leg.get("steps", []) or []:
            nav = step.get("navigationInstruction", {}) or {}
            poly = step.get("polyline", {}) or {}
            encoded = poly.get("encodedPolyline", "")
            path = decode_polyline(encoded)
            steps.append({
                "instruction": nav.get("instructions") or "Continue",
                "maneuver": nav.get("maneuver") or "STRAIGHT",
                "distance_meters": step.get("distanceMeters", 0),
                "duration_seconds": _duration_to_seconds(step.get("staticDuration") or step.get("duration")),
                "path": path,
                "start": path[0] if path else None,
                "end": path[-1] if path else None,
            })
    return steps


def _normalize_google_route(route: dict[str, Any], label: str) -> dict[str, Any]:
    encoded = (route.get("polyline") or {}).get("encodedPolyline", "")
    path = decode_polyline(encoded)
    duration_seconds = _duration_to_seconds(route.get("duration") or route.get("staticDuration"))
    distance_meters = int(route.get("distanceMeters") or 0)
    return {
        "source": "google_routes",
        "label": label,
        "distance_meters": distance_meters,
        "duration_seconds": duration_seconds,
        "duration_min": round(duration_seconds / 60, 1) if duration_seconds else 0,
        "encoded_polyline": encoded,
        "path": path,
        "steps": _extract_google_steps(route),
        "route_labels": route.get("routeLabels", []),
    }


def _compute_google_routes(origin: tuple[float, float], destination: tuple[float, float], role: str, compute_alternatives: bool) -> dict[str, Any] | None:
    if not google_maps_enabled():
        return None
    api_key = get_server_key()
    if not api_key:
        return None

    body: dict[str, Any] = {
        "origin": {"location": {"latLng": {"latitude": origin[0], "longitude": origin[1]}}},
        "destination": {"location": {"latLng": {"latitude": destination[0], "longitude": destination[1]}}},
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE_OPTIMAL",
        "computeAlternativeRoutes": compute_alternatives,
        "languageCode": "en",
        "units": "METRIC",
        "polylineQuality": "HIGH_QUALITY",
        "polylineEncoding": "ENCODED_POLYLINE",
    }
    field_mask = ",".join([
        "routes.duration",
        "routes.staticDuration",
        "routes.distanceMeters",
        "routes.polyline.encodedPolyline",
        "routes.routeLabels",
        "routes.legs.steps.distanceMeters",
        "routes.legs.steps.staticDuration",
        "routes.legs.steps.polyline.encodedPolyline",
        "routes.legs.steps.navigationInstruction",
    ])

    with httpx.Client(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
        response = client.post(
            GOOGLE_ROUTES_URL,
            json=body,
            headers={"Content-Type": "application/json", "X-Goog-Api-Key": api_key, "X-Goog-FieldMask": field_mask},
        )
    response.raise_for_status()
    routes = response.json().get("routes", [])
    if not routes:
        raise RuntimeError("Google Routes returned no routes")

    normalized = [_normalize_google_route(r, "normal" if i == 0 else f"alternative_{i}") for i, r in enumerate(routes)]
    normal = normalized[0]
    priority = normalized[1] if len(normalized) > 1 else normalized[0].copy()
    priority["label"] = "priority"
    return {"source": "google_routes", "normal": normal, "priority": priority, "alternatives": normalized[1:]}


# ── OSRM / OpenStreetMap primary no-billing routing ──────────────────────────
def _maneuver_instruction(step: dict[str, Any]) -> tuple[str, str]:
    maneuver = step.get("maneuver", {}) or {}
    m_type = str(maneuver.get("type") or "continue").replace("_", " ").title()
    modifier = str(maneuver.get("modifier") or "").replace("_", " ").title()
    road = step.get("name") or "unnamed road"
    if m_type.lower() == "depart":
        return "DEPART", f"Depart onto {road}"
    if m_type.lower() == "arrive":
        return "ARRIVE", "Arrive at incident command point"
    label = f"{m_type} {modifier}".strip().upper()
    instruction = f"{m_type} {modifier} onto {road}".strip()
    return label, instruction


def _normalize_osrm_route(route: dict[str, Any], label: str) -> dict[str, Any]:
    path = _geojson_to_path(route.get("geometry"))
    duration_seconds = int(route.get("duration") or 0)
    distance_meters = int(route.get("distance") or 0)

    steps: list[dict[str, Any]] = []
    for leg in route.get("legs", []) or []:
        for step in leg.get("steps", []) or []:
            step_path = _geojson_to_path(step.get("geometry"))
            maneuver, instruction = _maneuver_instruction(step)
            steps.append({
                "instruction": instruction,
                "maneuver": maneuver,
                "distance_meters": int(step.get("distance") or 0),
                "duration_seconds": int(step.get("duration") or 0),
                "path": step_path,
                "start": step_path[0] if step_path else None,
                "end": step_path[-1] if step_path else None,
                "road_name": step.get("name", ""),
            })

    return {
        "source": "osrm",
        "label": label,
        "distance_meters": distance_meters,
        "duration_seconds": duration_seconds,
        "duration_min": round(duration_seconds / 60, 1) if duration_seconds else 0,
        "encoded_polyline": "",
        "path": path,
        "steps": steps,
        "route_labels": ["OPENSTREETMAP_OSRM"],
    }


def _compute_osrm_routes(origin: tuple[float, float], destination: tuple[float, float], role: str, compute_alternatives: bool) -> dict[str, Any] | None:
    global _OSRM_TEMP_DISABLED
    if _OSRM_TEMP_DISABLED or not osrm_enabled():
        return None
    base_url = get_osrm_base_url()
    coords = f"{origin[1]},{origin[0]};{destination[1]},{destination[0]}"
    url = f"{base_url}/{coords}"
    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "true",
        "alternatives": "true" if compute_alternatives else "false",
    }
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
            response = client.get(url, params=params)
        response.raise_for_status()
    except Exception:
        # Avoid repeatedly waiting for OSRM on every vehicle if the network is blocked.
        _OSRM_TEMP_DISABLED = True
        raise
    payload = response.json()
    if payload.get("code") != "Ok":
        raise RuntimeError(payload.get("message") or f"OSRM returned {payload.get('code')}")
    routes = payload.get("routes", [])
    if not routes:
        raise RuntimeError("OSRM returned no routes")
    normalized = [_normalize_osrm_route(r, "normal" if i == 0 else f"alternative_{i}") for i, r in enumerate(routes)]
    normal = normalized[0]
    priority = normalized[1] if len(normalized) > 1 else normalized[0].copy()
    priority["label"] = "priority"
    return {"source": "osrm", "normal": normal, "priority": priority, "alternatives": normalized[1:]}


# ── Public compute API ───────────────────────────────────────────────────────
def compute_routes(
    origin: tuple[float, float],
    destination: tuple[float, float],
    *,
    role: str = "primary",
    compute_alternatives: bool = True,
) -> dict[str, Any]:
    """Return normal + priority real road routes.

    Priority ETA optimization is still applied by the Emergency Agent, but the
    visible path comes from real roads whenever OSRM or Google returns geometry.
    """
    cache_key = (round(origin[0], 5), round(origin[1], 5), round(destination[0], 5), round(destination[1], 5), role, bool(compute_alternatives), bool(get_server_key() and google_maps_enabled()), bool(osrm_enabled()))
    if cache_key in _ROUTE_CACHE:
        return copy.deepcopy(_ROUTE_CACHE[cache_key])

    errors: list[str] = []

    # Try Google only if a server key is present. If billing is unavailable, this
    # will fail with 403 and immediately fall back to OSRM.
    if get_server_key() and google_maps_enabled():
        try:
            google_result = _compute_google_routes(origin, destination, role, compute_alternatives)
            if google_result:
                _ROUTE_CACHE[cache_key] = copy.deepcopy(google_result)
                return google_result
        except Exception as exc:
            errors.append(f"Google Routes: {exc}")

    try:
        osrm_result = _compute_osrm_routes(origin, destination, role, compute_alternatives)
        if osrm_result:
            _ROUTE_CACHE[cache_key] = copy.deepcopy(osrm_result)
            return osrm_result
    except Exception as exc:
        errors.append(f"OSRM: {exc}")

    error_text = " / ".join(errors) if errors else "No routing provider configured"
    normal = fallback_route(origin, destination, role, "normal", error=error_text)
    priority = fallback_route(origin, destination, role, "priority", error=error_text)
    result = {"source": "fallback", "normal": normal, "priority": priority, "alternatives": [], "error": error_text}
    _ROUTE_CACHE[cache_key] = copy.deepcopy(result)
    return result


def diagnostics(origin: tuple[float, float] = (24.7436, 46.6553), destination: tuple[float, float] = (24.7136, 46.6753)) -> dict[str, Any]:
    """Best-effort diagnostics for Settings/Test Connection."""
    result = compute_routes(origin, destination, role="diagnostic", compute_alternatives=False)
    normal = result.get("normal", {})
    src = result.get("source")
    if src == "google_routes":
        message = "Google Routes ready."
    elif src == "osrm":
        message = "OSRM/OpenStreetMap real road routing ready — no Google billing required."
    else:
        message = result.get("error") or normal.get("error") or "Routing fallback active."
    return {
        "routes_enabled": True,
        "routes_key_configured": bool(get_server_key()),
        "osrm_enabled": osrm_enabled(),
        "source": src,
        "message": message,
        "point_count": len(normal.get("path", [])),
        "distance_meters": normal.get("distance_meters"),
        "duration_seconds": normal.get("duration_seconds"),
    }
