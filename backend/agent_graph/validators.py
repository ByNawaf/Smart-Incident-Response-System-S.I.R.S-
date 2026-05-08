"""Guardrails for the LangGraph agent workflow."""

from __future__ import annotations

import re
from typing import Any


def _find_agent(agent_responses: list[dict[str, Any]], name: str) -> dict[str, Any]:
    return next((a for a in agent_responses if a.get("agent_name") == name), {})


def validate_emergency_result(emergency_result: dict[str, Any]) -> dict[str, Any]:
    findings = emergency_result.get("findings", {}) or {}
    fleet = findings.get("dispatched_fleet", []) or []
    units = findings.get("units_dispatched", []) or []
    total_units = findings.get("total_units", len(fleet))

    errors: list[str] = []
    if int(total_units or 0) != len(fleet):
        errors.append(f"total_units mismatch: {total_units} != dispatched_fleet length {len(fleet)}")
        findings["total_units"] = len(fleet)
    if sum(int(u.get("count", 0)) for u in units) not in {0, len(fleet)}:
        errors.append("units_dispatched count did not match dispatched_fleet length")

    # Make recommendation consistent with actual fleet count.
    rec = emergency_result.get("recommendation", "") or ""
    if rec:
        rec = re.sub(r"Dispatch\s+\d+\s+vehicles", f"Dispatch {len(fleet)} vehicles", rec, flags=re.I)
        emergency_result["recommendation"] = rec

    return {
        "valid": not errors,
        "errors": errors,
        "fleet_count": len(fleet),
        "total_units": findings.get("total_units", len(fleet)),
        "source_of_truth": "Emergency Agent dispatched_fleet",
    }


def enforce_coordinator_consistency(
    incident: dict[str, Any],
    agent_responses: list[dict[str, Any]],
    final_decision: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Coordinator cannot change unit count, ETA, route source, or status.

    Emergency Agent is the official source of dispatch truth. This prevents LLM
    or report text from saying 12 units when only 4 were selected.
    """
    emergency = _find_agent(agent_responses, "Emergency Agent")
    findings = emergency.get("findings", {}) or {}
    fleet = findings.get("dispatched_fleet", []) or []
    units = findings.get("units_dispatched", []) or []
    total = int(findings.get("total_units") or len(fleet))
    min_eta = findings.get("min_eta_minutes", None)

    validation = validate_emergency_result(emergency) if emergency else {"valid": False, "errors": ["Emergency Agent output missing"]}
    if emergency:
        # Replace response in-place if validator normalized recommendation.
        for idx, response in enumerate(agent_responses):
            if response.get("agent_name") == "Emergency Agent":
                agent_responses[idx] = emergency
                break

    emergency_plan = final_decision.get("emergency_plan") or {}
    emergency_plan["total_units"] = total
    emergency_plan["units_dispatched"] = units
    emergency_plan["min_eta_minutes"] = min_eta
    final_decision["emergency_plan"] = emergency_plan
    final_decision["agent_responses"] = agent_responses

    # Keep summary aligned with tool-derived count.
    inc_type = incident.get("type", "incident")
    location = incident.get("location_name", "the detected location")
    status = incident.get("status", "Active")
    unit_types = ", ".join(v.get("type", "Unit") for v in fleet[:6]) or "No units"
    final_decision["final_summary"] = (
        f"A {incident.get('severity', 'Medium').lower()}-severity {inc_type} was detected at {location}. "
        f"The LangGraph multi-agent workflow approved {total} incident-specific response units only "
        f"({unit_types}). Minimum ETA is {min_eta if min_eta is not None else 'N/A'} minutes. "
        f"Current incident status: {status}."
    )

    # Make communication log consistent.
    log = final_decision.get("agent_communication_log") or []
    log.append({
        "agent": "LangGraph Validation Node",
        "message": f"Coordinator plan validated against Emergency Agent source of truth: {total} dispatched units.",
        "decision_impact": "Prevents unit-count, ETA, route, and status contradictions in the final plan."
    })
    final_decision["agent_communication_log"] = log

    validation.update({
        "coordinator_consistency_enforced": True,
        "official_unit_count": total,
        "official_min_eta": min_eta,
        "incident_status_source": "incident lifecycle",
    })
    return final_decision, validation
