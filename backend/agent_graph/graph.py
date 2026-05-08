"""LangGraph-powered multi-agent workflow for S.I.R.S.

FastAPI calls this module; LangGraph is the internal agent orchestration engine.
If LangGraph is not installed, a sequential compatibility runner is used so the
application still starts, but the intended engine is LangGraph.
"""

from __future__ import annotations

from typing import Any

from agent_graph.state import IncidentAgentState
from agent_graph.nodes.camera_node import run_camera_node
from agent_graph.nodes.traffic_node import run_traffic_node
from agent_graph.nodes.emergency_node import run_emergency_node
from agent_graph.nodes.environment_node import run_environment_node
from agent_graph.nodes.analysis_node import run_analysis_node
from agent_graph.nodes.coordinator_node import run_coordinator_node
from agent_graph.utils import append_trace

try:  # LangGraph is installed through requirements.txt on the actual project machine.
    from langgraph.graph import END, StateGraph
    LANGGRAPH_AVAILABLE = True
except Exception:  # pragma: no cover - only for environments without dependency installed.
    END = "__end__"
    StateGraph = None
    LANGGRAPH_AVAILABLE = False


def _build_langgraph_app():
    workflow = StateGraph(IncidentAgentState)
    workflow.add_node("camera", run_camera_node)
    workflow.add_node("traffic_agent", run_traffic_node)
    workflow.add_node("emergency_agent", run_emergency_node)
    workflow.add_node("environment_agent", run_environment_node)
    workflow.add_node("analysis_agent", run_analysis_node)
    workflow.add_node("coordinator_agent", run_coordinator_node)

    workflow.set_entry_point("camera")
    workflow.add_edge("camera", "traffic_agent")
    workflow.add_edge("traffic_agent", "emergency_agent")
    workflow.add_edge("emergency_agent", "environment_agent")
    workflow.add_edge("environment_agent", "analysis_agent")
    workflow.add_edge("analysis_agent", "coordinator_agent")
    workflow.add_edge("coordinator_agent", END)
    return workflow.compile()


_GRAPH_APP = _build_langgraph_app() if LANGGRAPH_AVAILABLE else None


def _run_sequential_compat(state: dict[str, Any]) -> dict[str, Any]:
    """Fallback when LangGraph is not installed; keeps local dev from crashing."""
    state.update(append_trace(state, "Agent Graph", "LangGraph package unavailable; running compatibility sequence."))
    for node in [run_camera_node, run_traffic_node, run_emergency_node, run_environment_node, run_analysis_node, run_coordinator_node]:
        update = node(state)
        state.update(update)
    state["graph_engine"] = "sequential_compatibility_runner_missing_langgraph"
    return state


def run_incident_graph(
    *,
    incident: dict[str, Any],
    city_data: dict[str, Any],
    settings: dict[str, Any] | None = None,
    camera: dict[str, Any] | None = None,
    camera_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the stateful multi-agent incident workflow."""
    initial_state: dict[str, Any] = {
        "incident": incident,
        "city_data": city_data,
        "settings": settings or {},
        "camera": camera,
        "camera_result": camera_result,
        "agent_responses": [camera_result] if camera_result else [],
        "graph_trace": [],
        "errors": [],
        "graph_engine": "langgraph" if LANGGRAPH_AVAILABLE else "sequential_compatibility_runner_missing_langgraph",
    }
    if _GRAPH_APP is not None:
        result = _GRAPH_APP.invoke(initial_state)
        result["graph_engine"] = "langgraph"
        return result
    return _run_sequential_compat(initial_state)
