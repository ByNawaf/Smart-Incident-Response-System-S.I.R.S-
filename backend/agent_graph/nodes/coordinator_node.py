from __future__ import annotations

from typing import Any

from agent_graph.tools.agent_tools import coordinator_tool
from agent_graph.utils import append_error, append_trace
from agent_graph.validators import enforce_coordinator_consistency
from agent_graph.decision_layer import apply_coordinator_qwen_decision


def run_coordinator_node(state: dict[str, Any]) -> dict[str, Any]:
    try:
        incident = state["incident"]
        responses = list(state.get("agent_responses") or [])
        final = coordinator_tool(incident, responses, state["city_data"])
        final, validation = enforce_coordinator_consistency(incident, responses, final)
        final = apply_coordinator_qwen_decision(final, incident, responses, state.get("settings", {}))
        final, validation = enforce_coordinator_consistency(incident, responses, final)
        update = {"final_decision": final, "validation": validation}
        update.update(append_trace(state, "Coordinator Agent", "Final response plan coordinated and validated through Qwen decision layer.", {"unit_count": validation.get("official_unit_count")}))
        return update
    except Exception as exc:
        update = append_error(state, "Coordinator Agent", exc)
        update.update(append_trace(state, "Coordinator Agent", "Coordinator node failed."))
        return update
