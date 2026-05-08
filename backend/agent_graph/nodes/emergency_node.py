from __future__ import annotations

from typing import Any

from agent_graph.tools.agent_tools import emergency_dispatch_tool
from agent_graph.decision_layer import apply_emergency_qwen_decision
from agent_graph.utils import append_error, append_trace
from agent_graph.validators import validate_emergency_result


def run_emergency_node(state: dict[str, Any]) -> dict[str, Any]:
    try:
        result = emergency_dispatch_tool(state["incident"], state["city_data"])
        result = apply_emergency_qwen_decision(result, state["incident"], state.get("settings", {}))
        validation = validate_emergency_result(result)
        result.setdefault("agent_runtime", {})
        result["agent_runtime"]["validation"] = validation
        responses = list(state.get("agent_responses") or []) + [result]
        update = {"emergency_result": result, "agent_responses": responses}
        update.update(append_trace(state, "Emergency Agent", "Dispatch plan generated and validated.", {"fleet_count": validation.get("fleet_count")}))
        return update
    except Exception as exc:
        update = append_error(state, "Emergency Agent", exc)
        update.update(append_trace(state, "Emergency Agent", "Emergency node failed."))
        return update
