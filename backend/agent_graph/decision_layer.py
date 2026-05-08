"""Qwen decision layer for S.I.R.S LangGraph agents.

This module turns the old deterministic tool outputs into controlled agentic
outputs. Each agent still uses backend tools first, then Qwen chooses from
validated options. Validators apply the decision back to the operational JSON
without allowing invented units, routes, ETAs, coordinates, or statuses.
"""

from __future__ import annotations

import json
from typing import Any

from agent_graph.llm import qwen_json


def _compact(obj: Any, limit: int = 9000) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)[:limit]


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _risk_rank(level: str) -> int:
    return {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}.get(str(level), 2)


def _risk_name(rank: int) -> str:
    return {1: "Low", 2: "Medium", 3: "High", 4: "Critical"}.get(max(1, min(4, rank)), "Medium")


def _qwen_decide(agent_name: str, goal: str, incident: dict[str, Any], options: dict[str, Any], fallback: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    system = (
        f"You are the {agent_name} in S.I.R.S. Return JSON only. "
        "You are an operational decision layer, not a free text writer. "
        "You MUST choose only from the provided options. Do not invent units, routes, ETAs, coordinates, statuses, agencies, road names, or IDs. "
        "If the options are insufficient, choose the safest valid fallback from the provided options and explain briefly."
    )
    user = (
        f"Goal:\n{goal}\n\n"
        f"Incident context JSON:\n{_compact(incident, 5000)}\n\n"
        f"Allowed options JSON:\n{_compact(options, 12000)}\n\n"
        f"Required fallback JSON shape:\n{_compact(fallback, 4000)}\n\n"
        "Return JSON with the same keys as the fallback plus reasoning_summary. "
        "Every selected ID or action must exist in the Allowed options JSON."
    )
    decision = qwen_json(settings=settings, system=system, user=user, fallback=fallback, timeout_seconds=45, temperature=0.05)
    decision.setdefault("decision_source", "qwen_with_validated_tools" if decision.get("llm_used") else "tool_fallback")
    decision.setdefault("reasoning_summary", fallback.get("reasoning_summary", f"{agent_name} used validated backend tools."))
    return decision


# ─────────────────────────────────────────────────────────────────────────────
# Camera Vision Agent
# ─────────────────────────────────────────────────────────────────────────────

def apply_camera_qwen_decision(camera_result: dict[str, Any], camera: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    findings = camera_result.get("findings", {}) or {}
    obs = camera.get("sensor_observations", {}) or {}
    allowed_types = ["No Incident", "Traffic Accident", "Fire Incident", "Fuel Spill", "Road Blockage", "Medical Emergency"]
    allowed_severities = ["Low", "Medium", "High", "Critical"]
    fallback = {
        "incident_detected": bool(findings.get("incident_detected")),
        "incident_type": findings.get("incident_type", "No Incident"),
        "severity": findings.get("severity", "Low"),
        "traffic_density": findings.get("traffic_density", "Low"),
        "confidence_score": camera_result.get("confidence_score", 0.5),
        "evidence": findings.get("evidence", []),
        "reasoning_summary": "Camera sensor-fusion tool output accepted as the safest detection result.",
    }
    decision = _qwen_decide(
        "Camera Vision Agent",
        "Classify the camera event and decide whether an incident should be created.",
        {"camera_id": camera.get("camera_id"), "frame_summary": camera.get("frame_summary"), "sensor_observations": obs},
        {
            "allowed_incident_types": allowed_types,
            "allowed_severities": allowed_severities,
            "allowed_traffic_density": ["Low", "Moderate", "High", "Congested"],
            "tool_detection": fallback,
        },
        fallback,
        settings,
    )

    incident_type = decision.get("incident_type") if decision.get("incident_type") in allowed_types else fallback["incident_type"]
    severity = decision.get("severity") if decision.get("severity") in allowed_severities else fallback["severity"]
    incident_detected = bool(decision.get("incident_detected")) and incident_type != "No Incident"
    traffic_density = decision.get("traffic_density") if decision.get("traffic_density") in ["Low", "Moderate", "High", "Congested"] else fallback["traffic_density"]
    evidence = [e for e in _as_list(decision.get("evidence")) if isinstance(e, str)] or fallback.get("evidence", [])

    findings["incident_detected"] = incident_detected
    findings["incident_type"] = incident_type if incident_detected else "No Incident"
    findings["severity"] = severity if incident_detected else "Low"
    findings["traffic_density"] = traffic_density if incident_detected else "Low"
    findings["evidence"] = evidence[:8]
    findings["qwen_detection_decision"] = decision
    findings["decision_source"] = decision.get("decision_source")

    camera_result["status"] = "Incident Detected" if incident_detected else "No Incident"
    camera_result["risk_level"] = findings["severity"]
    try:
        camera_result["confidence_score"] = round(float(decision.get("confidence_score", camera_result.get("confidence_score", 0.5))), 2)
    except Exception:
        pass
    camera_result["recommendation"] = "Create incident and notify specialized agents" if incident_detected else "Continue monitoring; no dispatch required"

    payload = findings.get("incident_payload") or {}
    if incident_detected and payload:
        payload["type"] = findings["incident_type"]
        payload["severity"] = findings["severity"]
        payload["traffic_density"] = findings["traffic_density"]
        payload["description"] = f"Auto-created by Camera Vision Agent from {camera.get('camera_id')}: {decision.get('reasoning_summary', camera.get('frame_summary', ''))}"
        findings["incident_payload"] = payload
    elif not incident_detected:
        findings["incident_payload"] = None

    camera_result.setdefault("agent_runtime", {})
    camera_result["agent_runtime"].update({
        "engine": "langgraph/qwen_decision_layer",
        "goal": "Detect whether camera media/sensor data indicates a real incident.",
        "tools_used": ["camera_sensor_fusion_tool", "qwen_detection_decision", "detection_validator"],
        "llm_used": decision.get("llm_used", False),
        "decision_source": decision.get("decision_source"),
        "reasoning_summary": decision.get("reasoning_summary"),
    })
    return camera_result


# ─────────────────────────────────────────────────────────────────────────────
# Traffic Agent
# ─────────────────────────────────────────────────────────────────────────────

def apply_traffic_qwen_decision(result: dict[str, Any], incident: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    findings = result.get("findings", {}) or {}
    routes = findings.get("rerouting_plans", []) or []
    signal_actions = findings.get("signal_recommendations", []) or []
    route_ids = [r.get("id") for r in routes]
    fallback_route = findings.get("recommended_route", {}) or (routes[0] if routes else {})
    fallback = {
        "selected_route_id": fallback_route.get("id"),
        "closure_action": "partial_lane_closure" if _risk_rank(result.get("risk_level", "Medium")) <= 2 else "full_incident_lane_closure",
        "selected_signal_actions": signal_actions[:3],
        "public_advisory_required": result.get("risk_level") in {"High", "Critical"},
        "reasoning_summary": "Traffic tool route and signal actions accepted after road impact analysis.",
    }
    decision = _qwen_decide(
        "Traffic Agent",
        "Select the safest road-control action, diversion route, and signal actions for this incident.",
        incident,
        {
            "allowed_route_ids": route_ids,
            "routes": routes,
            "allowed_closure_actions": ["monitor_only", "shoulder_control", "partial_lane_closure", "full_incident_lane_closure", "full_road_closure"],
            "allowed_signal_actions": signal_actions,
            "tool_output_summary": findings.get("summary"),
        },
        fallback,
        settings,
    )

    selected_id = decision.get("selected_route_id") if decision.get("selected_route_id") in route_ids else fallback.get("selected_route_id")
    selected_route = next((r for r in routes if r.get("id") == selected_id), fallback_route)
    selected_signals = [a for a in _as_list(decision.get("selected_signal_actions")) if a in signal_actions] or fallback.get("selected_signal_actions", [])
    closure_action = decision.get("closure_action") if decision.get("closure_action") in ["monitor_only", "shoulder_control", "partial_lane_closure", "full_incident_lane_closure", "full_road_closure"] else fallback["closure_action"]

    findings["recommended_route"] = selected_route
    for r in routes:
        r["recommended"] = r.get("id") == selected_id
    findings["rerouting_plans"] = routes
    findings["signal_recommendations"] = selected_signals
    findings["closure_action"] = closure_action
    findings["qwen_traffic_decision"] = decision
    findings["decision_source"] = decision.get("decision_source")
    findings["summary"] = (
        f"Traffic Agent selected {closure_action.replace('_', ' ')} and diversion '{selected_route.get('label', 'N/A')}'. "
        f"Signal actions: {len(selected_signals)}. {decision.get('reasoning_summary', '')}"
    )
    result["recommendation"] = (
        f"{closure_action.replace('_', ' ').title()} on {findings.get('blocked_road', 'affected road')}; "
        f"divert via {selected_route.get('label', 'selected route')} (+{selected_route.get('extra_time_min', '?')} min)."
    )
    result.setdefault("agent_runtime", {})
    result["agent_runtime"].update({
        "engine": "langgraph/qwen_decision_layer",
        "goal": "Choose traffic control, diversion, and signal actions from validated route options.",
        "tools_used": ["road_impact_tool", "osrm_route_tool", "diversion_option_tool", "qwen_route_decision", "traffic_decision_validator"],
        "llm_used": decision.get("llm_used", False),
        "decision_source": decision.get("decision_source"),
        "reasoning_summary": decision.get("reasoning_summary"),
    })
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Emergency Agent
# ─────────────────────────────────────────────────────────────────────────────

_REQUIRED_UNIT_TYPES = {
    "Traffic Accident": ["Traffic Unit", "Police Car"],
    "Fire Incident": ["Fire Truck", "Civil Defense", "Police Car"],
    "Fuel Spill": ["Fire Truck", "Civil Defense", "Traffic Unit", "Police Car"],
    "Medical Emergency": ["Ambulance"],
    "Road Blockage": ["Traffic Unit", "Road Service"],
}


def _unit_required_types(incident: dict[str, Any]) -> list[str]:
    inc_type = incident.get("type", "Traffic Accident")
    required = list(_REQUIRED_UNIT_TYPES.get(inc_type, ["Traffic Unit"]))
    if int(incident.get("affected_people", 0) or 0) > 0 and "Ambulance" not in required:
        required.append("Ambulance")
    return required


def _regroup_units(fleet: list[dict[str, Any]]) -> list[dict[str, Any]]:
    labels = {"Ambulance": "Ambulance", "Fire Truck": "Fire Truck", "Civil Defense": "Civil Defense", "Police Car": "Police Unit", "Traffic Unit": "Traffic Unit", "Road Service": "Road Service / Tow"}
    grouped: dict[str, dict[str, Any]] = {}
    for v in fleet:
        t = v.get("type", "Unit")
        grouped.setdefault(t, {"unit": labels.get(t, t), "count": 0, "from": v.get("stationName", "Dispatch Station"), "eta_min": v.get("priorityEta", v.get("normalEta", 5)), "roles": []})
        grouped[t]["count"] += 1
        grouped[t]["eta_min"] = round(min(float(grouped[t]["eta_min"]), float(v.get("priorityEta", grouped[t]["eta_min"]))), 1)
        grouped[t]["roles"].append(v.get("label", t))
    return list(grouped.values())


def apply_emergency_qwen_decision(result: dict[str, Any], incident: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    findings = result.get("findings", {}) or {}
    fleet = findings.get("dispatched_fleet", []) or []
    available_ids = [v.get("unitId") for v in fleet if v.get("unitId")]
    required_types = _unit_required_types(incident)
    fallback = {
        "selected_unit_ids": available_ids,
        "staging_policy": "send_required_units_to_scene",
        "rejected_unit_ids": [],
        "reasoning_summary": "Emergency dispatch tool output accepted as the minimum suitable fleet.",
    }
    unit_options = [
        {
            "unitId": v.get("unitId"),
            "type": v.get("type"),
            "role": v.get("role"),
            "label": v.get("label"),
            "priorityEta": v.get("priorityEta"),
            "normalEta": v.get("normalEta"),
            "routeProvider": v.get("routeProvider"),
            "hazardStaged": v.get("hazardStaged", False),
        }
        for v in fleet
    ]
    decision = _qwen_decide(
        "Emergency Agent",
        "Select the minimum effective response units from available candidates. Required incident capabilities must be covered.",
        incident,
        {
            "available_unit_ids": available_ids,
            "candidate_units": unit_options,
            "required_unit_types": required_types,
            "allowed_staging_policies": ["send_required_units_to_scene", "stage_medical_outside_hazard", "stage_perimeter_units_outside_hazard"],
            "important_rule": "Do not add any unit ID not in available_unit_ids. Do not change ETA values.",
        },
        fallback,
        settings,
    )

    selected_ids = [uid for uid in _as_list(decision.get("selected_unit_ids")) if uid in available_ids]
    # Enforce required unit types if present in candidates.
    for req_type in required_types:
        if not any(v.get("unitId") in selected_ids and v.get("type") == req_type for v in fleet):
            req_candidate = next((v for v in fleet if v.get("type") == req_type), None)
            if req_candidate and req_candidate.get("unitId") not in selected_ids:
                selected_ids.append(req_candidate.get("unitId"))
    if not selected_ids:
        selected_ids = available_ids

    selected_fleet = [v for v in fleet if v.get("unitId") in selected_ids]
    rejected = [v.get("unitId") for v in fleet if v.get("unitId") not in selected_ids]
    units_dispatched = _regroup_units(selected_fleet)
    min_eta = min([float(u.get("eta_min", 99)) for u in units_dispatched], default=None)
    selected_vehicle = selected_fleet[0] if selected_fleet else {}

    findings["dispatched_fleet"] = selected_fleet
    findings["fleet_count"] = len(selected_fleet)
    findings["units_dispatched"] = units_dispatched
    findings["total_units"] = len(selected_fleet)
    findings["min_eta_minutes"] = round(min_eta, 1) if min_eta is not None else None
    findings["selected_vehicle"] = selected_vehicle
    findings["rejected_unit_ids"] = rejected
    findings["qwen_emergency_decision"] = decision
    findings["decision_source"] = decision.get("decision_source")
    findings["dispatch_reasoning"] = findings.get("dispatch_reasoning", []) + [decision.get("reasoning_summary", "Qwen validated dispatch plan.")]
    findings["summary"] = (
        f"Qwen-selected validated dispatch: {len(selected_fleet)} units. Required types: {', '.join(required_types)}. "
        f"Min ETA: {findings['min_eta_minutes']} min."
    )

    result["recommendation"] = (
        f"Dispatch {len(selected_fleet)} validated units immediately. "
        f"Primary: {selected_vehicle.get('unitId', 'N/A')} ({selected_vehicle.get('type', 'N/A')}) — "
        f"Priority ETA {selected_vehicle.get('priorityEta', findings['min_eta_minutes'])} min."
    )
    result.setdefault("agent_runtime", {})
    result["agent_runtime"].update({
        "engine": "langgraph/qwen_decision_layer",
        "goal": "Choose the minimum correct emergency units from real candidate fleet and ETAs.",
        "tools_used": ["fleet_capability_tool", "nearest_station_tool", "osrm_eta_tool", "qwen_dispatch_decision", "dispatch_validator"],
        "llm_used": decision.get("llm_used", False),
        "decision_source": decision.get("decision_source"),
        "reasoning_summary": decision.get("reasoning_summary"),
    })
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Environment Agent
# ─────────────────────────────────────────────────────────────────────────────

def apply_environment_qwen_decision(result: dict[str, Any], incident: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    findings = result.get("findings", {}) or {}
    base_radius = int(findings.get("affected_radius_m", 100) or 100)
    base_rank = _risk_rank(findings.get("environmental_risk", result.get("risk_level", "Medium")))
    all_precautions = findings.get("safety_precautions", []) or []
    policies = [
        {"policy_id": "monitor", "risk_level": _risk_name(max(1, base_rank - 1)), "radius_m": max(50, int(base_radius * 0.75)), "description": "monitoring perimeter only"},
        {"policy_id": "standard", "risk_level": _risk_name(base_rank), "radius_m": base_radius, "description": "standard safety perimeter"},
        {"policy_id": "expanded", "risk_level": _risk_name(min(4, base_rank + 1)), "radius_m": int(base_radius * 1.25), "description": "expanded public safety perimeter"},
        {"policy_id": "critical", "risk_level": "Critical", "radius_m": int(base_radius * 1.5), "description": "critical evacuation and exclusion perimeter"},
    ]
    fallback = {
        "selected_policy_id": "standard",
        "selected_precautions": all_precautions[:5],
        "public_advisory_required": findings.get("projected_aqi", 0) >= 101 or base_rank >= 3,
        "reasoning_summary": "Environmental tool risk and safety perimeter accepted.",
    }
    decision = _qwen_decide(
        "Environment Agent",
        "Choose the safest environmental response policy and precautions from validated options.",
        incident,
        {
            "environment_profile": findings,
            "allowed_policy_ids": [p["policy_id"] for p in policies],
            "policy_options": policies,
            "allowed_precautions": all_precautions,
        },
        fallback,
        settings,
    )
    selected_policy = next((p for p in policies if p["policy_id"] == decision.get("selected_policy_id")), policies[1])
    selected_precautions = [p for p in _as_list(decision.get("selected_precautions")) if p in all_precautions] or fallback["selected_precautions"]

    findings["environmental_risk"] = selected_policy["risk_level"]
    findings["affected_radius_m"] = selected_policy["radius_m"]
    if isinstance(findings.get("risk_coords"), dict):
        findings["risk_coords"]["radius_m"] = selected_policy["radius_m"]
    findings["safety_precautions"] = selected_precautions
    findings["selected_environment_policy"] = selected_policy
    findings["public_advisory_required"] = bool(decision.get("public_advisory_required"))
    findings["qwen_environment_decision"] = decision
    findings["decision_source"] = decision.get("decision_source")
    findings["summary"] = (
        f"Environment Agent selected {selected_policy['policy_id']} policy: {selected_policy['radius_m']}m perimeter, "
        f"risk {selected_policy['risk_level']}. {decision.get('reasoning_summary', '')}"
    )
    result["risk_level"] = selected_policy["risk_level"]
    result["recommendation"] = f"Environmental risk is {selected_policy['risk_level']}. Establish {selected_policy['radius_m']}m safety zone."
    result.setdefault("agent_runtime", {})
    result["agent_runtime"].update({
        "engine": "langgraph/qwen_decision_layer",
        "goal": "Select environmental safety policy, perimeter, and precautions from validated risk options.",
        "tools_used": ["hazard_profile_tool", "aqi_projection_tool", "safety_perimeter_options", "qwen_environment_decision", "environment_validator"],
        "llm_used": decision.get("llm_used", False),
        "decision_source": decision.get("decision_source"),
        "reasoning_summary": decision.get("reasoning_summary"),
    })
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Analysis Agent
# ─────────────────────────────────────────────────────────────────────────────

def apply_analysis_qwen_decision(result: dict[str, Any], incident: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    findings = result.get("findings", {}) or {}
    causes = findings.get("probable_causes", []) or []
    cause_names = [c.get("cause") for c in causes if c.get("cause")]
    prevention = findings.get("prevention_recommendations", []) or []
    risk_factors = findings.get("risk_factors", []) or []
    fallback = {
        "selected_primary_cause": findings.get("primary_cause") or (cause_names[0] if cause_names else "Unknown"),
        "selected_risk_factors": risk_factors[:3],
        "selected_prevention_actions": prevention[:4],
        "reasoning_summary": "Analysis tool primary cause and prevention recommendations accepted.",
    }
    decision = _qwen_decide(
        "Analysis Agent",
        "Choose the most plausible root cause and prevention recommendations from the validated candidate lists.",
        incident,
        {
            "allowed_causes": causes,
            "allowed_cause_names": cause_names,
            "allowed_risk_factors": risk_factors,
            "allowed_prevention_actions": prevention,
        },
        fallback,
        settings,
    )

    selected_cause_name = decision.get("selected_primary_cause") if decision.get("selected_primary_cause") in cause_names else fallback["selected_primary_cause"]
    selected_cause = next((c for c in causes if c.get("cause") == selected_cause_name), causes[0] if causes else {"cause": "Unknown", "probability": 0, "factor": "Unknown"})
    selected_risk = [r for r in _as_list(decision.get("selected_risk_factors")) if r in risk_factors] or fallback["selected_risk_factors"]
    selected_prev = [p for p in _as_list(decision.get("selected_prevention_actions")) if p in prevention] or fallback["selected_prevention_actions"]

    findings["primary_cause"] = selected_cause.get("cause")
    findings["primary_factor_type"] = selected_cause.get("factor")
    findings["primary_probability"] = int(float(selected_cause.get("probability", 0)) * 100) if selected_cause.get("probability", 0) <= 1 else int(selected_cause.get("probability", 0))
    findings["risk_factors"] = selected_risk
    findings["prevention_recommendations"] = selected_prev
    findings["qwen_analysis_decision"] = decision
    findings["decision_source"] = decision.get("decision_source")
    findings["summary"] = (
        f"Qwen-selected primary cause: {findings['primary_cause']} ({findings['primary_probability']}%). "
        f"Selected prevention actions: {len(selected_prev)}."
    )
    result["recommendation"] = f"Primary cause: {findings['primary_cause']} ({findings['primary_probability']}%). Implement selected prevention actions."
    result.setdefault("agent_runtime", {})
    result["agent_runtime"].update({
        "engine": "langgraph/qwen_decision_layer",
        "goal": "Select root cause and prevention actions from validated candidate evidence.",
        "tools_used": ["root_cause_candidate_tool", "risk_factor_tool", "prevention_option_tool", "qwen_root_cause_decision", "analysis_validator"],
        "llm_used": decision.get("llm_used", False),
        "decision_source": decision.get("decision_source"),
        "reasoning_summary": decision.get("reasoning_summary"),
    })
    return result

# ─────────────────────────────────────────────────────────────────────────────
# Coordinator Agent
# ─────────────────────────────────────────────────────────────────────────────

def apply_coordinator_qwen_decision(final: dict[str, Any], incident: dict[str, Any], agent_responses: list[dict[str, Any]], settings: dict[str, Any]) -> dict[str, Any]:
    immediate_actions = final.get("immediate_actions", []) or []
    secondary_actions = final.get("secondary_actions", []) or []
    action_options = [{"id": f"A{idx+1}", "text": text, "type": "immediate"} for idx, text in enumerate(immediate_actions)]
    action_options += [{"id": f"S{idx+1}", "text": text, "type": "secondary"} for idx, text in enumerate(secondary_actions)]
    fallback = {
        "approved_action_ids": [a["id"] for a in action_options if a["type"] == "immediate"][:6],
        "deferred_action_ids": [a["id"] for a in action_options if a["type"] == "secondary"][:4],
        "conflicts_detected": [],
        "coordination_priority": "life_safety_then_traffic_then_environment",
        "reasoning_summary": "Coordinator approved validated agent outputs with life-safety priority.",
    }
    decision = _qwen_decide(
        "Coordinator Agent",
        "Approve one final response plan by selecting actions from validated agent outputs and identifying conflicts without changing operational values.",
        incident,
        {
            "agent_outputs": agent_responses,
            "current_final_decision": final,
            "allowed_action_ids": [a["id"] for a in action_options],
            "action_options": action_options,
            "allowed_priorities": ["life_safety_then_traffic_then_environment", "fire_suppression_then_perimeter_then_traffic", "medical_access_then_scene_security", "hazard_isolation_then_dispatch_then_diversion"],
            "important_rule": "Do not change fleet count, ETA, route source, status, coordinates, or dispatched unit IDs.",
        },
        fallback,
        settings,
    )
    approved_ids = [x for x in _as_list(decision.get("approved_action_ids")) if x in [a["id"] for a in action_options]] or fallback["approved_action_ids"]
    deferred_ids = [x for x in _as_list(decision.get("deferred_action_ids")) if x in [a["id"] for a in action_options]]
    approved = [a["text"] for a in action_options if a["id"] in approved_ids]
    deferred = [a["text"] for a in action_options if a["id"] in deferred_ids]
    if approved:
        final["immediate_actions"] = approved
    if deferred:
        final["secondary_actions"] = deferred
    final["coordination_priority"] = decision.get("coordination_priority", fallback["coordination_priority"])
    final["conflicts_detected"] = _as_list(decision.get("conflicts_detected"))
    final["qwen_coordinator_decision"] = decision
    final.setdefault("agent_runtime", {})
    final["agent_runtime"].update({
        "engine": "langgraph/qwen_decision_layer",
        "goal": "Approve final coordinated response plan from validated agent outputs.",
        "tools_used": ["agent_output_aggregator", "consistency_validator", "qwen_coordination_decision", "final_plan_guardrails"],
        "llm_used": decision.get("llm_used", False),
        "decision_source": decision.get("decision_source"),
        "reasoning_summary": decision.get("reasoning_summary"),
    })
    return final
