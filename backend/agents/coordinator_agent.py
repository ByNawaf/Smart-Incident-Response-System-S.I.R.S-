import random
from datetime import datetime


def run(incident: dict, agent_responses: list, city_data: dict) -> dict:
    """Coordinator Agent: Integrates all agent outputs into a final response plan."""
    severity = incident.get("severity", "Medium")
    inc_type = incident.get("type", "Traffic Accident")
    incident_id = incident.get("id", "INC-000")
    lat = incident.get("latitude", 24.7136)
    lng = incident.get("longitude", 46.6753)
    location_name = incident.get("location_name", "Unknown Location")
    affected_people = incident.get("affected_people", 0)
    affected_vehicles = incident.get("affected_vehicles", 0)

    severity_score = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}.get(severity, 2)

    # Extract each agent's output
    traffic_data = next((r for r in agent_responses if r["agent_name"] == "Traffic Agent"), {})
    emergency_data = next((r for r in agent_responses if r["agent_name"] == "Emergency Agent"), {})
    env_data = next((r for r in agent_responses if r["agent_name"] == "Environment Agent"), {})
    analysis_data = next((r for r in agent_responses if r["agent_name"] == "Analysis Agent"), {})
    camera_data = next((r for r in agent_responses if r["agent_name"] == "Camera Vision Agent"), {})

    traffic_findings = traffic_data.get("findings", {})
    emergency_findings = emergency_data.get("findings", {})
    env_findings = env_data.get("findings", {})
    analysis_findings = analysis_data.get("findings", {})
    camera_findings = camera_data.get("findings", {})

    # ── Priority classification ──────────────────────────────────────────────
    priority_labels = {
        1: "P4 — Standard Response",
        2: "P3 — Elevated Response",
        3: "P2 — High-Priority Emergency",
        4: "P1 — Critical Emergency / Full Mobilisation"
    }
    priority_level = priority_labels.get(severity_score, "P3 — Elevated Response")

    # ── Conflict resolution ──────────────────────────────────────────────────
    conflicts_resolved = []
    traffic_risk = traffic_data.get("risk_level", "Medium")
    env_risk = env_data.get("risk_level", "Low")

    if traffic_risk == "High" and env_risk in ["High", "Critical"]:
        conflicts_resolved.append(
            "Traffic rerouting route adjusted to avoid environmental risk zone — "
            "alternative corridor selected to minimize public exposure to pollutants."
        )
    if severity_score >= 3 and traffic_findings.get("congestion_level") == "High":
        conflicts_resolved.append(
            "Emergency vehicle corridor prioritised over general traffic rerouting — "
            "signal preemption activated on primary dispatch route."
        )

    # ── Emergency Plan ───────────────────────────────────────────────────────
    units = emergency_findings.get("units_dispatched", [])
    min_eta = emergency_findings.get("min_eta_minutes", 8)
    min_eta_int = int(round(float(min_eta or 8)))

    # ── Extract EV ETA optimization data ─────────────────────────────────────
    sv = emergency_findings.get("selected_vehicle", {})
    ev_normal_eta  = sv.get("normalEta", emergency_findings.get("ev_normal_eta", 0))
    ev_priority_eta = sv.get("priorityEta", emergency_findings.get("ev_priority_eta", 0))
    ev_time_saved  = sv.get("timeSaved", emergency_findings.get("ev_time_saved", 0))
    ev_unit_id     = sv.get("unitId", "N/A")
    ev_type        = sv.get("type", "Ambulance")
    ev_route_status = sv.get("routeStatus", "Priority Route")
    ev_congestion  = sv.get("currentCongestionLevel", emergency_findings.get("ev_congestion_level", "Medium"))
    ev_clearance_approved = emergency_findings.get("ev_clearance_requested", severity_score >= 3)
    ev_intersections = sv.get("priorityIntersections", emergency_findings.get("ev_priority_intersections", []))

    patient_transfer_plan = emergency_findings.get("patient_transfer_plan")
    destination_hospital = emergency_findings.get("destination_hospital") or emergency_findings.get("closest_hospital") or {}
    ambulance_origin = emergency_findings.get("closest_ambulance_origin") or {}

    emergency_plan = {
        "priority": emergency_findings.get("priority_level", priority_level),
        "units_dispatched": units,
        "total_units": emergency_findings.get("total_units", len(units)),
        "first_responder_eta_min": min_eta,
        "hospital": destination_hospital.get("name", "N/A"),
        "patient_transfer_plan": patient_transfer_plan,
        "ambulance_origin": ambulance_origin.get("name", "N/A"),
        "dispatch_reasoning": emergency_findings.get("dispatch_reasoning", []),
        "command": f"Establish unified Incident Command Post near {location_name}",
        "medical_triage": affected_people > 0,
        "scene_security_perimeter_m": int(env_findings.get("affected_radius_m", 200) * 1.2),
        # EV ETA fields
        "ev_unit": f"{ev_type} {ev_unit_id}",
        "ev_normal_eta": ev_normal_eta,
        "ev_priority_eta": ev_priority_eta,
        "ev_time_saved": ev_time_saved,
        "ev_route_status": ev_route_status,
        "ev_clearance_approved": ev_clearance_approved,
    }

    # ── Traffic Plan ─────────────────────────────────────────────────────────
    alt_routes = traffic_findings.get("alternative_routes", [])
    traffic_plan = {
        "congestion_level": traffic_findings.get("congestion_level", "Medium"),
        "affected_roads": traffic_findings.get("affected_roads", []),
        "recommended_diversions": alt_routes[:3],
        "estimated_delay_min": traffic_findings.get("estimated_delay_minutes", 20),
        "delay_reduction_min": traffic_findings.get("delay_reduction_minutes", 12),
        "signal_actions": traffic_findings.get("signal_recommendations", [])[:3],
        "vms_message": f"INCIDENT AHEAD — {inc_type.upper()} — USE DIVERSION ROUTE",
        "traffic_status": "Road closure recommended" if severity_score >= 3 else "Lane restriction advised"
    }

    # ── Environment Plan ─────────────────────────────────────────────────────
    environment_plan = {
        "risk_level": env_findings.get("environmental_risk", "Medium"),
        "projected_aqi": env_findings.get("projected_aqi", 75),
        "aqi_category": env_findings.get("air_quality_impact", "Moderate"),
        "exclusion_zone_m": env_findings.get("affected_radius_m", 300),
        "pollutants": env_findings.get("pollutants_detected", []),
        "safety_actions": env_findings.get("safety_precautions", [])[:3],
        "public_advisory": env_findings.get("projected_aqi", 75) > 100,
        "dispersion": env_findings.get("dispersion_estimate", "Monitor surrounding area")
    }

    # ── Cause Analysis ───────────────────────────────────────────────────────
    cause_analysis = {
        "primary_cause": analysis_findings.get("primary_cause", "Under investigation"),
        "cause_probability": f"{analysis_findings.get('primary_probability', 35)}%",
        "factor_type": analysis_findings.get("primary_factor_type", "Human"),
        "all_causes": analysis_findings.get("probable_causes", []),
        "risk_factors": analysis_findings.get("risk_factors", [])[:3],
        "responsibility": analysis_findings.get("responsibility_estimate", {})
    }

    # ── Prevention Recommendations ────────────────────────────────────────────
    prevention = analysis_findings.get("prevention_recommendations", [
        "Deploy AI-powered incident prediction system at high-risk corridors",
        "Enhance inter-agency real-time data sharing protocols",
        "Upgrade road infrastructure with IoT sensor network",
        "Implement mandatory safety training for commercial vehicle operators"
    ])

    # ── Prioritised Action List ───────────────────────────────────────────────
    immediate_actions = [
        f"🚨 IMMEDIATE: {emergency_plan['command']}",
        f"🚑 Dispatch {emergency_plan['total_units']} emergency units — ETA {min_eta} min",
    ]
    if ev_clearance_approved and ev_normal_eta and ev_priority_eta:
        immediate_actions.append(
            f"⚡ Emergency corridor approved — {ev_type} {ev_unit_id} ETA reduced from "
            f"{ev_normal_eta} min → {ev_priority_eta} min (saves {ev_time_saved} min)"
        )
    if traffic_plan["congestion_level"] in ["High", "Medium"]:
        immediate_actions.append(f"🚦 Activate traffic diversions on affected roads — signal priority enabled")
    if ev_intersections:
        int_names = " & ".join([i.get("name", "") for i in ev_intersections[:2]])
        immediate_actions.append(f"🚦 Signal preemption at: {int_names}")
    if environment_plan["risk_level"] in ["High", "Critical"]:
        immediate_actions.append(f"⚠️ Establish {environment_plan['exclusion_zone_m']}m safety perimeter around incident site")
    if environment_plan["public_advisory"]:
        immediate_actions.append("📢 Issue public health advisory — AQI elevated above safe threshold")
    immediate_actions.append("📡 Activate Riyadh Incident Command Centre — coordinate all agencies")

    secondary_actions = [
        "Conduct scene investigation and evidence preservation",
        "Brief media and public via official channels",
        "Document all response actions for post-incident review",
        "Initiate insurance and legal notification procedures if applicable"
    ]

    # ── Response Timeline ─────────────────────────────────────────────────────
    now = datetime.now()
    env_timeline_event = {
        "Fuel Spill": "Environment Agent deployed — flammable spill perimeter and ignition risk calculated",
        "Fire Incident": "Environment Agent deployed — smoke dispersion and heat exposure zone calculated",
        "Traffic Accident": "Environment Agent deployed — roadway safety and air-quality impact assessed",
        "Road Blockage": "Environment Agent deployed — public access and congestion exposure assessed",
        "Medical Emergency": "Environment Agent deployed — safe access zone and crowd-control risk assessed",
    }.get(inc_type, "Environment Agent deployed — site safety zone calculated")

    response_timeline = [
        {"time": "T+00:00", "event": f"Incident detected by Camera Vision Agent from {camera_findings.get('camera_id', incident.get('camera_id', 'street camera'))}", "actor": "Camera Vision Agent", "status": "done"},
        {"time": "T+00:30", "event": "Traffic Agent deployed — road analysis & congestion mapping initiated", "actor": "Traffic Agent", "status": "done"},
        {"time": "T+01:00", "event": f"Emergency Agent deployed — {ev_type} {ev_unit_id} selected, congestion detected ({ev_congestion})", "actor": "Emergency Agent", "status": "done"},
        {"time": "T+01:15", "event": f"Emergency Agent: Normal ETA {ev_normal_eta} min detected — requesting corridor from Traffic Agent", "actor": "Emergency Agent", "status": "done"},
        {"time": "T+01:30", "event": f"Traffic Agent: Emergency corridor identified — signal priority at {len(ev_intersections)} intersections", "actor": "Traffic Agent", "status": "done"},
        {"time": "T+02:00", "event": env_timeline_event, "actor": "Environment Agent", "status": "done"},
        {"time": "T+02:15", "event": "Analysis Agent deployed — root cause analysis complete", "actor": "Analysis Agent", "status": "done"},
        {"time": "T+02:30", "event": f"Coordinator Agent — emergency corridor APPROVED. ETA reduced {ev_normal_eta}→{ev_priority_eta} min (saves {ev_time_saved} min)", "actor": "Coordinator Agent", "status": "done"},
        {"time": f"T+{min_eta_int:02d}:00", "event": "First responders arrive on scene from nearest station", "actor": "Emergency Services", "status": "pending"},
        {"time": f"T+{int(round(float(ev_priority_eta))):02d}:00" if ev_priority_eta else f"T+{min_eta_int+5:02d}:00", "event": f"{ev_type} {ev_unit_id} arrives via priority corridor — ETA optimised", "actor": "Emergency Services", "status": "pending"},
        {"time": f"T+{min_eta_int + 5:02d}:00", "event": "Traffic diversions fully operational — signal priority active", "actor": "Traffic Control", "status": "pending"},
        {"time": f"T+{min_eta_int + 15:02d}:00", "event": "Scene secured and under control", "actor": "All Agencies", "status": "pending"}
    ]

    # ── Overall Confidence ────────────────────────────────────────────────────
    agent_confidences = [
        traffic_data.get("confidence_score", 0.88),
        emergency_data.get("confidence_score", 0.91),
        env_data.get("confidence_score", 0.85),
        analysis_data.get("confidence_score", 0.87)
    ]
    overall_confidence = round(sum(agent_confidences) / len(agent_confidences) * random.uniform(0.97, 1.02), 2)
    overall_confidence = min(overall_confidence, 0.99)

    # ── Final Summary ─────────────────────────────────────────────────────────
    ev_corridor_summary = (
        f"{ev_type} {ev_unit_id} selected for primary response. "
        f"Normal ETA was {ev_normal_eta} minutes due to {ev_congestion} congestion. "
        f"By activating emergency corridor and traffic signal priority, ETA is reduced to {ev_priority_eta} minutes — saving {ev_time_saved} minutes. "
        f"Emergency corridor status: {ev_route_status}."
    ) if ev_normal_eta and ev_priority_eta else ""

    final_summary = (
        f"A {severity.lower()}-severity {inc_type} has occurred at {location_name}, "
        f"affecting {affected_vehicles} vehicles and {affected_people} people. "
        f"The Multi-Agent System has completed analysis in under 3 minutes. "
        f"{emergency_plan['total_units']} incident-specific emergency units are being dispatched with a station ETA of {min_eta} minutes. "
        f"{('If patient transport is required, the destination hospital is ' + emergency_plan['hospital'] + '. ') if emergency_plan.get('hospital') != 'N/A' and affected_people > 0 else ''}"
        f"{ev_corridor_summary} "
        f"Traffic is being rerouted, reducing civilian delays by {traffic_plan.get('delay_reduction_min', 12)} minutes. "
        f"Environmental risk is classified as {environment_plan['risk_level']} with a {environment_plan['exclusion_zone_m']}m safety zone. "
        f"Primary incident cause: {cause_analysis['primary_cause']} ({cause_analysis['cause_probability']} probability). "
        f"All {len(immediate_actions)} immediate actions are in progress. System confidence: {int(overall_confidence * 100)}%."
    )


    # ── Deterministic Agent Communication Log ────────────────────────────────
    route_provider = sv.get("routeProvider", "fallback")
    agent_communication_log = [
        {
            "agent": "Camera Vision Agent",
            "message": f"Camera {camera_findings.get('camera_id', incident.get('camera_id', 'N/A'))} detected {inc_type} at {location_name} using visual/sensor cues: {', '.join((camera_findings.get('evidence') or [])[:2]) or 'camera evidence attached'}.",
            "decision_impact": "Coordinator started the response automatically from camera evidence instead of waiting for manual reporting."
        },
        {
            "agent": "Traffic Agent",
            "message": f"Detected {traffic_plan['congestion_level']} congestion around {location_name}; proposed diversion routes and signal priority for emergency access.",
            "decision_impact": "Coordinator prioritised emergency corridor while keeping civilian diversion active."
        },
        {
            "agent": "Emergency Agent",
            "message": f"Selected only suitable responders for {inc_type}. Primary unit: {ev_type} {ev_unit_id}; normal ETA {ev_normal_eta} min and priority ETA {ev_priority_eta} min using {route_provider} routing.",
            "decision_impact": "Coordinator approved route clearance because it saves critical response time without dispatching unrelated agencies."
        },
        {
            "agent": "Environment Agent",
            "message": f"Risk level is {environment_plan['risk_level']} with a recommended {environment_plan['exclusion_zone_m']}m safety zone.",
            "decision_impact": "Coordinator kept staging and public access outside the safety perimeter."
        },
        {
            "agent": "Analysis Agent",
            "message": f"Most probable cause: {cause_analysis['primary_cause']} with {cause_analysis['cause_probability']} confidence from available indicators.",
            "decision_impact": "Coordinator added prevention recommendations to the final report."
        },
        {
            "agent": "Coordinator Agent",
            "message": "Resolved speed-versus-safety tradeoff by approving the emergency corridor, public diversion, incident-specific safety perimeter, and hospital transfer destination when ambulance support is required.",
            "decision_impact": "Final plan is operational, explainable, and ready for command-centre display."
        },
    ]

    conflict_resolution = []
    if ev_normal_eta and ev_priority_eta:
        conflict_resolution.append({
            "conflict": "Fastest emergency access vs. congested civilian traffic",
            "resolution": "Activate emergency corridor and adaptive signal priority on the selected route",
            "reason": f"This reduces ETA by {ev_time_saved} minutes while keeping diversion routes open for civilians."
        })
    if environment_plan["risk_level"] in ["High", "Critical"]:
        conflict_resolution.append({
            "conflict": "Closest approach route vs. hazardous safety perimeter",
            "resolution": "Stage support units outside the perimeter and keep only required units on the cleared corridor",
            "reason": f"Environment Agent recommended a {environment_plan['exclusion_zone_m']}m safety zone."
        })
    if not conflict_resolution:
        conflict_resolution.append({
            "conflict": "Operational speed vs. public road continuity",
            "resolution": "Use lane restriction and targeted diversion instead of full closure",
            "reason": "Severity does not require a complete area lockdown."
        })

    return {
        "incident_id": incident_id,
        "priority_level": priority_level,
        "emergency_plan": emergency_plan,
        "traffic_plan": traffic_plan,
        "environment_plan": environment_plan,
        "cause_analysis": cause_analysis,
        "prevention_recommendations": prevention[:5],
        "immediate_actions": immediate_actions,
        "secondary_actions": secondary_actions,
        "conflicts_resolved": conflicts_resolved,
        "final_summary": final_summary,
        "confidence_score": overall_confidence,
        "response_timeline": response_timeline,
        "agent_responses": agent_responses,
        "agent_communication_log": agent_communication_log,
        "conflict_resolution": conflict_resolution,
        "generated_at": now.isoformat(),
        # ── EV ETA Decision ─────────────────────────────────────────────────
        "ev_eta_decision": {
            "unit": f"{ev_type} {ev_unit_id}",
            "normal_eta": ev_normal_eta,
            "priority_eta": ev_priority_eta,
            "time_saved": ev_time_saved,
            "congestion_level": ev_congestion,
            "route_status": ev_route_status,
            "route_provider": sv.get("routeProvider", "fallback"),
            "corridor_approved": ev_clearance_approved,
            "signal_priority_intersections": len(ev_intersections),
            "summary": ev_corridor_summary if ev_normal_eta else "ETA optimization data unavailable",
            "patient_destination_hospital": emergency_plan.get("hospital"),
            "ambulance_origin": emergency_plan.get("ambulance_origin"),
        }
    }
