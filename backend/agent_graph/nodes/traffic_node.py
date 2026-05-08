from __future__ import annotations

from typing import Any

from agent_graph.tools.agent_tools import traffic_analysis_tool
from agent_graph.decision_layer import apply_traffic_qwen_decision
from agent_graph.utils import append_error, append_trace


def run_traffic_node(state: dict[str, Any]) -> dict[str, Any]:
    try:
        result = traffic_analysis_tool(state["incident"], state["city_data"])
        result = apply_traffic_qwen_decision(result, state["incident"], state.get("settings", {}))
        responses = list(state.get("agent_responses") or []) + [result]
        update = {"traffic_result": result, "agent_responses": responses}
        update.update(append_trace(state, "Traffic Agent", "Traffic impact analysis completed through LangGraph node."))
        return update
    except Exception as exc:
        update = append_error(state, "Traffic Agent", exc)
        update.update(append_trace(state, "Traffic Agent", "Traffic node failed."))
        return update
