"""Camera Vision Agent for S.I.R.S.

This agent turns a camera scenario/sensor observation into a structured
incident candidate. It is intentionally explainable: every detection includes
which visual/sensor cues affected the decision. Real media can be added later
without changing the downstream agents because the output contract is stable.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


def _clamp(value: float, low: float = 0.0, high: float = 0.99) -> float:
    return max(low, min(high, value))


def classify_camera_event(camera: dict[str, Any]) -> dict[str, Any]:
    obs = camera.get("sensor_observations", {}) or {}
    detected = set(obs.get("detected_objects", []) or [])
    evidence: list[str] = []
    score = 0.08
    incident_type = "No Incident"

    if obs.get("visible_flames") or "heat_signature" in detected:
        incident_type = "Fire Incident"
        score += 0.58
        evidence.append("Visible flame/heat signature detected in the camera frame")
    elif obs.get("liquid_on_road") or "liquid_spill" in detected:
        incident_type = "Fuel Spill"
        score += 0.54
        evidence.append("Reflective liquid/spill pattern detected on the roadway")
    elif obs.get("impact_pattern") or (obs.get("abnormal_stop") and obs.get("vehicles_involved_estimate", 0) >= 2):
        incident_type = "Traffic Accident"
        score += 0.52
        evidence.append("Multiple vehicles stopped abnormally with collision-like positioning")
    elif obs.get("person_down_detected"):
        incident_type = "Medical Emergency"
        score += 0.50
        evidence.append("Person-down pattern detected near the road edge")
    elif obs.get("blocked_lanes", 0) > 0 or "blocked_lane" in detected:
        incident_type = "Road Blockage"
        score += 0.40
        evidence.append("Lane blockage detected without clear fire/spill/collision evidence")

    blocked = int(obs.get("blocked_lanes", 0) or 0)
    lane_count = max(1, int(obs.get("lane_count", 1) or 1))
    speed_drop = float(obs.get("speed_drop_percent", 0) or 0)
    queue_m = float(obs.get("queue_length_m", 0) or 0)
    people = int(obs.get("people_visible_near_scene", 0) or 0)
    involved = int(obs.get("vehicles_involved_estimate", 0) or 0)

    if blocked:
        evidence.append(f"{blocked} of {lane_count} lanes appear blocked")
        score += min(0.12, blocked / lane_count * 0.12)
    if speed_drop >= 45:
        evidence.append(f"Traffic speed dropped by approximately {int(speed_drop)}% near the camera")
        score += 0.10
    if queue_m >= 300:
        evidence.append(f"Queue length is estimated at {int(queue_m)} meters")
        score += 0.07
    if obs.get("visible_smoke") and not obs.get("visible_flames"):
        evidence.append("Smoke is visible; fire risk requires verification")
        score += 0.08

    incident_detected = incident_type != "No Incident" and score >= 0.45
    if not incident_detected:
        incident_type = "No Incident"
        severity = "Low"
        traffic_density = "Low"
        evidence = evidence or ["No stopped vehicles, smoke, spill, blocked lane, or person-down pattern detected"]
    else:
        severity_index = 1
        severity_index += 1 if blocked >= 1 or speed_drop >= 45 else 0
        severity_index += 1 if people >= 2 or involved >= 2 or queue_m >= 500 else 0
        severity_index += 1 if obs.get("visible_flames") or obs.get("liquid_on_road") or people >= 5 else 0
        severity = {1: "Low", 2: "Medium", 3: "High", 4: "Critical"}.get(min(4, severity_index), "Medium")
        if speed_drop >= 75 or queue_m >= 550:
            traffic_density = "Congested"
        elif speed_drop >= 55 or queue_m >= 350:
            traffic_density = "High"
        elif speed_drop >= 25 or blocked:
            traffic_density = "Moderate"
        else:
            traffic_density = "Low"

    affected_people = 0
    if incident_type in {"Medical Emergency", "Fire Incident"}:
        affected_people = max(1, people)
    elif incident_type == "Traffic Accident":
        affected_people = max(0, min(people, involved * 2))
    elif incident_type == "Fuel Spill":
        affected_people = max(0, people // 2)

    confidence = round(_clamp(score), 2)
    incident_payload = None
    if incident_detected:
        incident_payload = {
            "type": incident_type,
            "severity": severity,
            "location_name": camera.get("location_name") or camera.get("name") or "Detected Camera Location",
            "latitude": float(camera.get("latitude")),
            "longitude": float(camera.get("longitude")),
            "time": datetime.now().strftime("%H:%M"),
            "traffic_density": traffic_density,
            "weather": "Clear",
            "affected_vehicles": max(0, involved),
            "affected_people": affected_people,
            "description": f"Auto-created by Camera Vision Agent from {camera.get('camera_id')}: {camera.get('frame_summary', '')}",
            "source": "Street Camera",
            "camera_id": camera.get("camera_id"),
        }

    return {
        "agent_name": "Camera Vision Agent",
        "status": "Incident Detected" if incident_detected else "No Incident",
        "risk_level": severity,
        "confidence_score": confidence,
        "recommendation": "Create incident and notify specialized agents" if incident_detected else "Continue monitoring; no dispatch required",
        "findings": {
            "camera_id": camera.get("camera_id"),
            "camera_name": camera.get("name"),
            "road_name": camera.get("road_name"),
            "location_name": camera.get("location_name"),
            "coordinates": {"lat": camera.get("latitude"), "lng": camera.get("longitude")},
            "media_url": camera.get("media_url", ""),
            "frame_summary": camera.get("frame_summary", ""),
            "detected_objects": list(detected),
            "incident_detected": incident_detected,
            "incident_type": incident_type,
            "severity": severity,
            "traffic_density": traffic_density,
            "blocked_lanes": blocked,
            "lane_count": lane_count,
            "average_speed_kmh": obs.get("average_speed_kmh"),
            "speed_drop_percent": speed_drop,
            "queue_length_m": queue_m,
            "affected_people_estimate": affected_people,
            "affected_vehicles_estimate": involved,
            "evidence": evidence,
            "analysis_mode": "camera_sensor_fusion_simulation",
            "incident_payload": incident_payload,
        },
    }
