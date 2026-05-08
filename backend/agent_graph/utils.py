from __future__ import annotations

from datetime import datetime
from typing import Any


def append_trace(state: dict[str, Any], node: str, message: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    trace = list(state.get("graph_trace") or [])
    trace.append({
        "node": node,
        "message": message,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "data": data or {},
    })
    return {"graph_trace": trace}


def append_error(state: dict[str, Any], node: str, error: Exception | str) -> dict[str, Any]:
    errors = list(state.get("errors") or [])
    errors.append(f"{node}: {error}")
    return {"errors": errors}


def compact_agent(agent_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "agent_name": agent_result.get("agent_name"),
        "status": agent_result.get("status"),
        "risk_level": agent_result.get("risk_level"),
        "confidence_score": agent_result.get("confidence_score"),
        "recommendation": agent_result.get("recommendation"),
    }
