"""Google Places integration for real emergency-service origins.

This service fixes the biggest demo realism issue: station coordinates should not
come from mock demo data. It can use Google Places if billing is available, but
for this no-billing build it falls back to curated Riyadh station data.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from services import data_service

NEARBY_URL = "https://places.googleapis.com/v1/places:searchNearby"
TEXT_URL = "https://places.googleapis.com/v1/places:searchText"
DEFAULT_TIMEOUT_SECONDS = 10
DEFAULT_RADIUS_METERS = 12000

# Small in-memory cache to keep the live demo fast and avoid repeated paid calls.
_CACHE: dict[str, Any] = {}


def _settings() -> dict[str, Any]:
    try:
        return data_service.load_settings()
    except Exception:
        return {}


def get_places_key() -> str:
    settings = _settings()
    return (
        settings.get("google_places_api_key")
        or settings.get("google_routes_api_key")
        or settings.get("google_maps_server_key")
        or os.getenv("GOOGLE_PLACES_API_KEY")
        or os.getenv("GOOGLE_ROUTES_API_KEY")
        or os.getenv("GOOGLE_MAPS_SERVER_KEY")
        or os.getenv("GOOGLE_MAPS_API_KEY")
        or ""
    ).strip()


def places_enabled() -> bool:
    settings = _settings()
    value = str(settings.get("google_places_enabled", settings.get("google_maps_enabled", "true"))).lower()
    return value not in {"false", "0", "no", "off"}


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.location,places.types,places.googleMapsUri",
    }


def _normalize(place: dict[str, Any], service_type: str) -> dict[str, Any] | None:
    loc = place.get("location") or {}
    lat = loc.get("latitude")
    lng = loc.get("longitude")
    if lat is None or lng is None:
        return None
    name = ((place.get("displayName") or {}).get("text") or "Google Place").strip()
    return {
        "id": place.get("id") or name,
        "name": name,
        "lat": float(lat),
        "lng": float(lng),
        "address": place.get("formattedAddress", ""),
        "types": place.get("types", []),
        "google_maps_uri": place.get("googleMapsUri", ""),
        "service_type": service_type,
        "source": "google_places",
    }


def nearby_place(lat: float, lng: float, included_types: list[str], service_type: str, radius_m: int = DEFAULT_RADIUS_METERS) -> dict[str, Any] | None:
    if not places_enabled():
        return None
    api_key = get_places_key()
    if not api_key:
        return None

    cache_key = f"nearby:{service_type}:{round(lat,4)}:{round(lng,4)}:{','.join(included_types)}"
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    body = {
        "includedTypes": included_types,
        "maxResultCount": 5,
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": radius_m,
            }
        },
        "rankPreference": "DISTANCE",
        "languageCode": "en",
    }
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
            response = client.post(NEARBY_URL, json=body, headers=_headers(api_key))
        response.raise_for_status()
        places = response.json().get("places", []) or []
        result = _normalize(places[0], service_type) if places else None
        _CACHE[cache_key] = result
        return result
    except Exception as exc:
        _CACHE[cache_key] = {"source": "google_places_error", "service_type": service_type, "error": str(exc)}
        return None


def text_place(lat: float, lng: float, query: str, service_type: str, radius_m: int = DEFAULT_RADIUS_METERS) -> dict[str, Any] | None:
    if not places_enabled():
        return None
    api_key = get_places_key()
    if not api_key:
        return None

    cache_key = f"text:{service_type}:{round(lat,4)}:{round(lng,4)}:{query.lower()}"
    if cache_key in _CACHE:
        cached = _CACHE[cache_key]
        return cached if isinstance(cached, dict) and cached.get("lat") is not None else None

    body = {
        "textQuery": query,
        "maxResultCount": 5,
        "locationBias": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": radius_m,
            }
        },
        "languageCode": "en",
    }
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
            response = client.post(TEXT_URL, json=body, headers=_headers(api_key))
        response.raise_for_status()
        places = response.json().get("places", []) or []
        result = _normalize(places[0], service_type) if places else None
        _CACHE[cache_key] = result
        return result
    except Exception as exc:
        _CACHE[cache_key] = {"source": "google_places_error", "service_type": service_type, "error": str(exc)}
        return None



def _dist_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    import math
    r = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return r * 2 * math.asin(math.sqrt(a))


def _nearest_from_city_data(lat: float, lng: float) -> dict[str, Any]:
    """Use the curated Riyadh station dataset when Google Places is not available."""
    try:
        city = data_service.load_city_data()
    except Exception:
        city = {}

    def nearest(items: list[dict[str, Any]], service_type: str) -> dict[str, Any] | None:
        candidates = [i for i in items if i.get("lat") is not None and i.get("lng") is not None]
        if not candidates:
            return None
        best = min(candidates, key=lambda x: _dist_km(lat, lng, float(x["lat"]), float(x["lng"])))
        return {
            "id": best.get("id") or best.get("name") or service_type,
            "name": best.get("name") or service_type,
            "lat": float(best["lat"]),
            "lng": float(best["lng"]),
            "address": best.get("address", "Riyadh, Saudi Arabia"),
            "service_type": service_type,
            "source": "riyadh_local_real",
            "distance_km": round(_dist_km(lat, lng, float(best["lat"]), float(best["lng"])), 2),
        }

    origins: dict[str, Any] = {}
    ambulance = nearest(city.get("ambulance_bases", []), "ambulance_base")
    hospital = nearest(city.get("hospitals", []), "destination_hospital")
    fire = nearest(city.get("fire_stations", []), "fire_station")
    police = nearest(city.get("police_stations", []), "police")
    cd = nearest(city.get("civil_defense", []), "civil_defense")
    traffic = nearest(city.get("traffic_units", []), "traffic_unit")
    road_service = nearest(city.get("road_service_units", []), "road_service")

    # Ambulance origin must be an EMS / Red Crescent dispatch base.
    # Hospitals remain patient destinations, not default ambulance origins.
    if ambulance:
        origins["Ambulance"] = ambulance
    if hospital:
        origins["Destination Hospital"] = hospital
    if fire:
        origins["Fire Truck"] = fire
    if police:
        origins["Police Car"] = police
    if cd:
        origins["Civil Defense"] = cd
    if traffic:
        origins["Traffic Unit"] = traffic
    if road_service:
        origins["Road Service"] = road_service
    return origins


def find_real_emergency_origins(lat: float, lng: float) -> dict[str, Any]:
    """Return emergency-service origins near the incident.

    Google Places is optional. If it is unavailable because billing is not enabled,
    S.I.R.S uses the curated Riyadh station dataset instead of mock demo data.
    """
    api_key = get_places_key()
    local_origins = _nearest_from_city_data(lat, lng)

    if not places_enabled() or not api_key:
        return {
            "source": "riyadh_local_real",
            "enabled": places_enabled(),
            "configured": bool(api_key),
            "origins": local_origins,
            "message": "Using curated Riyadh emergency-service origins. Google Places is optional.",
        }

    origins: dict[str, Any] = {}
    errors: list[str] = []

    try:
        ambulance = (
            text_place(lat, lng, "Saudi Red Crescent ambulance station Riyadh", "ambulance_base")
            or text_place(lat, lng, "ambulance station Riyadh", "ambulance_base")
        )
        if ambulance:
            origins["Ambulance"] = ambulance
    except Exception as exc:
        errors.append(f"ambulance_base: {exc}")

    try:
        hospital = nearby_place(lat, lng, ["hospital"], "destination_hospital") or text_place(lat, lng, "hospital near Riyadh", "destination_hospital")
        if hospital:
            origins["Destination Hospital"] = hospital
    except Exception as exc:
        errors.append(f"hospital_destination: {exc}")

    try:
        fire = nearby_place(lat, lng, ["fire_station"], "fire_station") or text_place(lat, lng, "fire station near Riyadh", "fire_station")
        if fire:
            origins["Fire Truck"] = fire
    except Exception as exc:
        errors.append(f"fire: {exc}")

    try:
        police = nearby_place(lat, lng, ["police"], "police") or text_place(lat, lng, "police station near Riyadh", "police")
        if police:
            origins["Police Car"] = police
    except Exception as exc:
        errors.append(f"police: {exc}")

    try:
        civil_defense = (
            text_place(lat, lng, "Civil Defense Riyadh", "civil_defense")
            or text_place(lat, lng, "Saudi Civil Defense Riyadh", "civil_defense")
            or text_place(lat, lng, "الدفاع المدني الرياض", "civil_defense")
        )
        if civil_defense:
            origins["Civil Defense"] = civil_defense
    except Exception as exc:
        errors.append(f"civil_defense: {exc}")

    try:
        traffic_unit = (
            text_place(lat, lng, "traffic patrol Riyadh", "traffic_unit")
            or text_place(lat, lng, "traffic police Riyadh", "traffic_unit")
        )
        if traffic_unit:
            origins["Traffic Unit"] = traffic_unit
    except Exception as exc:
        errors.append(f"traffic_unit: {exc}")

    try:
        road_service = (
            text_place(lat, lng, "tow truck service Riyadh", "road_service")
            or text_place(lat, lng, "roadside assistance Riyadh", "road_service")
        )
        if road_service:
            origins["Road Service"] = road_service
    except Exception as exc:
        errors.append(f"road_service: {exc}")

    if origins:
        # Fill any missing emergency type from the Riyadh curated data.
        for key, value in local_origins.items():
            origins.setdefault(key, value)
        return {
            "source": "google_places",
            "enabled": True,
            "configured": True,
            "origins": origins,
            "message": "Google Places origins loaded; missing types filled from Riyadh local data.",
        }

    return {
        "source": "riyadh_local_real",
        "enabled": True,
        "configured": True,
        "origins": local_origins,
        "message": "Google Places unavailable/403. Using curated Riyadh emergency-service origins instead.",
        "errors": errors,
    }

def diagnostics(lat: float = 24.7136, lng: float = 46.6753) -> dict[str, Any]:
    origins = find_real_emergency_origins(lat, lng)
    return {
        "places_enabled": places_enabled(),
        "places_key_configured": bool(get_places_key()),
        "source": origins.get("source"),
        "message": origins.get("message"),
        "origin_count": len(origins.get("origins", {})),
        "origins": origins.get("origins", {}),
    }
