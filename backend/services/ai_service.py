"""Local Ollama-only AI service for S.I.R.S.

The system uses a local Ollama server and falls back safely to rule-based
coordinator output if the local model is unavailable.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx

DATA_DIR = Path(__file__).parent.parent / "data"
SETTINGS_FILE = DATA_DIR / "settings.json"
INCIDENTS_FILE = DATA_DIR / "incidents.json"

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "qwen3:8b"
DEFAULT_TIMEOUT_SECONDS = 90


AI_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "priority_level": {"type": "string"},
        "final_summary": {"type": "string"},
        "immediate_actions": {"type": "array", "items": {"type": "string"}},
        "ai_insight": {"type": "string"},
        "prevention_recommendations": {"type": "array", "items": {"type": "string"}},
        "confidence_score": {"type": "number"},
        "agent_communication_log": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "agent": {"type": "string"},
                    "message": {"type": "string"},
                    "decision_impact": {"type": "string"},
                },
                "required": ["agent", "message", "decision_impact"],
            },
        },
        "conflict_resolution": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "conflict": {"type": "string"},
                    "resolution": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["conflict", "resolution", "reason"],
            },
        },
    },
    "required": [
        "priority_level",
        "final_summary",
        "immediate_actions",
        "ai_insight",
        "prevention_recommendations",
        "confidence_score",
        "agent_communication_log",
        "conflict_resolution",
    ],
}


# ── Data helpers ─────────────────────────────────────────────────────────────
def load_settings() -> dict:
    if SETTINGS_FILE.exists():
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_settings(settings: dict):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)


def load_incidents() -> list:
    if INCIDENTS_FILE.exists():
        with open(INCIDENTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_incidents(incidents: list):
    with open(INCIDENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(incidents, f, indent=2, default=str)


# ── Public API ───────────────────────────────────────────────────────────────
async def generate_ai_analysis(incident: dict, agent_responses: list, settings: dict) -> dict | None:
    """Generate AI enrichment using only local Ollama.

    Returns None when Ollama is not available so the rule-based Coordinator Agent
    remains the source of truth and the demo does not fail.
    """
    enabled = str(settings.get("ollama_enabled", os.getenv("OLLAMA_ENABLED", "true"))).lower() not in {"false", "0", "no", "off"}
    if not enabled:
        return None

    base_url = (settings.get("ollama_base_url") or os.getenv("OLLAMA_BASE_URL") or DEFAULT_OLLAMA_BASE_URL).rstrip("/")
    model = settings.get("ollama_model") or os.getenv("OLLAMA_MODEL") or DEFAULT_OLLAMA_MODEL
    timeout = int(settings.get("ollama_timeout") or os.getenv("OLLAMA_TIMEOUT") or DEFAULT_TIMEOUT_SECONDS)

    prompt = build_prompt(incident, agent_responses)
    return await _call_ollama(prompt, base_url, model, timeout)


def build_prompt(incident: dict, agent_responses: list) -> str:
    agents_payload = []
    for ar in agent_responses:
        agents_payload.append({
            "agent_name": ar.get("agent_name"),
            "risk_level": ar.get("risk_level"),
            "confidence_score": ar.get("confidence_score"),
            "recommendation": ar.get("recommendation"),
            "findings": ar.get("findings", {}),
        })

    return f"""You are the local Coordinator AI inside S.I.R.S (Smart Incident Response System) for a Riyadh smart-city emergency response demo.
You do not invent sensor readings, agencies, roads, casualties, or unsupported scenarios. Use only the incident data and specialized agent outputs below.

Your job:
1. Summarize the final response plan in a judge-friendly way.
2. Explain how the agents cooperated and which agent influenced the decision.
3. Identify conflicts between response speed, road safety, traffic continuity, and environmental safety.
4. Recommend practical prevention actions for Riyadh roads and emergency coordination.
5. Return ONLY valid JSON matching the provided schema. No markdown.

INCIDENT JSON:
{json.dumps(incident, ensure_ascii=False, indent=2, default=str)}

SPECIALIZED AGENT OUTPUTS JSON:
{json.dumps(agents_payload, ensure_ascii=False, indent=2, default=str)}
"""


async def _call_ollama(prompt: str, base_url: str, model: str, timeout: int) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{base_url}/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a strict JSON-only emergency response coordinator. Return no prose outside JSON.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                    "format": AI_RESPONSE_SCHEMA,
                    "options": {
                        "temperature": 0.2,
                        "top_p": 0.85,
                    },
                },
            )
        response.raise_for_status()
        payload = response.json()
        content = (payload.get("message") or {}).get("content", "").strip()
        if not content:
            return None
        if content.startswith("```json"):
            content = content.split("```json", 1)[1].split("```", 1)[0].strip()
        elif content.startswith("```"):
            content = content.split("```", 1)[1].split("```", 1)[0].strip()
        parsed = json.loads(content)
        parsed["provider"] = "ollama"
        parsed["model"] = model
        return parsed
    except Exception as e:
        print(f"[AI] Ollama error: {e}")
        return None


async def check_ollama_status(settings: dict | None = None) -> dict[str, Any]:
    settings = settings or load_settings()
    base_url = (settings.get("ollama_base_url") or os.getenv("OLLAMA_BASE_URL") or DEFAULT_OLLAMA_BASE_URL).rstrip("/")
    model = settings.get("ollama_model") or os.getenv("OLLAMA_MODEL") or DEFAULT_OLLAMA_MODEL
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            tags_res = await client.get(f"{base_url}/api/tags")
        tags_res.raise_for_status()
        models = [m.get("name") for m in tags_res.json().get("models", [])]
        return {
            "enabled": True,
            "reachable": True,
            "base_url": base_url,
            "model": model,
            "model_installed": model in models,
            "installed_models": models,
        }
    except Exception as e:
        return {
            "enabled": True,
            "reachable": False,
            "base_url": base_url,
            "model": model,
            "model_installed": False,
            "installed_models": [],
            "error": str(e),
        }


REPORT_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "executive_summary": {"type": "string"},
        "camera_detection_summary": {"type": "string"},
        "dispatch_summary": {"type": "string"},
        "route_eta_summary": {"type": "string"},
        "final_status_summary": {"type": "string"},
        "lessons_learned": {"type": "array", "items": {"type": "string"}},
        "recommendations": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "executive_summary", "camera_detection_summary", "dispatch_summary",
        "route_eta_summary", "final_status_summary", "lessons_learned", "recommendations"
    ],
}


def _fallback_incident_report(incident: dict, agent_responses: list, final_decision: dict) -> dict[str, Any]:
    camera = next((a for a in agent_responses if a.get("agent_name") == "Camera Vision Agent"), {})
    emergency = next((a for a in agent_responses if a.get("agent_name") == "Emergency Agent"), {})
    camera_f = camera.get("findings", {})
    emergency_f = emergency.get("findings", {})
    eta = final_decision.get("ev_eta_decision", {}) or {}
    fleet = emergency_f.get("dispatched_fleet", []) or []
    status = incident.get("status", "Unknown")
    route_provider = eta.get("route_provider") or "osrm/fallback"
    units = ", ".join(f"{v.get('type')} {v.get('unitId')}" for v in fleet[:6]) or "No fleet dispatch recorded"
    return {
        "executive_summary": final_decision.get("final_summary") or (
            f"{incident.get('type')} at {incident.get('location_name')} was processed by the S.I.R.S multi-agent workflow. "
            f"The incident status is {status}, severity is {incident.get('severity')}, and dispatch decisions were generated from the current incident data."
        ),
        "camera_detection_summary": (
            f"Camera {camera_f.get('camera_id', incident.get('camera_id', 'N/A'))} detected {incident.get('type')} "
            f"with {int((camera.get('confidence_score') or 0) * 100)}% confidence. Evidence: "
            f"{'; '.join(camera_f.get('evidence', [])[:4]) or incident.get('description', 'No camera evidence attached.')}"
        ),
        "dispatch_summary": (
            f"Emergency Agent selected incident-specific units only: {units}. "
            f"Dispatch reasoning: {'; '.join(emergency_f.get('dispatch_reasoning', [])[:4])}"
        ),
        "route_eta_summary": (
            f"Routes were calculated through {route_provider}. Primary unit {eta.get('unit', 'N/A')} has normal ETA "
            f"{eta.get('normal_eta', '—')} min and priority ETA {eta.get('priority_eta', '—')} min, saving {eta.get('time_saved', '—')} min."
        ),
        "final_status_summary": (
            "Incident is resolved and all report timeline rows were normalized to completed status."
            if str(status).lower() == "resolved" else
            f"Incident remains {status}; pending timeline rows represent future operational steps."
        ),
        "lessons_learned": [
            "Camera-triggered incident creation reduces dependency on manual reporting.",
            "Dispatch must remain incident-specific to avoid wasting emergency resources.",
            "ETA values should be explained by route source, traffic factor, and priority corridor effect.",
        ],
        "recommendations": final_decision.get("prevention_recommendations") or [
            "Keep camera evidence attached to every incident record.",
            "Review recurring hot spots using the incident memory dataset.",
            "Continue improving real road routing through local OSRM cache for offline demos.",
        ],
    }


async def generate_incident_report(incident: dict, agent_responses: list, final_decision: dict, settings: dict) -> dict[str, Any]:
    """Generate an incident-specific report narrative with Ollama/Qwen when available.

    Falls back to a deterministic report built only from the actual incident,
    camera evidence, specialized agent outputs, route ETA, and final status.
    """
    fallback = _fallback_incident_report(incident, agent_responses, final_decision)
    enabled = str(settings.get("ollama_enabled", os.getenv("OLLAMA_ENABLED", "true"))).lower() not in {"false", "0", "no", "off"}
    if not enabled:
        fallback["generated_by"] = "deterministic_report_builder"
        return fallback

    base_url = (settings.get("ollama_base_url") or os.getenv("OLLAMA_BASE_URL") or DEFAULT_OLLAMA_BASE_URL).rstrip("/")
    model = settings.get("ollama_model") or os.getenv("OLLAMA_MODEL") or DEFAULT_OLLAMA_MODEL
    timeout = int(settings.get("ollama_timeout") or os.getenv("OLLAMA_TIMEOUT") or DEFAULT_TIMEOUT_SECONDS)

    prompt = f"""You are the S.I.R.S local report-writing AI. Generate an incident-specific report narrative.
Do not use generic mock text. Do not claim pending actions if the incident status is Resolved.
Use only the incident, camera evidence, agent outputs, and final decision below.
Return ONLY valid JSON matching the schema.

INCIDENT:
{json.dumps(incident, ensure_ascii=False, indent=2, default=str)}

AGENT_OUTPUTS:
{json.dumps(agent_responses, ensure_ascii=False, indent=2, default=str)}

FINAL_DECISION:
{json.dumps(final_decision, ensure_ascii=False, indent=2, default=str)}
"""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{base_url}/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "You are a strict JSON-only incident report writer. Return no prose outside JSON."},
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                    "format": REPORT_RESPONSE_SCHEMA,
                    "options": {"temperature": 0.15, "top_p": 0.8},
                },
            )
        response.raise_for_status()
        content = (response.json().get("message") or {}).get("content", "").strip()
        if content.startswith("```json"):
            content = content.split("```json", 1)[1].split("```", 1)[0].strip()
        elif content.startswith("```"):
            content = content.split("```", 1)[1].split("```", 1)[0].strip()
        parsed = json.loads(content)
        parsed["generated_by"] = "ollama_qwen_report_writer"
        parsed["model"] = model
        return {**fallback, **parsed}
    except Exception as e:
        print(f"[AI] Report generation fallback used: {e}")
        fallback["generated_by"] = "deterministic_report_builder"
        fallback["ollama_error"] = str(e)
        return fallback
