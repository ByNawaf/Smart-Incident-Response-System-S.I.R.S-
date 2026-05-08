from __future__ import annotations

from typing import Any

from agent_graph.tools.agent_tools import root_cause_analysis_tool
from agent_graph.decision_layer import apply_analysis_qwen_decision
from agent_graph.utils import append_error, append_trace


def run_analysis_node(state: dict[str, Any]) -> dict[str, Any]:
    try:
        result = root_cause_analysis_tool(state["incident"], state["city_data"])
        result = apply_analysis_qwen_decision(result, state["incident"], state.get("settings", {}))
        responses = list(state.get("agent_responses") or []) + [result]
        update = {"analysis_result": result, "agent_responses": responses}
        update.update(append_trace(state, "Analysis Agent", "Root-cause analysis completed."))
        return update
    except Exception as exc:
        update = append_error(state, "Analysis Agent", exc)
        update.update(append_trace(state, "Analysis Agent", "Analysis node failed."))
        return update
