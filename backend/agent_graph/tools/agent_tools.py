"""Tool wrappers used by LangGraph nodes.

These wrappers are intentionally separated from the agent nodes so the graph can
prove that agents use tools rather than returning static text directly.
"""

from __future__ import annotations

from typing import Any

from agents import camera_vision_agent, traffic_agent, emergency_agent, environment_agent, analysis_agent, coordinator_agent


def camera_detection_tool(camera: dict[str, Any]) -> dict[str, Any]:
    return camera_vision_agent.classify_camera_event(camera)


def traffic_analysis_tool(incident: dict[str, Any], city_data: dict[str, Any]) -> dict[str, Any]:
    return traffic_agent.run(incident, city_data)


def emergency_dispatch_tool(incident: dict[str, Any], city_data: dict[str, Any]) -> dict[str, Any]:
    return emergency_agent.run(incident, city_data)


def environmental_assessment_tool(incident: dict[str, Any], city_data: dict[str, Any]) -> dict[str, Any]:
    return environment_agent.run(incident, city_data)


def root_cause_analysis_tool(incident: dict[str, Any], city_data: dict[str, Any]) -> dict[str, Any]:
    return analysis_agent.run(incident, city_data)


def coordinator_tool(incident: dict[str, Any], agent_responses: list[dict[str, Any]], city_data: dict[str, Any]) -> dict[str, Any]:
    return coordinator_agent.run(incident, agent_responses, city_data)
