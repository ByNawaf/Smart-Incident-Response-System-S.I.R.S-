"""Small Ollama/Qwen helper used by the LangGraph nodes.

The graph never lets Qwen invent operational values. Qwen can provide reasoning
summaries and checks; numeric/operational values remain tool-derived.
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "qwen3:8b"


def ollama_enabled(settings: dict[str, Any] | None = None) -> bool:
    settings = settings or {}
    value = settings.get("ollama_enabled", os.getenv("OLLAMA_ENABLED", "true"))
    return str(value).lower() not in {"false", "0", "no", "off"}


def qwen_json(
    *,
    settings: dict[str, Any] | None,
    system: str,
    user: str,
    fallback: dict[str, Any],
    timeout_seconds: int = 45,
    temperature: float = 0.15,
) -> dict[str, Any]:
    """Return JSON from local Ollama/Qwen, or fallback on any failure."""
    settings = settings or {}
    if not ollama_enabled(settings):
        return {**fallback, "llm_used": False, "llm_reason": "ollama_disabled"}

    base_url = (settings.get("ollama_base_url") or os.getenv("OLLAMA_BASE_URL") or DEFAULT_OLLAMA_BASE_URL).rstrip("/")
    model = settings.get("ollama_model") or os.getenv("OLLAMA_MODEL") or DEFAULT_OLLAMA_MODEL
    timeout = int(settings.get("ollama_timeout") or os.getenv("OLLAMA_TIMEOUT") or timeout_seconds)

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                f"{base_url}/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": temperature, "top_p": 0.85},
                },
            )
        response.raise_for_status()
        content = (response.json().get("message") or {}).get("content", "").strip()
        if content.startswith("```json"):
            content = content.split("```json", 1)[1].split("```", 1)[0].strip()
        elif content.startswith("```"):
            content = content.split("```", 1)[1].split("```", 1)[0].strip()
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise ValueError("Ollama response was not a JSON object")
        parsed["llm_used"] = True
        parsed["llm_model"] = model
        return parsed
    except Exception as exc:
        return {**fallback, "llm_used": False, "llm_error": str(exc)}


def reasoning_summary(agent_name: str, incident: dict[str, Any], tool_output: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    """Ask Qwen to explain a tool-derived result without changing it."""
    fallback = {
        "reasoning_summary": tool_output.get("recommendation") or f"{agent_name} completed using backend tools.",
        "confidence_note": "Operational values were produced by backend tools and validated by the graph.",
    }
    system = (
        "You are an emergency-response agent in S.I.R.S. Return JSON only. "
        "You may explain the decision, but you must not change unit counts, ETA, route source, incident status, or coordinates."
    )
    user = (
        f"Agent: {agent_name}\n"
        "Incident JSON:\n"
        f"{json.dumps(incident, ensure_ascii=False, default=str)[:6000]}\n\n"
        "Tool-derived output JSON:\n"
        f"{json.dumps(tool_output, ensure_ascii=False, default=str)[:9000]}\n\n"
        "Return JSON with keys: reasoning_summary, confidence_note. Do not add operational numbers not present above."
    )
    return qwen_json(settings=settings, system=system, user=user, fallback=fallback, timeout_seconds=30, temperature=0.1)
