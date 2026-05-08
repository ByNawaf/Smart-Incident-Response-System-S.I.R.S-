from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from enum import Enum


class IncidentType(str, Enum):
    TRAFFIC_ACCIDENT = "Traffic Accident"
    FIRE_INCIDENT = "Fire Incident"
    ROAD_BLOCKAGE = "Road Blockage"
    FUEL_SPILL = "Fuel Spill"
    MEDICAL_EMERGENCY = "Medical Emergency"


class Severity(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class WeatherCondition(str, Enum):
    CLEAR = "Clear"
    CLOUDY = "Cloudy"
    RAIN = "Rain"
    SANDSTORM = "Sandstorm"
    FOG = "Fog"
    EXTREME_HEAT = "Extreme Heat"


class TrafficDensity(str, Enum):
    LOW = "Low"
    MODERATE = "Moderate"
    HIGH = "High"
    CONGESTED = "Congested"


class IncidentCreate(BaseModel):
    type: str
    severity: str
    location_name: str
    latitude: float
    longitude: float
    time: Optional[str] = None
    traffic_density: str
    weather: str
    affected_vehicles: Optional[int] = 0
    affected_people: Optional[int] = 0
    description: Optional[str] = ""


class Incident(IncidentCreate):
    id: str
    status: str = "Active"
    created_at: str


class AgentResponse(BaseModel):
    agent_name: str
    status: str
    findings: Dict[str, Any]
    recommendation: str
    confidence_score: float
    risk_level: str


class FinalDecision(BaseModel):
    incident_id: str
    priority_level: str
    emergency_plan: Dict[str, Any]
    traffic_plan: Dict[str, Any]
    environment_plan: Dict[str, Any]
    cause_analysis: Dict[str, Any]
    prevention_recommendations: List[str]
    final_summary: str
    confidence_score: float
    response_timeline: List[Dict[str, Any]]
    agent_responses: List[Dict[str, Any]]


class AnalysisResponse(BaseModel):
    incident: Dict[str, Any]
    agent_responses: List[Dict[str, Any]]


class CoordinatorResponse(BaseModel):
    incident: Dict[str, Any]
    final_decision: Dict[str, Any]


class SettingsUpdate(BaseModel):
    # Ollama-only AI settings
    ai_provider: Optional[str] = "ollama"
    ollama_base_url: Optional[str] = None
    ollama_model: Optional[str] = "qwen3:8b"
    ollama_timeout: Optional[int] = 90
    ollama_enabled: Optional[bool] = True

    # Google Maps / Routes settings
    google_maps_browser_key: Optional[str] = None
    google_routes_api_key: Optional[str] = None
    google_places_api_key: Optional[str] = None
    google_maps_enabled: Optional[bool] = True
    google_places_enabled: Optional[bool] = True

