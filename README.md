# S.I.R.S — Smart Incident Response System

Agenticthon-ready Riyadh demo with:

- FastAPI backend
- Vanilla JS frontend
- Leaflet + OpenStreetMap visible map by default
- OSRM/OpenStreetMap real road routing without Google billing
- Curated Riyadh emergency-service origins for ambulance, traffic, police, fire, civil defense, and road-service/tow units
- Hospitals are modeled as patient destinations, not ambulance dispatch origins
- Ollama-only local AI provider
- Multi-agent architecture: Camera Vision, Traffic, Emergency, Environment, Analysis, Coordinator

## Camera-first command center

This build adds a new camera-based flow for Agenticthon:

```text
Street Camera → Camera Vision Agent → Auto Incident → Specialized Agents → Coordinator → Map Dispatch → Incident Report
```

Open the new command center:

```text
http://localhost:8000/command-center.html
```

Camera scenarios are stored in `backend/data/camera_scenarios.json`. Each scenario contains camera coordinates, road context, observed visual/sensor cues, and optional `media_url`. You can later place real licensed clips under `frontend/assets/camera-feeds/` and reference them from the scenario file without changing the agent pipeline.

New camera API endpoints:

```text
GET  /api/cameras
POST /api/cameras/{camera_id}/scan
POST /api/cameras/{camera_id}/trigger
POST /api/camera-demo/run
```

## What changed in this build

Google billing is no longer required for the demo. Routes are requested from OSRM using OpenStreetMap road geometry, so emergency vehicles move on actual road polylines instead of straight fake lines. If OSRM is unreachable, the app still has a last-resort deterministic fallback and marks it clearly.

### v1.6 resource realism / dispatch suitability fixes

- Ambulances now dispatch from EMS / Red Crescent response bases when available. Hospitals are used as patient destinations only.
- Added a patient-transfer plan for ambulance cases, including destination hospital and transfer ETA when routing is available.
- Emergency Agent now dispatches only incident-suitable vehicles:
  - Medical Emergency: ambulance + traffic access support when needed.
  - Traffic Accident: ambulance only if people are affected, plus traffic/police/tow as needed.
  - Fire Incident: fire + civil defense + perimeter support; ambulance only if casualties are detected.
  - Fuel Spill: fire + civil defense + traffic/police isolation; ambulance only if people are affected and staged outside the hazard zone.
  - Road Blockage: traffic unit + road-service/tow, with police only for high-impact scenes.

### v1.5/v1.4 realism / consistency fixes

- Demo scenario is a Riyadh-realistic **Fuel Spill** on King Fahd Road with fire, civil defense, police, and ambulance coordination.
- Supported incident types are limited to realistic Riyadh road/public-safety scenarios.
- Added deterministic Agent Communication Log and Conflict Resolution even when Ollama is offline.
- Expanded the report to include camera evidence, incident-specific dispatch reasoning, route optimisation, agent communication, conflict resolution, final status, and lessons learned.
- Added live replay controls to Agents Analysis and Judges View so the simulation uses the same routes, fleet, ETA, and agent outputs across pages.
- Dashboard statistics now derive from stored incident decisions instead of hardcoded values.

## Requirements

Use Python 3.11 or 3.12. Avoid Python 3.14 for the pinned dependency set.

```bash
cd backend
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Ollama setup

```bash
ollama pull qwen3:8b
ollama run qwen3:8b
```

Then exit with `/bye`. Ollama normally serves the local API at:

```text
http://localhost:11434
```

## Run

```bash
cd backend
.venv\Scripts\activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Open:

```text
http://localhost:8000/command-center.html
```

## Test routing

Open:

```text
http://localhost:8000/api/routing/diagnostics
```

Expected real mode:

```json
{
  "routes": { "source": "osrm" },
  "places": { "source": "riyadh_local_real" }
}
```

If `routes.source` is `fallback`, OSRM was not reachable from your network.

## Notes for judges

- Routes: OSRM/OpenStreetMap real road geometry.
- Origins: curated Riyadh emergency response dataset stored in `backend/data/city_data.json`. Ambulance bases are dispatch origins; hospitals are patient destinations.
- Traffic-light inventory: public routing APIs do not expose live traffic-light locations. S.I.R.S derives emergency signal-priority points from route maneuvers/intersections and labels them as control points.
- AI: Ollama local model for decision explanation, incident-specific report writing, communication log, and coordinator reasoning. If Ollama is offline, S.I.R.S falls back to deterministic report generation from the actual incident and agent outputs.
