import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


def load_city_data() -> dict:
    with open(DATA_DIR / "city_data.json", "r") as f:
        return json.load(f)


def load_camera_scenarios() -> dict:
    cameras_file = DATA_DIR / "camera_scenarios.json"
    if cameras_file.exists():
        with open(cameras_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"version": "0", "cameras": []}


def load_incidents() -> list:
    incidents_file = DATA_DIR / "incidents.json"
    if incidents_file.exists():
        with open(incidents_file, "r") as f:
            return json.load(f)
    return []


def save_incidents(incidents: list):
    with open(DATA_DIR / "incidents.json", "w") as f:
        json.dump(incidents, f, indent=2, default=str)


def load_settings() -> dict:
    settings_file = DATA_DIR / "settings.json"
    if settings_file.exists():
        with open(settings_file, "r") as f:
            return json.load(f)
    return {}


def save_settings(settings: dict):
    with open(DATA_DIR / "settings.json", "w") as f:
        json.dump(settings, f, indent=2)


def get_dashboard_stats(incidents: list) -> dict:
    active = [i for i in incidents if i.get("status") in {"Active", "Analyzed"}]
    resolved = [i for i in incidents if i.get("status") == "Resolved"]
    total = len(incidents)

    type_counts = {}
    severity_counts = {"Low": 0, "Medium": 0, "High": 0, "Critical": 0}
    route_provider_counts = {}
    ai_enhanced_count = 0
    eta_values = []
    normal_eta_values = []
    time_saved_values = []
    env_risk_scores = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}
    max_env_score = 1
    max_traffic_score = 1

    traffic_scores = {"Low": 1, "Medium": 2, "Moderate": 2, "High": 3, "Congested": 4, "Critical": 4}

    for inc in incidents:
        t = inc.get("type", "Unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
        s = inc.get("severity", "Medium")
        severity_counts[s] = severity_counts.get(s, 0) + 1
        max_traffic_score = max(max_traffic_score, traffic_scores.get(inc.get("traffic_density", "Moderate"), 2))

        final = inc.get("final_decision") or {}
        if final.get("ai_enhanced"):
            ai_enhanced_count += 1
        eta = final.get("ev_eta_decision") or {}
        if eta.get("priority_eta"):
            eta_values.append(float(eta["priority_eta"]))
        if eta.get("normal_eta"):
            normal_eta_values.append(float(eta["normal_eta"]))
        if eta.get("time_saved"):
            time_saved_values.append(float(eta["time_saved"]))
        provider = eta.get("route_provider")
        if provider:
            route_provider_counts[provider] = route_provider_counts.get(provider, 0) + 1
        env = final.get("environment_plan") or {}
        max_env_score = max(max_env_score, env_risk_scores.get(env.get("risk_level", "Low"), 1))

    if eta_values:
        avg_response = round(sum(eta_values) / len(eta_values), 1)
    elif incidents:
        sv_map = {"Low": 12, "Medium": 8, "High": 6, "Critical": 4}
        times = [sv_map.get(i.get("severity", "Medium"), 8) for i in incidents]
        avg_response = round(sum(times) / len(times), 1)
    else:
        avg_response = 0

    avg_normal_eta = round(sum(normal_eta_values) / len(normal_eta_values), 1) if normal_eta_values else 0
    avg_time_saved = round(sum(time_saved_values) / len(time_saved_values), 1) if time_saved_values else 0
    traffic_impact_level = {1: "Low", 2: "Moderate", 3: "High", 4: "Congested"}.get(max_traffic_score, "Moderate")
    environment_risk_level = {1: "Low", 2: "Medium", 3: "High", 4: "Critical"}.get(max_env_score, "Low")

    latest = incidents[-1] if incidents else {}
    latest_final = latest.get("final_decision") or {}
    latest_eta = latest_final.get("ev_eta_decision") or {}

    return {
        "total_incidents": total,
        "active_incidents": len(active),
        "resolved_incidents": len(resolved),
        "average_response_time_min": avg_response,
        "average_normal_eta_min": avg_normal_eta,
        "average_time_saved_min": avg_time_saved,
        "traffic_impact_level": traffic_impact_level,
        "environment_risk_level": environment_risk_level,
        "incident_types": type_counts,
        "severity_distribution": severity_counts,
        "route_provider_counts": route_provider_counts,
        "ai_enhanced_count": ai_enhanced_count,
        "latest_incident": {
            "id": latest.get("id"),
            "type": latest.get("type"),
            "severity": latest.get("severity"),
            "location_name": latest.get("location_name"),
            "status": latest.get("status"),
            "priority_eta": latest_eta.get("priority_eta"),
            "normal_eta": latest_eta.get("normal_eta"),
            "time_saved": latest_eta.get("time_saved"),
            "route_provider": latest_eta.get("route_provider"),
        } if latest else None,
        "agents_online": 6,
        "system_status": "Operational"
    }
