import sys
sys.path.insert(0, '.')
from models.schemas import IncidentCreate, SettingsUpdate
from services import data_service, demo_service
from agents import traffic_agent, emergency_agent, environment_agent, analysis_agent, coordinator_agent

print("All imports OK")
city = data_service.load_city_data()
print(f"City: {len(city['hospitals'])} hospitals, {len(city['fire_stations'])} stations")
demo = demo_service.get_demo_incident()
print(f"Demo: {demo['type']} - {demo['severity']}")
agents_out = [
    traffic_agent.run(demo, city),
    emergency_agent.run(demo, city),
    environment_agent.run(demo, city),
    analysis_agent.run(demo, city),
]
for a in agents_out:
    print(f"  {a['agent_name']}: {a['risk_level']} risk, {a['confidence_score']} confidence")
final = coordinator_agent.run(demo, agents_out, city)
print(f"Coordinator: {final['priority_level']}")
print(f"Confidence:  {final['confidence_score']}")
print(f"Timeline:    {len(final['response_timeline'])} steps")
print("PIPELINE TEST PASSED")
