// ══════════════════════════════════════════════════════════════════════════════
// S.I.R.S — Incident-Aware Multi-Vehicle Animation Engine v2
// ══════════════════════════════════════════════════════════════════════════════

const VehicleAnimation = (() => {
  let _map = null;
  let _intervals = [];
  let _animLayers = [];
  let _animMarkers = [];
  let _paused = false;
  let _phase = 'idle';
  let _statusCallback = null;
  let _etaCallback = null;
  let _fleetCallback = null;   // NEW: fires with fleet progress updates

  // ── Interpolation ─────────────────────────────────────────────────────────
  function interp(a, b, t) { return [a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t]; }

  function buildPath(coords, steps) {
    if (!coords || coords.length < 2) return [];
    const pts = [];
    const segs = coords.length - 1;
    for (let i = 0; i < segs; i++) {
      const ss = Math.max(4, Math.floor(steps / segs));
      for (let s = 0; s < ss; s++) pts.push(interp(coords[i], coords[i+1], s/ss));
    }
    pts.push(coords[coords.length-1]);
    return pts;
  }

  // ── Layer management ──────────────────────────────────────────────────────
  function addLayer(l) { _animLayers.push(l); return l; }
  function addMarker(m) { _animMarkers.push(m); return m; }

  function removeAll() {
    _intervals.forEach(id => clearInterval(id));
    _intervals = [];
    _animLayers.forEach(l => { try { _map && _map.removeLayer(l); } catch(_){} });
    _animMarkers.forEach(m => { try { _map && _map.removeLayer(m); } catch(_){} });
    _animLayers = []; _animMarkers = [];
  }

  // ── Icon builders ─────────────────────────────────────────────────────────
  function evIcon(emoji, color, pulse) {
    const ring = pulse
      ? `<div style="position:absolute;inset:-6px;border-radius:50%;border:2px solid ${color};animation:va-pulse 1s ease infinite;opacity:0.6"></div>` : '';
    return L.divIcon({
      className: '',
      html: `<div style="position:relative;width:44px;height:44px">
        ${ring}
        <div style="width:44px;height:44px;background:${color}33;border:3px solid ${color};border-radius:50%;
          display:flex;align-items:center;justify-content:center;font-size:22px;
          box-shadow:0 0 22px ${color}bb;animation:va-glow 1.5s ease infinite">${emoji}</div>
      </div>`,
      iconSize:[44,44], iconAnchor:[22,22]
    });
  }

  function civIcon(color) {
    return L.divIcon({
      className:'',
      html:`<div style="width:16px;height:16px;background:${color}cc;border:2px solid ${color};
        border-radius:3px;display:flex;align-items:center;justify-content:center;font-size:8px">🚗</div>`,
      iconSize:[16,16], iconAnchor:[8,8]
    });
  }

  function hazardIcon(radiusM) {
    return `<div style="position:relative;display:flex;align-items:center;justify-content:center">
      <div style="font-size:28px">⚠️</div>
      <div style="position:absolute;bottom:-14px;background:#ef444499;color:#fff;font-size:9px;
        font-weight:900;padding:2px 6px;border-radius:4px;white-space:nowrap">⚠️ ${radiusM}m zone</div>
    </div>`;
  }

  // ── Animated polyline ─────────────────────────────────────────────────────
  function drawRoute(coords, color, weight, dash, label, glow) {
    if (!coords || coords.length < 2) return;
    if (glow) addLayer(L.polyline(coords,{color,weight:glow,opacity:0.12}).addTo(_map));
    const l = L.polyline(coords,{color,weight,opacity:0.95,dashArray:dash}).addTo(_map);
    if (label) l.bindPopup(label);
    addLayer(l);
    return l;
  }

  // ── Move marker along path ────────────────────────────────────────────────
  function moveAlongPath(marker, path, stepMs, onStep, onDone) {
    let idx = 0;
    const iv = setInterval(() => {
      if (_paused) return;
      if (idx >= path.length) { clearInterval(iv); if (onDone) onDone(); return; }
      marker.setLatLng(path[idx]);
      if (onStep) onStep(idx, path.length);
      idx++;
    }, stepMs);
    _intervals.push(iv);
    return iv;
  }

  // ── Civilian cars ─────────────────────────────────────────────────────────
  function spawnCivilian(route, color, stepMs, delay) {
    setTimeout(() => {
      if (!_map) return;
      const path = buildPath(route, 60);
      if (path.length < 2) return;
      const m = L.marker(path[0],{icon:civIcon(color),zIndexOffset:-10}).addTo(_map);
      addMarker(m);
      moveAlongPath(m, path, stepMs, null, () => { try{_map&&_map.removeLayer(m);}catch(_){} });
    }, delay);
  }

  // ── BEFORE scene ──────────────────────────────────────────────────────────
  function showBeforeScene(data) {
    removeAll(); _phase = 'before';
    if (_statusCallback) _statusCallback('before');

    const inc = data.incidentLatLng;
    const congestedSegs = data.congestedSegments || [];
    const normalRoute   = data.normalRoute || [];
    const altRoutes     = data.altRoutes || [];
    const isHazard      = data.isHazard;
    const hazardRadius  = data.hazardRadius || 0;

    // Hazard zone overlay
    if (isHazard && inc && hazardRadius > 0) {
      addLayer(L.circle(inc, {
        radius: hazardRadius, color:'#ef4444', fillColor:'#ef4444',
        fillOpacity:0.12, weight:2, dashArray:'6,4'
      }).addTo(_map).bindPopup('⚠️ Hazard Exclusion Zone'));
      addMarker(L.marker(inc, {
        icon: L.divIcon({className:'', html: hazardIcon(hazardRadius), iconSize:[60,60], iconAnchor:[30,30]})
      }).addTo(_map));
    }

    // Congested road
    if (congestedSegs.length >= 2) {
      drawRoute(congestedSegs,'#ef4444',8,null,'🔴 Congested Road');
      addLayer(L.polyline(congestedSegs,{color:'#ff0000',weight:14,opacity:0.08}).addTo(_map));
    }

    // Normal (blocked) route
    if (normalRoute.length >= 2)
      drawRoute(normalRoute,'#64748b',4,'8,6','🛤️ Normal Route (Congested)');

    // Incident marker
    if (inc && !isHazard)
      addMarker(L.marker(inc,{icon:makeIcon('💥','#ef4444',42),zIndexOffset:100})
        .addTo(_map).bindPopup('<b style="color:#ef4444">⚡ Active Incident</b>'));

    // Show ALL fleet stuck
    (data.fleet || []).forEach((v,i) => {
      const start = [v.latitude, v.longitude];
      const m = L.marker(start, {icon:evIcon(v.emoji, '#ef4444', true), zIndexOffset:200+i})
        .addTo(_map).bindPopup(`<b style="color:#ef4444">${v.emoji} ${v.label} — DELAYED</b><br>Normal ETA: <b>${v.normalEta} min</b>`);
      addMarker(m);
      let vis=true;
      const fiv = setInterval(()=>{ if(_phase!=='before'){clearInterval(fiv);return;} m.setOpacity(vis?1:0.3); vis=!vis; },800+i*100);
      _intervals.push(fiv);
    });

    // Civilian traffic jammed
    altRoutes.forEach((r,i) => {
      for (let j=0;j<3;j++) spawnCivilian(r,'#ef4444',150,i*800+j*350);
    });
    if (normalRoute.length>=2) {
      for (let j=0;j<5;j++) spawnCivilian(normalRoute,'#f97316',200,j*450);
    }
  }

  // ── AFTER scene — multi-vehicle ───────────────────────────────────────────
  function showAfterScene(data, onAllArrived) {
    removeAll(); _phase = 'after';
    if (_statusCallback) _statusCallback('after');

    const inc = data.incidentLatLng;
    const altRoutes    = data.altRoutes || [];
    const congestedSegs= data.congestedSegments || [];
    const isHazard     = data.isHazard;
    const hazardRadius = data.hazardRadius || 0;
    const fleet        = data.fleet || [];

    // Hazard zone
    if (isHazard && inc && hazardRadius > 0) {
      addLayer(L.circle(inc, {
        radius: hazardRadius, color:'#f97316', fillColor:'#f97316',
        fillOpacity:0.10, weight:2, dashArray:'5,5'
      }).addTo(_map).bindPopup('⚠️ Hazard Zone — Exclusion Active'));
      addMarker(L.marker(inc, {
        icon: L.divIcon({className:'', html: hazardIcon(hazardRadius), iconSize:[60,60], iconAnchor:[30,30]})
      }).addTo(_map));
    }

    // Cleared/blocked congested road
    if (congestedSegs.length >= 2)
      drawRoute(congestedSegs,'#374151',5,'4,8','🚧 Cleared for Emergency');

    // Incident marker
    if (inc && !isHazard)
      addMarker(L.marker(inc,{icon:makeIcon('💥','#ef4444',42),zIndexOffset:100})
        .addTo(_map).bindPopup('<b style="color:#ef4444">⚡ Active Incident</b>'));

    // Alt routes (civilian reroute)
    altRoutes.forEach(r => {
      if (r.length >= 2) drawRoute(r,'#10b981',3,'8,5','🔀 Civilian Reroute',8);
    });
    altRoutes.forEach((r,i) => {
      for (let j=0;j<4;j++) spawnCivilian(r,'#10b981',85,i*600+j*200);
    });

    // ── Animate each fleet vehicle ──────────────────────────────────────────
    const VEHICLE_COLORS = {
      'Ambulance':     '#06b6d4',
      'Police Car':    '#3b82f6',
      'Traffic Unit':  '#22c55e',
      'Road Service':  '#eab308',
      'Fire Truck':    '#f97316',
      'Civil Defense': '#8b5cf6',
    };
    const ROUTE_DASH = {
      'primary':   '14,4',
      'secondary': '10,6',
      'tertiary':  '6,8',
      'support':   '4,10',
    };
    const GLOW = { 'primary':18, 'secondary':14, 'tertiary':10, 'support':10 };

    let arrivedCount = 0;
    const primaryV = fleet.find(v=>v.role==='primary') || fleet[0];

    fleet.forEach((v, i) => {
      const color = VEHICLE_COLORS[v.type] || '#06b6d4';
      const route = v.priorityRoute || [];
      const stagger = i * 1200; // vehicles stagger their departure

      // Draw priority corridor for this vehicle
      if (route.length >= 2) {
        setTimeout(() => {
          drawRoute(route, color, 5, ROUTE_DASH[v.role]||'10,5',
            `⚡ ${v.label} — Priority Route`, GLOW[v.role]||12);
        }, stagger);
      }

      // Traffic signal markers (only primary to avoid clutter)
      if (v.role === 'primary') {
        (v.priorityIntersections || []).forEach(int => {
          const c = {Critical:'#ef4444',High:'#f97316',Medium:'#eab308'}[int.priorityLevel]||'#f97316';
          addMarker(L.marker([int.lat,int.lng],{
            icon:L.divIcon({className:'',
              html:`<div style="width:26px;height:26px;background:${c}33;border:2px solid ${c};
                border-radius:5px;display:flex;align-items:center;justify-content:center;font-size:13px;
                box-shadow:0 0 10px ${c}aa">🚦</div>`,
              iconSize:[26,26],iconAnchor:[13,13]})
          }).addTo(_map).bindPopup(`<b style="color:${c}">🚦 ${int.name}</b><br>${int.action}`));
        });
      }

      // Animate the vehicle marker
      setTimeout(() => {
        if (!_map) return;
        const start = [v.latitude, v.longitude];
        const path = buildPath(route.length>=2 ? route : [start, inc], 100);
        const evM = L.marker(start, {icon:evIcon(v.emoji,color,true), zIndexOffset:300+i})
          .addTo(_map)
          .bindPopup(`<b style="color:${color}">${v.emoji} ${v.label}</b><br>
            Priority ETA: <b>${v.priorityEta} min</b><br>
            Normal ETA: <s>${v.normalEta} min</s><br>
            Saves: <b style="color:#10b981">${v.timeSaved} min</b>`);
        addMarker(evM);

        const stepMs = Math.max(30, Math.floor((v.priorityEta*60*1000)/path.length/10));
        const isPrimary = (v.role === 'primary' || i===0);

        moveAlongPath(evM, path, stepMs,
          (idx, total) => {
            if (isPrimary) {
              const progress = idx/total;
              const eta = Math.round(v.priorityEta*(1-progress));
              const msg = progress>0.8 ? 'Approaching incident' : progress<0.1 ? 'Dispatched' : 'En route — priority corridor';
              if (_etaCallback) _etaCallback(eta, msg, v);
            }
            if (_fleetCallback) _fleetCallback(i, idx/total, v);
          },
          () => {
            arrivedCount++;
            evM.setIcon(evIcon('✅','#10b981',false));
            evM.setPopupContent(`<b style="color:#10b981">✅ ${v.label} ARRIVED</b><br>
              Saved: <b>${v.timeSaved} min</b>`);
            if (isPrimary && _etaCallback) _etaCallback(0,'Arrived',v);
            if (arrivedCount === fleet.length && onAllArrived) onAllArrived();
          }
        );
      }, stagger);
    });
  }

  // ── Public buildSceneData ─────────────────────────────────────────────────
  function buildSceneData(incident, agentResponses) {
    let emergency=null, traffic=null;
    (agentResponses||[]).forEach(a=>{
      if(a.agent_name==='Emergency Agent') emergency=a;
      if(a.agent_name==='Traffic Agent') traffic=a;
    });

    const inc = [incident.latitude, incident.longitude];
    let altRoutes=[], congestedSegs=[], fleet=[];
    let isHazard=false, hazardRadius=0, hazardRadiusDeg=0;
    let primaryEta={normal:12,priority:5};

    if (emergency && emergency.findings) {
      const ef = emergency.findings;
      fleet = ef.dispatched_fleet || [];
      isHazard = ef.is_hazard_incident || false;
      hazardRadius = ef.hazard_radius_m || 0;
      hazardRadiusDeg = ef.hazard_radius_deg || 0;
      const pv = fleet.find(v=>v.role==='primary') || fleet[0];
      if (pv) { primaryEta = {normal:pv.normalEta||12, priority:pv.priorityEta||5}; }
      if (!congestedSegs.length && ef.ev_congested_segments && ef.ev_congested_segments.length)
        congestedSegs = ef.ev_congested_segments;
    }

    if (traffic && traffic.findings) {
      const tf = traffic.findings;
      if (tf.alt_route_coords && tf.alt_route_coords.length>=2) altRoutes.push(tf.alt_route_coords);
      const rp = tf.rerouting_plans || [];
      rp.forEach(p=>{ if(p.waypoints&&p.waypoints.length>=2) altRoutes.push(p.waypoints); });
      if (!congestedSegs.length && tf.blocked_coords && tf.blocked_coords.length>=2)
        congestedSegs = tf.blocked_coords;
    }

    // Build fallback fleet if empty
    if (!fleet.length) {
      const evStart = [inc[0]+0.025, inc[1]-0.03];
      fleet = [{
        vehicleIndex:0, role:'primary', label:'Ambulance', type:'Ambulance', emoji:'🚑',
        color:'#06b6d4', unitId:'AMB-01',
        latitude:evStart[0], longitude:evStart[1],
        normalEta:12, priorityEta:5, timeSaved:7,
        priorityRoute:[evStart,[inc[0]+0.015,inc[1]-0.015],inc],
        normalRoute:[evStart,[inc[0]+0.01,inc[1]+0.01],inc],
        congestedSegments:[[inc[0]+0.01,inc[1]+0.01],inc],
        clearedSegments:[[evStart[0]+0.01,evStart[1]-0.01],[inc[0]+0.005,inc[1]-0.005]],
        priorityIntersections:[],
      }];
    }

    if (!congestedSegs.length) congestedSegs = [[inc[0]+0.01,inc[1]+0.01],[inc[0]-0.005,inc[1]+0.015],inc];
    if (!altRoutes.length) altRoutes = [
      [[inc[0]+0.03,inc[1]-0.04],[inc[0]+0.02,inc[1]-0.02],[inc[0]+0.01,inc[1]-0.01]],
      [[inc[0]-0.02,inc[1]-0.035],[inc[0]-0.01,inc[1]-0.02],[inc[0],inc[1]-0.01]]
    ];

    return {
      incidentLatLng: inc,
      fleet,
      isHazard, hazardRadius, hazardRadiusDeg,
      normalRoute: (fleet[0]&&fleet[0].normalRoute)||[],
      congestedSegments: congestedSegs,
      altRoutes,
      normalEta: primaryEta.normal,
      priorityEta: primaryEta.priority,
      // Legacy single-vehicle shims
      evStartLatLng: fleet[0] ? [fleet[0].latitude,fleet[0].longitude] : [inc[0]+0.025,inc[1]-0.03],
      priorityRoute: (fleet[0]&&fleet[0].priorityRoute)||[],
      priorityIntersections: (fleet[0]&&fleet[0].priorityIntersections)||[],
    };
  }

  // ── Public API ────────────────────────────────────────────────────────────
  function init(mapRef) { _map = mapRef; }
  function setStatusCallback(fn) { _statusCallback = fn; }
  function setEtaCallback(fn)    { _etaCallback = fn; }
  function setFleetCallback(fn)  { _fleetCallback = fn; }
  function pause()   { _paused = true; }
  function resume()  { _paused = false; }
  function isPaused(){ return _paused; }
  function getPhase(){ return _phase; }
  function reset() {
    removeAll(); _phase='idle'; _paused=false;
    if (_statusCallback) _statusCallback('idle');
    if (_etaCallback) _etaCallback(null,'Idle',null);
  }

  return { init, setStatusCallback, setEtaCallback, setFleetCallback,
           showBeforeScene, showAfterScene, buildSceneData,
           pause, resume, isPaused, reset, getPhase };
})();

// ── Inject animation CSS ──────────────────────────────────────────────────────
(function injectVAStyles(){
  if (document.getElementById('va-styles')) return;
  const s = document.createElement('style');
  s.id = 'va-styles';
  s.textContent = `
    @keyframes va-pulse {
      0%,100%{transform:scale(1);opacity:0.7;} 50%{transform:scale(1.6);opacity:0;}
    }
    @keyframes va-glow {
      0%,100%{box-shadow:0 0 16px #06b6d4aa;} 50%{box-shadow:0 0 32px #06b6d4ff,0 0 60px #06b6d466;}
    }
    .va-status-pill{display:inline-flex;align-items:center;gap:6px;padding:4px 12px;border-radius:20px;
      font-size:11px;font-weight:700;letter-spacing:0.5px;white-space:nowrap;transition:all 0.3s;}
    .va-pill-idle   {background:rgba(71,85,105,0.35);color:#94a3b8;border:1px solid rgba(71,85,105,0.4);}
    .va-pill-active {background:rgba(6,182,212,0.2);color:#06b6d4;border:1px solid rgba(6,182,212,0.5);}
    .va-pill-green  {background:rgba(16,185,129,0.2);color:#10b981;border:1px solid rgba(16,185,129,0.4);}
    .va-pill-red    {background:rgba(239,68,68,0.2);color:#ef4444;border:1px solid rgba(239,68,68,0.4);}
    .va-pill-orange {background:rgba(249,115,22,0.2);color:#f97316;border:1px solid rgba(249,115,22,0.4);}
    .va-pill-purple {background:rgba(139,92,246,0.2);color:#8b5cf6;border:1px solid rgba(139,92,246,0.4);}
    .sim-control-panel{background:linear-gradient(135deg,rgba(13,21,38,0.97),rgba(17,29,53,0.97));
      border:1px solid rgba(6,182,212,0.25);border-radius:12px;overflow:hidden;}
    .sim-control-header{padding:16px 20px;border-bottom:1px solid rgba(6,182,212,0.15);
      background:rgba(6,182,212,0.06);display:flex;align-items:center;gap:10px;}
    .sim-control-header h3{font-size:14px;font-weight:700;color:#e2e8f0;}
    .sim-control-body{padding:20px;}
    .sim-btn-row{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px;}
    .sim-btn{padding:8px 16px;border-radius:8px;font-size:12px;font-weight:700;border:none;
      cursor:pointer;transition:all 0.2s;display:inline-flex;align-items:center;gap:6px;}
    .sim-btn:hover{transform:translateY(-1px);filter:brightness(1.15);}
    .sim-btn:disabled{opacity:0.4;cursor:not-allowed;transform:none;}
    .sim-btn-before{background:linear-gradient(135deg,#dc2626,#ef4444);color:#fff;box-shadow:0 4px 14px rgba(239,68,68,0.35);}
    .sim-btn-after {background:linear-gradient(135deg,#0369a1,#06b6d4);color:#fff;box-shadow:0 4px 14px rgba(6,182,212,0.35);}
    .sim-btn-pause {background:linear-gradient(135deg,#d97706,#f59e0b);color:#fff;box-shadow:0 4px 14px rgba(245,158,11,0.35);}
    .sim-btn-reset {background:rgba(99,179,237,0.12);color:#94a3b8;border:1px solid rgba(99,179,237,0.2);}
    .sim-btn-replay{background:linear-gradient(135deg,#7c3aed,#8b5cf6);color:#fff;box-shadow:0 4px 14px rgba(139,92,246,0.35);}
    .sim-eta-display{background:linear-gradient(135deg,rgba(6,182,212,0.1),rgba(3,105,161,0.1));
      border:1px solid rgba(6,182,212,0.3);border-radius:10px;padding:14px;text-align:center;margin-bottom:12px;}
    .sim-eta-number{font-size:38px;font-weight:900;font-family:'JetBrains Mono',monospace;
      background:linear-gradient(135deg,#06b6d4,#3b82f6);-webkit-background-clip:text;
      -webkit-text-fill-color:transparent;background-clip:text;}
    .sim-eta-label{font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-top:2px;}
    .sim-ev-status{font-size:12px;font-weight:700;text-align:center;padding:8px;border-radius:8px;
      background:rgba(6,182,212,0.08);color:#06b6d4;border:1px solid rgba(6,182,212,0.2);margin-bottom:10px;}
    .sim-phase-bar{display:flex;gap:0;border-radius:8px;overflow:hidden;border:1px solid rgba(99,179,237,0.15);margin-bottom:12px;}
    .sim-phase-seg{flex:1;padding:7px;text-align:center;font-size:11px;font-weight:700;
      background:rgba(71,85,105,0.2);color:#475569;transition:all 0.4s;}
    .sim-phase-seg.active-before{background:rgba(239,68,68,0.2);color:#ef4444;}
    .sim-phase-seg.active-after {background:rgba(6,182,212,0.2);color:#06b6d4;}
    .sim-phase-seg.active-arrived{background:rgba(16,185,129,0.2);color:#10b981;}
    .fleet-card{background:rgba(6,182,212,0.04);border:1px solid rgba(6,182,212,0.1);
      border-radius:8px;padding:8px 12px;display:flex;align-items:center;gap:8px;margin-bottom:6px;transition:all 0.3s;}
    .fleet-card.fleet-active{border-color:rgba(6,182,212,0.4);background:rgba(6,182,212,0.08);}
    .fleet-card.fleet-arrived{border-color:rgba(16,185,129,0.4);background:rgba(16,185,129,0.06);}
    .fleet-card.fleet-hazard{border-color:rgba(249,115,22,0.4);background:rgba(249,115,22,0.06);}
    .fleet-progress{flex:1;height:4px;background:rgba(99,179,237,0.15);border-radius:2px;overflow:hidden;}
    .fleet-progress-fill{height:100%;border-radius:2px;transition:width 0.4s;}
    .hazard-badge{display:inline-flex;align-items:center;gap:4px;padding:3px 8px;border-radius:6px;
      font-size:10px;font-weight:700;background:rgba(239,68,68,0.2);color:#ef4444;
      border:1px solid rgba(239,68,68,0.4);}
  `;
  document.head.appendChild(s);
})();

window.VehicleAnimation = VehicleAnimation;
