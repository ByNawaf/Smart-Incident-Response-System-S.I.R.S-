from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import uuid
import random
from datetime import datetime

from models.schemas import IncidentCreate, SettingsUpdate
from services import data_service, ai_service, demo_service, google_routes_service, google_places_service
from services.demo_service import DEMO_INCIDENT_ID
from agents import traffic_agent, emergency_agent, environment_agent, analysis_agent, coordinator_agent, camera_vision_agent
from agent_graph import run_incident_graph, LANGGRAPH_AVAILABLE
from agent_graph.decision_layer import apply_camera_qwen_decision

# ── App setup ────────────────────────────────────────────────────────────────
app = FastAPI(title="S.I.R.S API", version="1.6.0", description="Smart Incident Response System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

# Serve static frontend files
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# ── Root: serve landing page ─────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root():
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"message": "S.I.R.S API Running — frontend not found"}


@app.get("/{page}.html", include_in_schema=False)
async def serve_page(page: str):
    html_file = FRONTEND_DIR / f"{page}.html"
    if html_file.exists():
        return FileResponse(str(html_file))
    raise HTTPException(status_code=404, detail="Page not found")



# ── Multi-Agent Pipeline Helpers ─────────────────────────────────────────────
def _merge_ai_into_final(final: dict, ai_result: dict | None) -> dict:
    """Merge optional Ollama/Qwen enrichment without replacing calculated tools data."""
    if ai_result:
        final["ai_enhanced"] = True
        final["ai_provider"] = ai_result.get("provider", "ollama")
        final["ai_model"] = ai_result.get("model", "qwen3:8b")
        final["ai_insight"] = ai_result.get("ai_insight", "")
        for key in ["final_summary", "immediate_actions", "prevention_recommendations"]:
            if ai_result.get(key):
                final[key] = ai_result[key]
        if ai_result.get("agent_communication_log"):
            final["ollama_agent_communication_log"] = ai_result["agent_communication_log"]
        if ai_result.get("conflict_resolution"):
            final["ai_conflict_resolution"] = ai_result["conflict_resolution"]
    else:
        final["ai_enhanced"] = False
        final["ai_provider"] = "ollama"
    return final


async def _run_full_agent_pipeline(incident: dict, city: dict, settings: dict, camera_result: dict | None = None, camera: dict | None = None) -> tuple[list, dict]:
    """Run the LangGraph-powered multi-agent workflow for an incident.

    FastAPI remains the application/API layer. LangGraph is now the core agent
    orchestration engine: it runs camera, traffic, emergency, environment,
    analysis, coordinator, and validation nodes over one shared incident state.
    """
    graph_state = run_incident_graph(
        incident=incident,
        city_data=city,
        settings=settings,
        camera=camera,
        camera_result=camera_result,
    )
    agent_responses = graph_state.get("agent_responses", [])
    final = graph_state.get("final_decision", {})
    final["agent_graph"] = {
        "engine": graph_state.get("graph_engine", "langgraph"),
        "langgraph_available": LANGGRAPH_AVAILABLE,
        "trace": graph_state.get("graph_trace", []),
        "errors": graph_state.get("errors", []),
        "validation": graph_state.get("validation", {}),
    }
    return agent_responses, final


# ── City Data ─────────────────────────────────────────────────────────────────
@app.get("/api/city-data")
async def get_city_data():
    return data_service.load_city_data()



@app.get("/api/agent-graph/status")
async def get_agent_graph_status():
    return {
        "fastapi_layer": "active",
        "agent_engine": "LangGraph" if LANGGRAPH_AVAILABLE else "Sequential compatibility runner",
        "langgraph_available": LANGGRAPH_AVAILABLE,
        "workflow": [
            "Camera Vision Agent",
            "Traffic Agent",
            "Emergency Agent",
            "Environment Agent",
            "Analysis Agent",
            "Coordinator Agent",
            "Validation Node",
        ],
    }

# ── Camera Monitoring / Camera Vision Agent ─────────────────────────────────
@app.get("/api/cameras")
async def get_cameras():
    """Return camera scenarios used by the Camera Detection Simulator."""
    scenarios = data_service.load_camera_scenarios()
    return {
        "version": scenarios.get("version", "1.0"),
        "note": scenarios.get("note", ""),
        "cameras": scenarios.get("cameras", []),
        "total": len(scenarios.get("cameras", [])),
    }


@app.post("/api/cameras/{camera_id}/scan")
async def scan_camera(camera_id: str):
    """Run only the Camera Vision Agent for one camera without creating an incident."""
    scenarios = data_service.load_camera_scenarios()
    camera = next((c for c in scenarios.get("cameras", []) if c.get("camera_id") == camera_id), None)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    settings = data_service.load_settings()
    result = camera_vision_agent.classify_camera_event(camera)
    result = apply_camera_qwen_decision(result, camera, settings)
    return {"camera": camera, "camera_agent_result": result}


@app.post("/api/cameras/{camera_id}/trigger")
async def trigger_camera_incident(camera_id: str):
    """Camera detects an incident, creates it automatically, and runs all agents."""
    scenarios = data_service.load_camera_scenarios()
    camera = next((c for c in scenarios.get("cameras", []) if c.get("camera_id") == camera_id), None)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    city = data_service.load_city_data()
    settings = data_service.load_settings()
    camera_result = camera_vision_agent.classify_camera_event(camera)
    camera_result = apply_camera_qwen_decision(camera_result, camera, settings)
    payload = (camera_result.get("findings") or {}).get("incident_payload")
    if not payload:
        return {
            "camera": camera,
            "camera_agent_result": camera_result,
            "incident_created": False,
            "message": "No incident detected; monitoring continues.",
        }

    incident = payload.copy()
    incident["id"] = f"CAM-{str(uuid.uuid4())[:8].upper()}"
    incident["status"] = "Active"
    incident["created_at"] = datetime.now().isoformat()
    incident["camera_detection"] = camera_result.get("findings", {})

    agent_responses, final = await _run_full_agent_pipeline(incident, city, settings, camera_result, camera)
    incident["status"] = "Resolved"
    final["resolved_status"] = "Resolved"
    if isinstance(final.get("final_summary"), str):
        final["final_summary"] = final["final_summary"].replace("Current incident status: Active.", "Current incident status: Resolved.")
    incident["agent_responses"] = agent_responses
    incident["final_decision"] = final

    incidents = data_service.load_incidents()
    incidents.append(incident)
    data_service.save_incidents(incidents)
    return {
        "camera": camera,
        "camera_agent_result": camera_result,
        "incident_created": True,
        "incident": incident,
        "agent_responses": agent_responses,
        "final_decision": final,
    }


@app.post("/api/camera-demo/run")
async def run_camera_demo(payload: dict | None = None):
    """Run the camera-first demo. Defaults to the high collision scenario."""
    payload = payload or {}
    camera_id = payload.get("camera_id") or "CAM-KFD-01"
    return await trigger_camera_incident(camera_id)


# ── Stats / Dashboard ─────────────────────────────────────────────────────────
@app.get("/api/stats")
async def get_stats():
    incidents = data_service.load_incidents()
    return data_service.get_dashboard_stats(incidents)


# ── Incidents ─────────────────────────────────────────────────────────────────
@app.get("/api/incidents")
async def get_incidents():
    return data_service.load_incidents()


@app.post("/api/incidents", status_code=201)
async def create_incident(payload: IncidentCreate):
    incidents = data_service.load_incidents()
    incident = payload.model_dump()
    incident["id"] = f"INC-{str(uuid.uuid4())[:8].upper()}"
    incident["status"] = "Active"
    incident["created_at"] = datetime.now().isoformat()
    if not incident.get("time"):
        incident["time"] = datetime.now().strftime("%H:%M")
    incidents.append(incident)
    data_service.save_incidents(incidents)
    return incident


@app.get("/api/incidents/{incident_id}")
async def get_incident(incident_id: str):
    incidents = data_service.load_incidents()
    inc = next((i for i in incidents if i["id"] == incident_id), None)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    return inc


@app.delete("/api/incidents/{incident_id}")
async def delete_incident(incident_id: str):
    incidents = data_service.load_incidents()
    incidents = [i for i in incidents if i["id"] != incident_id]
    data_service.save_incidents(incidents)
    return {"message": "Incident deleted"}


# ── Agent Analysis ────────────────────────────────────────────────────────────
@app.post("/api/incidents/{incident_id}/analyze")
async def analyze_incident(incident_id: str):
    incidents = data_service.load_incidents()
    inc = next((i for i in incidents if i["id"] == incident_id), None)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    city = data_service.load_city_data()
    settings = data_service.load_settings()
    agent_responses, final = await _run_full_agent_pipeline(inc, city, settings)

    # Store LangGraph agent outputs. Final decision is saved as a preview;
    # /coordinate is still allowed to mark the incident as Resolved.
    inc["agent_responses"] = agent_responses
    inc["final_decision_preview"] = final
    inc["status"] = "Analyzed"
    data_service.save_incidents(incidents)

    return {"incident": inc, "agent_responses": agent_responses, "final_decision_preview": final}


# ── Coordinator Decision ──────────────────────────────────────────────────────
@app.post("/api/incidents/{incident_id}/coordinate")
async def coordinate_incident(incident_id: str):
    incidents = data_service.load_incidents()
    inc = next((i for i in incidents if i["id"] == incident_id), None)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    city = data_service.load_city_data()
    settings = data_service.load_settings()
    agent_responses, final = await _run_full_agent_pipeline(inc, city, settings)

    # Save final LangGraph decision
    inc["agent_responses"] = agent_responses
    inc["final_decision"] = final
    inc["status"] = "Resolved"
    final["resolved_status"] = "Resolved"
    data_service.save_incidents(incidents)

    return {"incident": inc, "final_decision": final}


# ── Incident Report ───────────────────────────────────────────────────────────
@app.get("/api/incidents/{incident_id}/report")
async def get_report(incident_id: str):
    incidents = data_service.load_incidents()
    inc = next((i for i in incidents if i["id"] == incident_id), None)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    final = inc.get("final_decision", {})
    agent_responses = inc.get("agent_responses", [])
    settings = data_service.load_settings()

    ai_report = await ai_service.generate_incident_report(inc, agent_responses, final, settings)
    timeline = final.get("response_timeline", [])
    if str(inc.get("status", "")).lower() == "resolved":
        timeline = [{**t, "status": "done"} for t in timeline]

    report = {
        "report_id": f"RPT-{incident_id}",
        "generated_at": datetime.now().isoformat(),
        "incident": inc,
        "executive_summary": ai_report.get("executive_summary", final.get("final_summary", "Analysis pending")),
        "camera_detection_summary": ai_report.get("camera_detection_summary", ""),
        "dispatch_summary": ai_report.get("dispatch_summary", ""),
        "route_eta_summary": ai_report.get("route_eta_summary", ""),
        "final_status_summary": ai_report.get("final_status_summary", ""),
        "lessons_learned": ai_report.get("lessons_learned", []),
        "priority_level": final.get("priority_level", "N/A"),
        "agent_analyses": agent_responses,
        "final_decision": {**final, "response_timeline": timeline},
        "response_timeline": timeline,
        "prevention_recommendations": ai_report.get("recommendations") or final.get("prevention_recommendations", []),
        "ai_enhanced": final.get("ai_enhanced", False),
        "report_generated_by": ai_report.get("generated_by", "deterministic_report_builder"),
        "report_model": ai_report.get("model", ""),
    }
    return report


# ── Emergency Units Fleet ─────────────────────────────────────────────────
@app.get("/api/emergency-units")
async def get_emergency_units():
    """Return all emergency vehicles with current status from city data."""
    city = data_service.load_city_data()
    vehicles = city.get("emergency_vehicles", [])
    return {"emergency_units": vehicles, "total": len(vehicles)}


@app.post("/api/incidents/{incident_id}/emergency-route")
async def calculate_emergency_route(incident_id: str):
    """Calculate and return emergency vehicle normal ETA vs priority ETA for an incident."""
    incidents = data_service.load_incidents()
    inc = next((i for i in incidents if i["id"] == incident_id), None)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    city = data_service.load_city_data()
    result = emergency_agent.run(inc, city)
    findings = result.get("findings", {})
    sv = findings.get("selected_vehicle", {})
    return {
        "incident_id": incident_id,
        "selected_vehicle": sv,
        "ev_normal_eta": findings.get("ev_normal_eta"),
        "ev_priority_eta": findings.get("ev_priority_eta"),
        "ev_time_saved": findings.get("ev_time_saved"),
        "ev_congestion_level": findings.get("ev_congestion_level"),
        "ev_route_status": findings.get("ev_route_status"),
        "ev_priority_intersections": findings.get("ev_priority_intersections", []),
        "ev_normal_route": findings.get("ev_normal_route", []),
        "ev_priority_route": findings.get("ev_priority_route", []),
        "ev_summary": findings.get("ev_summary", ""),
    }


@app.post("/api/incidents/{incident_id}/activate-emergency-corridor")
async def activate_emergency_corridor(incident_id: str):
    """Activate simulated emergency corridor — marks corridor as active in incident record."""
    incidents = data_service.load_incidents()
    inc = next((i for i in incidents if i["id"] == incident_id), None)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    city = data_service.load_city_data()
    result = emergency_agent.run(inc, city)
    findings = result.get("findings", {})
    inc["emergency_corridor_active"] = True
    inc["emergency_corridor_data"] = findings.get("selected_vehicle", {})
    data_service.save_incidents(incidents)
    return {
        "incident_id": incident_id,
        "corridor_activated": True,
        "message": f"Emergency corridor activated for {findings.get('selected_vehicle', {}).get('unitId', 'unit')}",
        "ev_priority_eta": findings.get("ev_priority_eta"),
        "ev_time_saved": findings.get("ev_time_saved"),
    }


# ── Settings / Frontend Config ───────────────────────────────────────────────
@app.get("/api/settings")
async def get_settings():
    settings = data_service.load_settings()
    masked = settings.copy()

    # Always force Ollama as the active local AI provider.
    masked["ai_provider"] = "ollama"
    masked.setdefault("ollama_base_url", "http://localhost:11434")
    masked.setdefault("ollama_model", "qwen3:8b")
    masked.setdefault("ollama_timeout", 90)
    masked.setdefault("ollama_enabled", True)
    masked.setdefault("google_maps_enabled", False)

    # Mask browser/server keys for display while keeping status flags.
    for key, flag in [
        ("google_maps_browser_key", "google_maps_browser_key_set"),
        ("google_routes_api_key", "google_routes_key_set"),
        ("google_places_api_key", "google_places_key_set"),
    ]:
        value = masked.get(key, "")
        if value:
            masked[key] = value[:6] + "••••••••" + value[-4:] if len(value) > 12 else "••••••••"
            masked[flag] = True
        else:
            masked[flag] = False


    # Best-effort local Ollama health info.
    masked["ollama_status"] = await ai_service.check_ollama_status(settings)
    return masked


@app.post("/api/settings")
async def update_settings(payload: SettingsUpdate):
    settings = data_service.load_settings()

    settings["ai_provider"] = "ollama"
    if payload.ollama_base_url:
        settings["ollama_base_url"] = payload.ollama_base_url.rstrip("/")
    if payload.ollama_model:
        settings["ollama_model"] = payload.ollama_model
    if payload.ollama_timeout:
        settings["ollama_timeout"] = payload.ollama_timeout
    if payload.ollama_enabled is not None:
        settings["ollama_enabled"] = payload.ollama_enabled

    if payload.google_maps_enabled is not None:
        settings["google_maps_enabled"] = payload.google_maps_enabled
    if payload.google_maps_browser_key and "••" not in payload.google_maps_browser_key:
        settings["google_maps_browser_key"] = payload.google_maps_browser_key
    if payload.google_routes_api_key and "••" not in payload.google_routes_api_key:
        settings["google_routes_api_key"] = payload.google_routes_api_key
    if payload.google_places_api_key and "••" not in payload.google_places_api_key:
        settings["google_places_api_key"] = payload.google_places_api_key
    if payload.google_places_enabled is not None:
        settings["google_places_enabled"] = payload.google_places_enabled


    data_service.save_settings(settings)
    return {"message": "Settings saved successfully", "ai_provider": "ollama"}


@app.get("/api/frontend-config")
async def frontend_config():
    """Minimal non-secret config for browser-side Google Maps rendering."""
    settings = data_service.load_settings()
    browser_key = google_routes_service.get_browser_key()
    return {
        "map_provider": "google" if browser_key and google_routes_service.google_maps_enabled() else "leaflet_fallback",
        "google_maps_enabled": bool(browser_key and google_routes_service.google_maps_enabled()),
        "google_maps_browser_key": browser_key,
        "ollama_model": settings.get("ollama_model", "qwen3:8b"),
    }


@app.post("/api/routes/preview")
async def preview_route(payload: dict):
    """Preview a real Google/fallback route between two points for debugging."""
    origin = payload.get("origin") or {}
    destination = payload.get("destination") or {}
    if not origin or not destination:
        raise HTTPException(status_code=400, detail="origin and destination are required")
    routes = google_routes_service.compute_routes(
        (float(origin["lat"]), float(origin["lng"])),
        (float(destination["lat"]), float(destination["lng"])),
        role=payload.get("role", "primary"),
    )
    return routes


# ── Demo Mode ─────────────────────────────────────────────────────────────────
@app.post("/api/demo/run")
async def run_demo():
    """Run the unified Riyadh demo scenario automatically.

    The demo uses a stable incident ID so all pages replay the same scenario and
    read the same stored agent outputs, route geometry, ETA, communication log,
    and generated report.
    """
    city = data_service.load_city_data()
    settings = data_service.load_settings()

    # 1. Create/update the unified demo incident
    inc = demo_service.get_demo_incident()

    # Keep demo outputs stable for presentation mode.
    random.seed("SIRS-RIYADH-DEMO-V1.5")

    # 2. Run all agents
    traffic_result = traffic_agent.run(inc, city)
    emergency_result = emergency_agent.run(inc, city)
    env_result = environment_agent.run(inc, city)
    analysis_result = analysis_agent.run(inc, city)
    agent_responses = [traffic_result, emergency_result, env_result, analysis_result]
    inc["agent_responses"] = agent_responses

    # 3. Try AI enrichment
    ai_result = await ai_service.generate_ai_analysis(inc, agent_responses, settings)

    # 4. Coordinator final plan
    final = coordinator_agent.run(inc, agent_responses, city)
    if ai_result:
        final["ai_enhanced"] = True
        final["ai_provider"] = ai_result.get("provider", "ollama")
        final["ai_model"] = ai_result.get("model", "qwen3:8b")
        final["ai_insight"] = ai_result.get("ai_insight", "")
        if ai_result.get("final_summary"):
            final["final_summary"] = ai_result["final_summary"]
        if ai_result.get("immediate_actions"):
            final["immediate_actions"] = ai_result["immediate_actions"]
        if ai_result.get("prevention_recommendations"):
            final["prevention_recommendations"] = ai_result["prevention_recommendations"]
        if ai_result.get("agent_communication_log"):
            final["ollama_agent_communication_log"] = ai_result["agent_communication_log"]
        if ai_result.get("conflict_resolution"):
            final["ai_conflict_resolution"] = ai_result["conflict_resolution"]
    else:
        final["ai_enhanced"] = False
        final["ai_provider"] = "ollama"

    inc["final_decision"] = final
    inc["status"] = "Resolved"

    # 5. Save/update the unified demo record instead of appending duplicates.
    incidents = data_service.load_incidents()
    incidents = [i for i in incidents if i.get("id") != DEMO_INCIDENT_ID]
    incidents.append(inc)
    data_service.save_incidents(incidents)

    return {
        "incident": inc,
        "agent_responses": agent_responses,
        "final_decision": final,
        "demo": True
    }


@app.get("/api/demo/current")
async def get_current_demo():
    """Return the unified demo incident if it has been generated already."""
    incidents = data_service.load_incidents()
    demo = next((i for i in incidents if i.get("id") == DEMO_INCIDENT_ID), None)
    if not demo:
        raise HTTPException(status_code=404, detail="Unified demo has not been generated yet. Run /api/demo/run first.")
    return {
        "incident": demo,
        "agent_responses": demo.get("agent_responses", []),
        "final_decision": demo.get("final_decision", {}),
        "demo": True
    }


# ── Public Citizen Alert Portal ───────────────────────────────────────────────

_INCIDENT_INSTRUCTIONS = {
    "Fire Incident":     {"do": ["Stay clear of the incident area", "Follow evacuation orders immediately", "Keep roads clear for fire trucks", "Call 998 for fire or smoke escalation"], "dont": ["Do NOT stop near the fire", "Do NOT obstruct emergency routes", "Do NOT re-enter evacuated buildings"], "alert_level": "WARNING", "color": "#f97316"},
    "Traffic Accident":  {"do": ["Use alternative routes as directed", "Call 997 if injuries are present", "Move your vehicle off the road if safe"], "dont": ["Do NOT stop to observe the scene", "Do NOT drive through the blocked area"], "alert_level": "ADVISORY", "color": "#eab308"},
    "Road Blockage":     {"do": ["Use alternative routes", "Allow extra travel time", "Follow traffic control directions"], "dont": ["Do NOT attempt to pass through blockage"], "alert_level": "ADVISORY", "color": "#eab308"},
    "Fuel Spill":        {"do": ["Stay clear of the spill area", "Call 998 if fire risk or fuel vapour is visible", "Eliminate ignition sources", "Follow evacuation orders if issued"], "dont": ["Do NOT smoke near the area", "Do NOT start engines near spill"], "alert_level": "WARNING", "color": "#f97316"},
    "Medical Emergency": {"do": ["Keep area clear for ambulances", "Call 997 immediately", "Offer help only if trained in first aid"], "dont": ["Do NOT crowd the scene", "Do NOT obstruct emergency access"], "alert_level": "ADVISORY", "color": "#eab308"},
}


@app.get("/api/public/alerts")
async def get_public_alerts():
    """Public-facing emergency alert feed for citizens."""
    incidents = data_service.load_incidents()
    public_alerts = []
    total_citizens = 0
    zones_set = set()
    sev_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}

    for inc in incidents:
        inc_type  = inc.get("type", "Traffic Accident")
        severity  = inc.get("severity", "Medium")
        info      = _INCIDENT_INSTRUCTIONS.get(inc_type, _INCIDENT_INSTRUCTIONS["Traffic Accident"])

        radius_m, units_deployed = 300, 0
        for a in inc.get("agent_responses", []):
            if a.get("agent_name") == "Environment Agent":
                radius_m = a.get("findings", {}).get("affected_radius_m", 300)
            if a.get("agent_name") == "Emergency Agent":
                units_deployed = sum(u.get("count", 1) for u in a.get("findings", {}).get("units_dispatched", []))

        sev_mult           = {"Low": 1, "Medium": 3, "High": 6, "Critical": 12}.get(severity, 3)
        estimated_citizens = max(300, int(radius_m * sev_mult * 0.8))
        alert_sent         = inc.get("public_alert_sent", False)
        citizens_notified  = inc.get("citizens_notified", 0) if alert_sent else 0
        total_citizens    += citizens_notified
        zone               = inc.get("location_name", "City Center")
        zones_set.add(zone.split(" ")[0])

        public_alerts.append({
            "id": inc.get("id"), "type": inc_type, "severity": severity,
            "alert_level": info["alert_level"], "alert_color": info["color"],
            "location": zone, "latitude": inc.get("latitude"), "longitude": inc.get("longitude"),
            "time": inc.get("time", "—"), "created_at": inc.get("created_at", ""),
            "status": inc.get("status"), "description": inc.get("description", ""),
            "affected_radius_m": radius_m, "instructions_do": info["do"], "instructions_dont": info["dont"],
            "affected_people": inc.get("affected_people", 0), "affected_vehicles": inc.get("affected_vehicles", 0),
            "alert_sent": alert_sent, "citizens_notified": citizens_notified,
            "estimated_citizens": estimated_citizens, "units_deployed": units_deployed,
            "alert_sent_at": inc.get("alert_sent_at", ""), "alert_zones": inc.get("alert_zones", [zone]),
        })

    public_alerts.sort(key=lambda x: (0 if x["status"] in ["Active", "Analyzed"] else 1, sev_order.get(x["severity"], 2)))
    any_active = any(a["status"] in ["Active", "Analyzed"] for a in public_alerts)
    return {
        "alerts": public_alerts[:12],
        "total_active": len([a for a in public_alerts if a["status"] in ["Active", "Analyzed"]]),
        "total_citizens_notified": total_citizens,
        "zones_affected": list(zones_set)[:6],
        "system_status": "ACTIVE EMERGENCY" if any_active else "ALL CLEAR",
        "last_updated": datetime.now().isoformat(),
    }


@app.post("/api/incidents/{incident_id}/send-alert")
async def send_public_alert(incident_id: str):
    """Simulate dispatching a public emergency alert to citizens in the affected zone."""
    incidents = data_service.load_incidents()
    inc = next((i for i in incidents if i["id"] == incident_id), None)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    severity  = inc.get("severity", "Medium")
    radius_m  = 300
    for a in inc.get("agent_responses", []):
        if a.get("agent_name") == "Environment Agent":
            radius_m = a.get("findings", {}).get("affected_radius_m", 300)

    sev_mult          = {"Low": 1, "Medium": 3, "High": 6, "Critical": 12}.get(severity, 3)
    citizens_notified = max(500, int(radius_m * sev_mult * 0.8))

    city = data_service.load_city_data()
    inc_lat, inc_lng = inc.get("latitude", 24.7136), inc.get("longitude", 46.6753)
    zones = [inc.get("location_name", "City Center")]
    for loc in city.get("locations", []):
        dist = ((loc["lat"] - inc_lat) ** 2 + (loc["lng"] - inc_lng) ** 2) ** 0.5
        if dist < 0.05:
            zones.append(loc["name"])
    zones = list(set(zones))[:3]

    inc["public_alert_sent"]  = True
    inc["citizens_notified"]  = citizens_notified
    inc["alert_zones"]        = zones
    inc["alert_sent_at"]      = datetime.now().isoformat()
    data_service.save_incidents(incidents)

    inc_type = inc.get("type", "Incident")
    info     = _INCIDENT_INSTRUCTIONS.get(inc_type, _INCIDENT_INSTRUCTIONS["Traffic Accident"])
    return {
        "incident_id": incident_id, "alert_sent": True,
        "citizens_notified": citizens_notified, "zones_alerted": zones,
        "channels": ["SMS", "Mobile App Push", "Emergency Broadcast", "Variable Message Signs"],
        "alert_level": info["alert_level"],
        "message": f"EMERGENCY ALERT: {inc_type} at {inc.get('location_name')}. Avoid the area. Follow official instructions.",
        "estimated_reach_min": 3,
    }


@app.post("/api/public/report", status_code=201)
async def citizen_report_incident(payload: IncidentCreate):
    """Allow citizens to report an incident through the public portal."""
    incidents = data_service.load_incidents()
    incident = payload.model_dump()
    incident["id"]           = f"CIT-{str(uuid.uuid4())[:8].upper()}"
    incident["status"]       = "Active"
    incident["created_at"]   = datetime.now().isoformat()
    incident["reported_by"]  = "Citizen Report — Public Portal"
    if not incident.get("time"):
        incident["time"] = datetime.now().strftime("%H:%M")
    incidents.append(incident)
    data_service.save_incidents(incidents)
    return {"message": "Report received. Emergency services have been notified.", "report_id": incident["id"]}


@app.get("/api/routing/diagnostics")
async def routing_diagnostics(lat: float = 24.7136, lng: float = 46.6753):
    """Validate whether real road routing and real Riyadh origins are active."""
    routes = google_routes_service.diagnostics((lat + 0.02, lng - 0.02), (lat, lng))
    places = google_places_service.diagnostics(lat, lng)
    return {"routes": routes, "places": places}


@app.get("/api/google/diagnostics")
async def google_diagnostics(lat: float = 24.7136, lng: float = 46.6753):
    """Backward-compatible endpoint used by Settings. Now reports OSRM too."""
    return await routing_diagnostics(lat, lng)


# ── Health Check ──────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    settings = data_service.load_settings()
    ollama = await ai_service.check_ollama_status(settings)
    return {
        "status": "ok",
        "system": "S.I.R.S",
        "version": "1.6.0-riyadh-realistic-resources",
        "agents": 6,
        "ai_provider": "ollama",
        "ollama": ollama,
        "map_provider": "openstreetmap_leaflet" if not google_routes_service.get_browser_key() else "google_maps_optional",
        "routing_provider": "osrm_openstreetmap",
        "google_routes_key_configured": bool(google_routes_service.get_server_key()),
        "google_places_key_configured": bool(google_places_service.get_places_key()),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
