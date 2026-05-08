from datetime import datetime

DEMO_INCIDENT = {
    "type": "Fuel Spill",
    "severity": "High",
    "location_name": "King Fahd Road - Kingdom Centre",
    "latitude": 24.7114,
    "longitude": 46.6744,
    "traffic_density": "Congested",
    "weather": "Extreme Heat",
    "affected_vehicles": 4,
    "affected_people": 12,
    "description": "Fuel tanker collision caused a diesel spill on a major Riyadh corridor. Civil Defense, fire, police, and ambulance units are required to isolate ignition sources, reroute traffic, and treat exposed civilians."
}


DEMO_INCIDENT_ID = "DEMO-RIYADH-LIVE"


def get_demo_incident() -> dict:
    demo = DEMO_INCIDENT.copy()
    # A stable demo ID keeps Dashboard, Judges View, Reports, and Agents pages
    # aligned on the same hackathon scenario instead of creating different
    # one-off demo records in each page.
    demo["id"] = DEMO_INCIDENT_ID
    demo["is_demo"] = True
    demo["status"] = "Active"
    demo["created_at"] = datetime.now().isoformat()
    demo["time"] = datetime.now().strftime("%H:%M")
    return demo
