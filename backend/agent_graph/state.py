"""Shared state for the S.I.R.S LangGraph incident workflow.

FastAPI remains the API layer. This state object is the internal contract used
by the LangGraph agent engine.
"""

from __future__ import annotations

from typing import Any, TypedDict


class IncidentAgentState(TypedDict, total=False):
    incident: dict[str, Any]
    city_data: dict[str, Any]
    settings: dict[str, Any]
    camera: dict[str, Any] | None
    camera_result: dict[str, Any] | None

    traffic_result: dict[str, Any]
    emergency_result: dict[str, Any]
    environment_result: dict[str, Any]
    analysis_result: dict[str, Any]

    agent_responses: list[dict[str, Any]]
    final_decision: dict[str, Any]
    validation: dict[str, Any]
    report: dict[str, Any] | None

    graph_engine: str
    graph_trace: list[dict[str, Any]]
    errors: list[str]
