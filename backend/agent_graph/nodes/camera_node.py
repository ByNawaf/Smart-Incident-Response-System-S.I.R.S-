from __future__ import annotations

from typing import Any

from agent_graph.tools.agent_tools import camera_detection_tool
from agent_graph.decision_layer import apply_camera_qwen_decision
from agent_graph.utils import append_trace, append_error


def run_camera_node(state: dict[str, Any]) -> dict[str, Any]:
    camera = state.get("camera")
    if not camera:
        return append_trace(state, "Camera Vision Agent", "No camera object provided; using existing incident context.")
    try:
        result = state.get("camera_result") or camera_detection_tool(camera)
        result = apply_camera_qwen_decision(result, camera, state.get("settings", {}))
        update = {"camera_result": result}
        update.update(append_trace(state, "Camera Vision Agent", "Camera frame/sensor data analyzed and incident candidate produced.", {"status": result.get("status")}))
        return update
    except Exception as exc:
        update = append_error(state, "Camera Vision Agent", exc)
        update.update(append_trace(state, "Camera Vision Agent", "Camera node failed; workflow continued with existing incident data."))
        return update
