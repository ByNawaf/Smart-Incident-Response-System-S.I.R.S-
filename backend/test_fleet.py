import requests, json

r = requests.post('http://localhost:8000/api/demo/run', timeout=30)
d = r.json()

inc = d.get('incident', {})
print(f"Incident: {inc.get('type')} | Severity: {inc.get('severity')}")

ef = next((a for a in d['agent_responses'] if a['agent_name'] == 'Emergency Agent'), None)
tf = next((a for a in d['agent_responses'] if a['agent_name'] == 'Traffic Agent'), None)

if ef:
    finds = ef['findings']
    fleet = finds.get('dispatched_fleet', [])
    print(f"\nFleet count     : {len(fleet)}")
    print(f"Is hazard       : {finds.get('is_hazard_incident')}")
    print(f"Hazard radius   : {finds.get('hazard_radius_m')} m")
    print(f"Ambulance origin: {(finds.get('closest_ambulance_origin') or {}).get('name', 'N/A')}")
    print(f"Hospital dest.  : {(finds.get('destination_hospital') or {}).get('name', 'N/A')}")
    print(f"Dispatch logic  : {' | '.join(finds.get('dispatch_reasoning', [])[:3])}")
    for v in fleet:
        pr = v.get('priorityRoute', [])
        nr = v.get('normalRoute', [])
        print(f"  [{v['role']:10}] {v['emoji']} {v['label']:35} | ETA {v['normalEta']:5}→{v['priorityEta']} min | pRoute:{len(pr)} pts | nRoute:{len(nr)} pts | staged:{v.get('hazardStaged')}")

if tf:
    tfinds = tf['findings']
    alts = tfinds.get('rerouting_plans', [])
    print(f"\nTraffic alts    : {len(alts)}")
    print(f"Blocked road    : {tfinds.get('blocked_road')}")
    print(f"Alt route pts   : {len(tfinds.get('alt_route_coords', []))}")

print("\n✅ API test complete")
