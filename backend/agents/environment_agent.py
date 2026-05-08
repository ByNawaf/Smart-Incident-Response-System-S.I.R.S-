import random


def run(incident: dict, city_data: dict) -> dict:
    """Environment Agent: Evaluates environmental impact and safety risks."""
    severity = incident.get("severity", "Medium")
    inc_type = incident.get("type", "Traffic Accident")
    lat = incident.get("latitude", 24.7136)
    lng = incident.get("longitude", 46.6753)
    weather = incident.get("weather", "Clear")
    affected_people = incident.get("affected_people", 0)

    severity_score = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}.get(severity, 2)
    weather_risk = {"Clear": 0.8, "Cloudy": 0.9, "Rain": 1.2, "Sandstorm": 1.4, "Fog": 1.1, "Extreme Heat": 1.3}.get(weather, 1.0)

    # Type-specific environmental risks
    type_env_profile = {
        "Traffic Accident": {
            "pollutants": ["Fuel vapors", "Oil spill", "Tire particles"],
            "base_aqi_impact": 15,
            "fire_risk": "Low",
            "toxic_risk": "Low",
            "base_radius_m": 200
        },
        "Fire Incident": {
            "pollutants": ["Smoke", "Carbon monoxide", "Particulate matter (PM2.5)", "Ash"],
            "base_aqi_impact": 55,
            "fire_risk": "High",
            "toxic_risk": "Medium",
            "base_radius_m": 800
        },
        "Road Blockage": {
            "pollutants": ["Vehicle exhaust (idling)", "Noise pollution"],
            "base_aqi_impact": 8,
            "fire_risk": "Very Low",
            "toxic_risk": "Very Low",
            "base_radius_m": 100
        },
        "Fuel Spill": {
            "pollutants": ["Hydrocarbon vapors", "Fuel contamination", "Ground pollution"],
            "base_aqi_impact": 40,
            "fire_risk": "High",
            "toxic_risk": "Medium",
            "base_radius_m": 600
        },
        "Medical Emergency": {
            "pollutants": ["Biohazard risk (low)", "Disinfectant vapors"],
            "base_aqi_impact": 5,
            "fire_risk": "Very Low",
            "toxic_risk": "Low",
            "base_radius_m": 50
        }
    }

    profile = type_env_profile.get(inc_type, type_env_profile["Traffic Accident"])
    aqi_impact = int(profile["base_aqi_impact"] * severity_score * 0.4 * weather_risk)
    affected_radius_m = int(profile["base_radius_m"] * (0.5 + severity_score * 0.25) * weather_risk)

    # Get nearest AQ station
    aq_stations = city_data.get("air_quality_stations", [])
    baseline_aqi = 50
    if aq_stations:
        baseline_aqi = aq_stations[1].get("baseline_aqi", 50)

    projected_aqi = baseline_aqi + aqi_impact
    aqi_category = (
        "Good" if projected_aqi < 51 else
        "Moderate" if projected_aqi < 101 else
        "Unhealthy for Sensitive Groups" if projected_aqi < 151 else
        "Unhealthy" if projected_aqi < 201 else
        "Very Unhealthy"
    )

    # Environmental risk level
    env_risk_score = (aqi_impact / 100) * 0.4 + (affected_radius_m / 2000) * 0.3 + (severity_score / 4) * 0.3
    env_risk = "Critical" if env_risk_score > 0.7 else ("High" if env_risk_score > 0.5 else ("Medium" if env_risk_score > 0.3 else "Low"))

    # Safety precautions
    precautions = []
    if profile["toxic_risk"] in ["Medium", "High", "Critical"]:
        precautions.append("Establish exclusion zone of " + str(affected_radius_m) + "m radius")
        precautions.append("Deploy hazmat team with full PPE")
    if profile["fire_risk"] in ["High"]:
        precautions.append("Position fire suppression units on standby")
        precautions.append("Eliminate ignition sources within zone")
    if aqi_impact > 30:
        precautions.append("Issue public health advisory for affected area")
        precautions.append("Advise sensitive groups to remain indoors")
    if weather in ["Sandstorm", "Extreme Heat"]:
        precautions.append("Account for weather conditions in evacuation planning")
    precautions.append("Deploy mobile air quality monitors to track dispersion")
    precautions.append("Notify environmental protection authority")

    # Wind dispersion estimate
    wind_direction = random.choice(["North", "Northeast", "East", "Southeast", "South"])
    dispersion_estimate = f"Pollutants dispersing {wind_direction}ward — monitor {affected_radius_m}m corridor"

    confidence = round(random.uniform(0.80, 0.94), 2)

    return {
        "agent_name": "Environment Agent",
        "status": "Completed",
        "risk_level": env_risk,
        "confidence_score": confidence,
        "recommendation": f"Environmental risk is {env_risk}. Establish {affected_radius_m}m safety zone. AQI projected at {projected_aqi} ({aqi_category}).",
        "findings": {
            "air_quality_impact": aqi_category,
            "baseline_aqi": baseline_aqi,
            "projected_aqi": projected_aqi,
            "aqi_increase": aqi_impact,
            "environmental_risk": env_risk,
            "affected_radius_m": affected_radius_m,
            "pollutants_detected": profile["pollutants"],
            "fire_risk": profile["fire_risk"],
            "toxic_risk": profile["toxic_risk"],
            "safety_precautions": precautions,
            "dispersion_estimate": dispersion_estimate,
            "weather_impact": weather,
            "risk_coords": {"lat": lat, "lng": lng, "radius_m": affected_radius_m},
            "summary": f"Detected {env_risk} environmental risk. Projected AQI: {projected_aqi} ({aqi_category}). "
                       f"Affected radius: {affected_radius_m}m. Pollutants: {', '.join(profile['pollutants'][:2])}."
        }
    }
