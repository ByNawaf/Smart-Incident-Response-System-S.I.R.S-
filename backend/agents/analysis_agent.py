import random


def run(incident: dict, city_data: dict) -> dict:
    """Analysis Agent: Analyzes root cause, responsibility, and prevention."""
    severity = incident.get("severity", "Medium")
    inc_type = incident.get("type", "Traffic Accident")
    weather = incident.get("weather", "Clear")
    traffic_density = incident.get("traffic_density", "Moderate")
    affected_vehicles = incident.get("affected_vehicles", 0)
    affected_people = incident.get("affected_people", 0)
    description = incident.get("description", "")
    location_name = incident.get("location_name", "Unknown")

    severity_score = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}.get(severity, 2)
    density_score = {"Low": 1, "Moderate": 2, "High": 3, "Congested": 4}.get(traffic_density, 2)

    # Possible causes by incident type
    causes_map = {
        "Traffic Accident": [
            {"cause": "Excessive speeding", "probability": 0.35, "factor": "Human"},
            {"cause": "Sudden lane change without signal", "probability": 0.25, "factor": "Human"},
            {"cause": "Distracted driving (mobile phone)", "probability": 0.20, "factor": "Human"},
            {"cause": "Poor road visibility conditions", "probability": 0.12, "factor": "Environmental"},
            {"cause": "Mechanical failure / brake malfunction", "probability": 0.08, "factor": "Mechanical"}
        ],
        "Fire Incident": [
            {"cause": "Electrical short circuit", "probability": 0.30, "factor": "Mechanical"},
            {"cause": "Fuel leak ignition", "probability": 0.28, "factor": "Mechanical"},
            {"cause": "Arson / deliberate act", "probability": 0.15, "factor": "Human"},
            {"cause": "Extreme heat & dry conditions", "probability": 0.17, "factor": "Environmental"},
            {"cause": "Improper storage of flammables", "probability": 0.10, "factor": "Procedural"}
        ],
        "Road Blockage": [
            {"cause": "Vehicle breakdown in active lane", "probability": 0.40, "factor": "Mechanical"},
            {"cause": "Construction without proper diversion", "probability": 0.25, "factor": "Procedural"},
            {"cause": "Debris or fallen object on road", "probability": 0.20, "factor": "Environmental"},
            {"cause": "Traffic accident spillover", "probability": 0.15, "factor": "Human"}
        ],
        "Fuel Spill": [
            {"cause": "Tanker valve failure during transit", "probability": 0.38, "factor": "Mechanical"},
            {"cause": "Improper coupling of fuel lines", "probability": 0.27, "factor": "Human"},
            {"cause": "Traffic collision with tanker", "probability": 0.22, "factor": "Human"},
            {"cause": "Road surface deterioration", "probability": 0.13, "factor": "Infrastructure"}
        ],
        "Medical Emergency": [
            {"cause": "Pre-existing medical condition", "probability": 0.45, "factor": "Health"},
            {"cause": "Stress or heat-related collapse", "probability": 0.25, "factor": "Environmental"},
            {"cause": "Accident-related injury", "probability": 0.20, "factor": "Human"},
            {"cause": "Unknown / requires investigation", "probability": 0.10, "factor": "Unknown"}
        ]
    }

    causes = causes_map.get(inc_type, causes_map["Traffic Accident"])

    # Adjust probabilities based on weather and density
    if weather in ["Sandstorm", "Fog", "Rain"]:
        for c in causes:
            if c["factor"] == "Environmental":
                c["probability"] = min(c["probability"] * 1.5, 0.9)
    if density_score >= 3:
        for c in causes:
            if c["factor"] == "Human":
                c["probability"] = min(c["probability"] * 1.2, 0.9)

    # Normalize probabilities
    total_prob = sum(c["probability"] for c in causes)
    for c in causes:
        c["probability"] = round(c["probability"] / total_prob, 2)

    # Sort by probability descending
    causes.sort(key=lambda x: x["probability"], reverse=True)
    primary_cause = causes[0]

    # Risk factors
    risk_factors = []
    if density_score >= 3:
        risk_factors.append(f"High traffic density ({traffic_density}) increases collision risk significantly")
    if weather in ["Sandstorm", "Fog", "Rain"]:
        risk_factors.append(f"Adverse weather ({weather}) reduces visibility and road grip")
    if severity_score >= 3:
        risk_factors.append("High severity suggests multiple contributing factors")
    if affected_vehicles > 3:
        risk_factors.append(f"Multiple vehicles involved ({affected_vehicles}) indicates chain reaction scenario")
    if location_name:
        risk_factors.append(f"Location '{location_name}' may have known safety concerns — review historical data")
    risk_factors.append("Peak hours increase exposure to human-factor incidents")

    # Prevention recommendations
    prevention = []
    if primary_cause["factor"] == "Human":
        prevention.append("Install automated speed enforcement cameras at high-risk intersections")
        prevention.append("Launch public awareness campaigns on safe driving and road regulations")
        prevention.append("Implement driver behavior monitoring systems with AI dashcams")
    if primary_cause["factor"] == "Mechanical":
        prevention.append("Mandate quarterly vehicle safety inspections with digital tracking")
        prevention.append("Deploy IoT vehicle health monitoring for commercial fleet operators")
    if primary_cause["factor"] == "Environmental":
        prevention.append("Install dynamic road condition sensors with real-time alerts")
        prevention.append("Implement weather-responsive speed limit adjustment system")
    if primary_cause["factor"] == "Procedural":
        prevention.append("Review and enforce safety protocols for hazmat and heavy transport")
        prevention.append("Improve inter-agency coordination for road safety enforcement")
    prevention.append("Integrate predictive AI analytics to identify high-risk zones before incidents occur")
    prevention.append("Establish a smart city incident learning database for policy improvement")

    # Responsibility estimate (for relevant types)
    responsibility = {}
    if inc_type in ["Traffic Accident", "Fuel Spill"]:
        human_causes = [c for c in causes if c["factor"] == "Human"]
        mech_causes = [c for c in causes if c["factor"] == "Mechanical"]
        env_causes = [c for c in causes if c["factor"] == "Environmental"]
        if human_causes:
            responsibility["Driver/Operator Responsibility"] = f"{int(sum(c['probability'] for c in human_causes) * 100)}%"
        if mech_causes:
            responsibility["Vehicle/Equipment Fault"] = f"{int(sum(c['probability'] for c in mech_causes) * 100)}%"
        if env_causes:
            responsibility["Environmental/External Factors"] = f"{int(sum(c['probability'] for c in env_causes) * 100)}%"

    confidence = round(random.uniform(0.78, 0.93), 2)
    risk_level = "High" if severity_score >= 3 else ("Medium" if severity_score == 2 else "Low")

    return {
        "agent_name": "Analysis Agent",
        "status": "Completed",
        "risk_level": risk_level,
        "confidence_score": confidence,
        "recommendation": f"Primary cause: {primary_cause['cause']} ({int(primary_cause['probability']*100)}% probability). Implement preventive measures targeting {primary_cause['factor']} factors.",
        "findings": {
            "probable_causes": causes[:4],
            "primary_cause": primary_cause["cause"],
            "primary_factor_type": primary_cause["factor"],
            "primary_probability": int(primary_cause["probability"] * 100),
            "responsibility_estimate": responsibility,
            "risk_factors": risk_factors,
            "prevention_recommendations": prevention[:5],
            "severity_assessment": f"{severity} — {severity_score}/4 severity index",
            "contributing_conditions": {
                "weather": weather,
                "traffic_density": traffic_density,
                "affected_scale": f"{affected_vehicles} vehicles, {affected_people} people"
            },
            "summary": f"Primary cause identified as '{primary_cause['cause']}' ({int(primary_cause['probability']*100)}% probability). "
                       f"Key risk factors: {', '.join(risk_factors[:2])}. "
                       f"{len(prevention)} preventive measures recommended."
        }
    }
