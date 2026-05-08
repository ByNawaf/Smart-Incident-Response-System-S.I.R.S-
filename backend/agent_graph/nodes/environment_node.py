from __future__ import annotations

from typing import Any

from agent_graph.tools.agent_tools import environmental_assessment_tool
from agent_graph.decision_layer import apply_environment_qwen_decision
from agent_graph.utils import append_error, append_trace


def run_environment_node(state: dict[str, Any]) -> dict[str, Any]:
    try:
        result = environmental_assessment_tool(state["incident"], state["city_data"])
        result = apply_environment_qwen_decision(result, state["incident"], state.get("settings", {}))
        responses = list(state.get("agent_responses") or []) + [result]
        update = {"environment_result": result, "agent_responses": responses}
        update.update(append_trace(state, "Environment Agent", "Hazard and safety analysis completed."))
        return update
    except Exception as exc:
        update = append_error(state, "Environment Agent", exc)
        update.update(append_trace(state, "Environment Agent", "Environment node failed."))
        return update
