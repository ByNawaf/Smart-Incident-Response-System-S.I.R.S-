import random
import math
from datetime import datetime
from services import google_routes_service

CITY_WAYPOINTS = {
    "King Fahd Road - Kingdom Centre": {"lat": 24.7114, "lng": 46.6744},
    "Olaya Street - Al Faisaliah District": {"lat": 24.6906, "lng": 46.6841},
    "King Fahd Medical City Area": {"lat": 24.6868, "lng": 46.7045},
    "King Abdullah Financial District": {"lat": 24.7636, "lng": 46.6406},
    "King Saud University - Main Gate": {"lat": 24.7246, "lng": 46.6239},
    "Northern Ring Road - Exit 5": {"lat": 24.7582, "lng": 46.6711},
    "Eastern Ring Road - Exit 13": {"lat": 24.7422, "lng": 46.7774},
    "Al Malaz District": {"lat": 24.6656, "lng": 46.7331},
    "Al Murabba Historical District": {"lat": 24.6465, "lng": 46.7107},
    "Riyadh Front / Airport Road": {"lat": 24.8342, "lng": 46.7299},
}

# Pre-defined Riyadh rerouting scenarios. Geometry is replaced by OSRM when
# internet routing is available, but these labels keep the traffic agent narrative
# grounded in Riyadh roads.
REROUTING_SCENARIOS = [
    {
        "trigger_roads": ["King Fahd", "Kingdom Centre", "Olaya", "Al Faisaliah"],
        "blocked_road": "King Fahd Road",
        "blocked_from": "Olaya / Al Faisaliah District",
        "blocked_to":   "Kingdom Centre Corridor",
        "blocked_coords": [[24.6906, 46.6841], [24.7036, 46.6836], [24.7114, 46.6744]],
        "alternatives": [
            {"id": 1, "label": "Route A — Olaya Street Parallel Diversion", "from_name": "Al Faisaliah", "to_name": "Kingdom Centre", "via_roads": ["Olaya Street", "Local service roads"], "waypoints": [[24.6906,46.6841],[24.7036,46.6836],[24.7114,46.6744]], "extra_time_min": 7, "congestion": "Low", "distance_km": 3.2, "recommended": True},
            {"id": 2, "label": "Route B — Tahlia / Local Grid Diversion", "from_name": "Olaya", "to_name": "King Fahd Road", "via_roads": ["Tahlia corridor", "local grid"], "waypoints": [[24.6906,46.6841],[24.7004,46.6930],[24.7114,46.6744]], "extra_time_min": 11, "congestion": "Moderate", "distance_km": 4.4, "recommended": False}
        ]
    },
    {
        "trigger_roads": ["King Fahd Medical City", "Makkah", "Medical City"],
        "blocked_road": "Makkah Al Mukarramah Road",
        "blocked_from": "King Faisal Specialist Hospital Area",
        "blocked_to":   "King Fahd Medical City Area",
        "blocked_coords": [[24.6700,46.6740], [24.6868,46.7045]],
        "alternatives": [
            {"id": 1, "label": "Route A — Olaya / Local Medical Corridor", "from_name": "KFSH Area", "to_name": "KFMC Area", "via_roads": ["Olaya Street", "local medical access roads"], "waypoints": [[24.6700,46.6740],[24.6906,46.6841],[24.6868,46.7045]], "extra_time_min": 8, "congestion": "Low", "distance_km": 4.8, "recommended": True},
            {"id": 2, "label": "Route B — Al Malaz Eastern Approach", "from_name": "Central Riyadh", "to_name": "KFMC Area", "via_roads": ["Al Malaz approach", "Makkah Road service lane"], "waypoints": [[24.6656,46.7331],[24.6868,46.7045]], "extra_time_min": 12, "congestion": "Moderate", "distance_km": 5.7, "recommended": False}
        ]
    },
    {
        "trigger_roads": ["KAFD", "Northern Ring", "Exit 5", "North Riyadh"],
        "blocked_road": "Northern Ring Road",
        "blocked_from": "Exit 5 / North Riyadh",
        "blocked_to":   "King Abdullah Financial District",
        "blocked_coords": [[24.7582,46.6711], [24.7636,46.6406]],
        "alternatives": [
            {"id": 1, "label": "Route A — King Fahd Road Southbound Access", "from_name": "Exit 5", "to_name": "KAFD", "via_roads": ["King Fahd Road", "KAFD access roads"], "waypoints": [[24.7582,46.6711],[24.7636,46.6406]], "extra_time_min": 9, "congestion": "Low", "distance_km": 3.6, "recommended": True}
        ]
    },
    {
        "trigger_roads": ["Eastern Ring", "Exit 13", "Riyadh Front", "Airport Road"],
        "blocked_road": "Eastern Ring Road",
        "blocked_from": "Exit 13",
        "blocked_to":   "Airport Road / Riyadh Front",
        "blocked_coords": [[24.7422,46.7774], [24.8342,46.7299]],
        "alternatives": [
            {"id": 1, "label": "Route A — Airport Road North Diversion", "from_name": "Exit 13", "to_name": "Riyadh Front", "via_roads": ["Airport Road", "local access corridor"], "waypoints": [[24.7422,46.7774],[24.8342,46.7299]], "extra_time_min": 13, "congestion": "Moderate", "distance_km": 11.0, "recommended": True}
        ]
    }
]


def calculate_distance(lat1, lng1, lat2, lng2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    return round(R * 2 * math.asin(math.sqrt(a)), 2)


def find_nearest_waypoint(lat, lng):
    best = None
    best_d = float('inf')
    for name, wp in CITY_WAYPOINTS.items():
        d = calculate_distance(lat, lng, wp["lat"], wp["lng"])
        if d < best_d:
            best_d = d
            best = name
    return best


def select_scenario(incident_lat, incident_lng, location_name):
    """Pick the most relevant rerouting scenario based on incident location."""
    loc_lower = location_name.lower()
    for scenario in REROUTING_SCENARIOS:
        for trigger in scenario["trigger_roads"]:
            if trigger.lower() in loc_lower:
                return scenario

    # Fall back: pick scenario whose blocked_from is nearest to incident
    best = REROUTING_SCENARIOS[0]
    best_d = float('inf')
    for scenario in REROUTING_SCENARIOS:
        wp_name = scenario["blocked_from"]
        wp = CITY_WAYPOINTS.get(wp_name)
        if wp:
            d = calculate_distance(incident_lat, incident_lng, wp["lat"], wp["lng"])
            if d < best_d:
                best_d = d
                best = scenario
    return best


def run(incident: dict, city_data: dict) -> dict:
    severity = incident.get("severity", "Medium")
    traffic_density = incident.get("traffic_density", "Moderate")
    inc_type = incident.get("type", "Traffic Accident")
    lat = incident.get("latitude", 24.7136)
    lng = incident.get("longitude", 46.6753)
    weather = incident.get("weather", "Clear")
    affected_vehicles = incident.get("affected_vehicles", 0)
    location_name = incident.get("location_name", "")

    density_score  = {"Low": 1, "Moderate": 2, "High": 3, "Congested": 4}.get(traffic_density, 2)
    severity_score = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}.get(severity, 2)
    weather_penalty = {"Clear": 0, "Cloudy": 0.5, "Rain": 1.5, "Sandstorm": 2, "Fog": 1.5, "Extreme Heat": 0.5}.get(weather, 0)

    congestion_index = (density_score * 0.5 + severity_score * 0.4 + weather_penalty * 0.1) / 4.0
    congestion_level = "High" if congestion_index > 0.65 else ("Medium" if congestion_index > 0.4 else "Low")

    # Select the best rerouting scenario
    scenario = select_scenario(lat, lng, location_name)

    # Adjust alternative times based on conditions
    alternatives = []
    for alt in scenario["alternatives"]:
        a = dict(alt)
        extra = a["extra_time_min"]
        if weather in ["Rain", "Sandstorm", "Fog"]:
            extra = int(extra * 1.3)
        if density_score >= 3:
            extra = int(extra * 1.15)
        a["extra_time_min"] = extra
        alternatives.append(a)

    base_delay = density_score * severity_score * 4
    weather_delay = weather_penalty * 3
    total_delay = int(base_delay + weather_delay + (affected_vehicles * 0.3))
    rec_alt = next((a for a in alternatives if a.get("recommended")), alternatives[0])
    delay_reduction = int(total_delay * 0.65)

    signal_recs = []
    if severity_score >= 3:
        signal_recs.append(f"Activate emergency green corridor on {rec_alt['via_roads'][0]}")
        signal_recs.append("Enable adaptive signal control on diversion routes")
    if traffic_density in ["High", "Congested"]:
        signal_recs.append("Increase signal cycle time by 25% on alternative route intersections")
        signal_recs.append("Activate variable message signs (VMS) on approach roads")
    signal_recs.append("Coordinate traffic signals to prioritise emergency vehicle corridor")

    nearest_wp = find_nearest_waypoint(lat, lng)
    incident_point_coords = [lat, lng]

    # Real traffic geometry: when Google Routes is configured, replace the
    # old mock detour polylines with actual road geometry from OSRM/Google.
    traffic_route_source = "local_fallback"
    route_error = ""
    blocked_coords = scenario["blocked_coords"]
    try:
        # Build an approach corridor that crosses the incident. The middle
        # section is treated as blocked/congested in the simulation.
        approach_origin = (lat - 0.025, lng - 0.030)
        approach_dest   = (lat + 0.025, lng + 0.030)
        google_bundle = google_routes_service.compute_routes(approach_origin, approach_dest, role="traffic", compute_alternatives=True)
        normal_path = (google_bundle.get("normal") or {}).get("path", [])
        if google_bundle.get("source") in {"google_routes", "osrm"} and len(normal_path) >= 6:
            traffic_route_source = google_bundle.get("source", "real_route")
            a = max(1, len(normal_path)//3)
            b = min(len(normal_path)-1, (len(normal_path)*2)//3)
            blocked_coords = normal_path[a:b+1]
            google_alts = []
            for idx, r in enumerate([google_bundle.get("priority")] + (google_bundle.get("alternatives") or [])):
                if not r or not r.get("path") or len(r.get("path")) < 2:
                    continue
                google_alts.append({
                    "id": idx + 1,
                    "label": ("OSRM/OpenStreetMap Route " if google_bundle.get("source") == "osrm" else "Google Route ") + chr(65 + idx) + " — Civilian diversion",
                    "from_name": "Google origin",
                    "to_name": "Google destination",
                    "via_roads": ["Real road-routing corridor"],
                    "waypoints": r["path"],
                    "extra_time_min": max(2, int((r.get("duration_seconds") or 0) / 60)),
                    "congestion": "Low" if idx == 0 else "Moderate",
                    "distance_km": round((r.get("distance_meters") or 0) / 1000, 2),
                    "recommended": idx == 0,
                    "source": google_bundle.get("source", "real_route"),
                })
            if google_alts:
                alternatives = google_alts
                rec_alt = alternatives[0]
                recommended_alt = alternatives[0]
        elif google_bundle.get("error"):
            route_error = google_bundle.get("error", "")
    except Exception as exc:
        route_error = str(exc)

    confidence = round(random.uniform(0.82, 0.96), 2)
    risk_level = "High" if congestion_index > 0.65 else ("Medium" if congestion_index > 0.4 else "Low")

    recommended_alt = next((a for a in alternatives if a.get("recommended")), alternatives[0])

    summary = (
        f"Incident at {location_name} has BLOCKED {scenario['blocked_road']} "
        f"between {scenario['blocked_from']} and {scenario['blocked_to']}. "
        f"Congestion level: {congestion_level}. Current delay: {total_delay} min. "
        f"Recommended diversion: {recommended_alt['label']} "
        f"(FROM {recommended_alt['from_name']} → TO {recommended_alt['to_name']} "
        f"VIA {', '.join(recommended_alt['via_roads'])}). "
        f"Extra travel time: +{recommended_alt['extra_time_min']} min. "
        f"Estimated delay reduction: {delay_reduction} min."
    )

    return {
        "agent_name": "Traffic Agent",
        "status": "Completed",
        "risk_level": risk_level,
        "confidence_score": confidence,
        "recommendation": (
            f"BLOCK {scenario['blocked_road']} from {scenario['blocked_from']} to {scenario['blocked_to']}. "
            f"Divert via {recommended_alt['label']} (+{recommended_alt['extra_time_min']} min). "
            f"Delay reduction: {delay_reduction} min."
        ),
        "findings": {
            "congestion_level": congestion_level,
            "congestion_index": round(congestion_index, 2),
            "blocked_road": scenario["blocked_road"],
            "blocked_from": scenario["blocked_from"],
            "blocked_to": scenario["blocked_to"],
            "blocked_coords": blocked_coords,
            "traffic_route_source": traffic_route_source,
            "traffic_route_error": route_error,
            "incident_point": incident_point_coords,
            "nearest_waypoint": nearest_wp,
            "rerouting_plans": alternatives,
            "recommended_route": recommended_alt,
            "alternative_routes": [
                {
                    "route": a["label"],
                    "from": a["from_name"],
                    "to": a["to_name"],
                    "via": ", ".join(a["via_roads"]),
                    "extra_time_min": a["extra_time_min"],
                    "distance_km": a["distance_km"],
                    "congestion": a["congestion"],
                    "recommended": a.get("recommended", False)
                }
                for a in alternatives
            ],
            "estimated_delay_minutes": total_delay,
            "delay_reduction_minutes": delay_reduction,
            "signal_recommendations": signal_recs,
            "affected_vehicles": affected_vehicles,
            "summary": summary,
            # Legacy compat for map.js
            "alt_route_coords": recommended_alt["waypoints"],
        }
    }
