// ── Agent Card Renderer ────────────────────────────────────────────────────────
var AGENT_META = {
  'Camera Vision Agent': { icon: '📹', cls: 'traffic',     color: '#22d3ee' },
  'Traffic Agent':      { icon: '🚦', cls: 'traffic',     color: '#3b82f6' },
  'Emergency Agent':    { icon: '🚑', cls: 'emergency',   color: '#ef4444' },
  'Environment Agent':  { icon: '🌿', cls: 'environment', color: '#10b981' },
  'Analysis Agent':     { icon: '🔬', cls: 'analysis',    color: '#8b5cf6' },
  'Coordinator Agent':  { icon: '🎯', cls: 'coordinator', color: '#f97316' },
};

function congestionColor(level) {
  return { 'Low': '#10b981', 'Moderate': '#eab308', 'Medium': '#eab308', 'High': '#f97316', 'Congested': '#ef4444', 'Critical': '#ef4444' }[level] || '#94a3b8';
}

function renderAgentCard(agent, container) {
  var meta = AGENT_META[agent.agent_name] || { icon: '🤖', cls: 'analysis', color: '#94a3b8' };
  var f = agent.findings || {};
  var conf = Math.round((agent.confidence_score || 0) * 100);
  var statusCls = { Waiting: 'badge-waiting', Analyzing: 'badge-analyzing', Completed: 'badge-completed' }[agent.status] || 'badge-waiting';

  var findingRows = '';
  if (agent.agent_name === 'Camera Vision Agent') {
    findingRows =
      '<div class="agent-finding-row"><span class="finding-label">Camera</span><span class="finding-value">' + (f.camera_id || '—') + '</span></div>' +
      '<div class="agent-finding-row"><span class="finding-label">Detected</span><span class="finding-value">' + (f.incident_type || '—') + '</span></div>' +
      '<div class="agent-finding-row"><span class="finding-label">Blocked Lanes</span><span class="finding-value">' + (f.blocked_lanes || 0) + '/' + (f.lane_count || '—') + '</span></div>' +
      '<div class="agent-finding-row"><span class="finding-label">Speed Drop</span><span class="finding-value">' + Math.round(f.speed_drop_percent || 0) + '%</span></div>' +
      '<div class="agent-finding-row"><span class="finding-label">Evidence</span><span class="finding-value">' + ((f.evidence || []).length) + ' cues</span></div>';

  } else if (agent.agent_name === 'Traffic Agent') {
    findingRows =
      '<div class="agent-finding-row"><span class="finding-label">Congestion</span><span class="finding-value">' + (f.congestion_level || '—') + '</span></div>' +
      '<div class="agent-finding-row"><span class="finding-label">Affected Roads</span><span class="finding-value">' + (f.alternative_routes || []).length + ' alt routes</span></div>' +
      '<div class="agent-finding-row"><span class="finding-label">Est. Delay</span><span class="finding-value">' + (f.estimated_delay_minutes || '—') + ' min</span></div>' +
      '<div class="agent-finding-row"><span class="finding-label">Delay Reduction</span><span class="finding-value text-green">-' + (f.delay_reduction_minutes || '—') + ' min</span></div>' +
      // Emergency corridor support from Traffic Agent
      '<div class="agent-finding-row" style="margin-top:6px;padding-top:6px;border-top:1px solid rgba(255,255,255,0.06)">' +
      '<span class="finding-label" style="color:#06b6d4">Signal Priority</span>' +
      '<span class="finding-value" style="color:#06b6d4">' + (f.signal_recommendations ? f.signal_recommendations.length + ' actions' : '—') + '</span></div>' +
      '<div class="agent-finding-row"><span class="finding-label" style="color:#06b6d4">Corridor Support</span>' +
      '<span class="finding-value" style="color:#06b6d4">✅ Active</span></div>';

  } else if (agent.agent_name === 'Emergency Agent') {
    var sv = f.selected_vehicle || {};
    var evCong = sv.currentCongestionLevel || f.ev_congestion_level || '—';
    var evCongColor = congestionColor(evCong);
    var stuckBadge = sv.stuckInCongestion
      ? '<span style="background:#ef44441a;border:1px solid #ef4444;color:#ef4444;font-size:10px;font-weight:700;padding:1px 6px;border-radius:4px">⚠️ STUCK</span>'
      : '<span style="background:#10b9811a;border:1px solid #10b981;color:#10b981;font-size:10px;font-weight:700;padding:1px 6px;border-radius:4px">🟢 MOVING</span>';
    var normalEta = sv.normalEta || f.ev_normal_eta || '—';
    var priorityEta = sv.priorityEta || f.ev_priority_eta || '—';
    var timeSaved = sv.timeSaved || f.ev_time_saved || '—';
    var routeStatus = sv.routeStatus || f.ev_route_status || '—';
    var unitId = sv.unitId || '—';
    var unitType = sv.type || '—';
    var distance = sv.distanceToIncident || f.ev_distance_km || '—';

    findingRows =
      // Standard dispatch info
      '<div class="agent-finding-row"><span class="finding-label">Priority</span><span class="finding-value" style="color:#ef4444">' + (f.priority_level || '—') + '</span></div>' +
      '<div class="agent-finding-row"><span class="finding-label">Units Dispatched</span><span class="finding-value">' + (f.total_units || '—') + '</span></div>' +
      '<div class="agent-finding-row"><span class="finding-label">Station ETA</span><span class="finding-value">' + (f.min_eta_minutes || '—') + ' min</span></div>' +
      // EV ETA Optimization section
      '<div style="margin-top:8px;padding:8px;background:rgba(6,182,212,0.06);border:1px solid rgba(6,182,212,0.2);border-radius:6px">' +
      '<div style="font-size:10px;font-weight:800;color:#06b6d4;letter-spacing:0.05em;margin-bottom:6px">⚡ EV ETA OPTIMIZATION</div>' +
      '<div class="agent-finding-row"><span class="finding-label">Selected Unit</span><span class="finding-value" style="font-weight:700">' + unitType + ' ' + unitId + '</span></div>' +
      '<div class="agent-finding-row"><span class="finding-label">Congestion</span>' +
        '<span class="finding-value" style="color:' + evCongColor + ';font-weight:700">' + evCong + ' &nbsp;' + stuckBadge + '</span></div>' +
      '<div class="agent-finding-row"><span class="finding-label">Distance</span><span class="finding-value">' + distance + ' km</span></div>' +
      '<div class="agent-finding-row"><span class="finding-label">Normal ETA</span><span class="finding-value" style="color:#94a3b8;text-decoration:line-through">' + normalEta + ' min</span></div>' +
      '<div class="agent-finding-row"><span class="finding-label">Priority ETA</span><span class="finding-value" style="color:#10b981;font-weight:900;font-size:13px">' + priorityEta + ' min</span></div>' +
      '<div class="agent-finding-row"><span class="finding-label">⏱️ Time Saved</span><span class="finding-value" style="color:#06b6d4;font-weight:900;font-size:13px">-' + timeSaved + ' min</span></div>' +
      '<div class="agent-finding-row"><span class="finding-label">Route Status</span><span class="finding-value" style="color:#f97316;font-size:11px">' + routeStatus + '</span></div>' +
      '</div>';

  } else if (agent.agent_name === 'Environment Agent') {
    findingRows =
      '<div class="agent-finding-row"><span class="finding-label">Env. Risk</span><span class="finding-value">' + (f.environmental_risk || '—') + '</span></div>' +
      '<div class="agent-finding-row"><span class="finding-label">AQI Impact</span><span class="finding-value">' + (f.air_quality_impact || '—') + '</span></div>' +
      '<div class="agent-finding-row"><span class="finding-label">Safety Zone</span><span class="finding-value">' + (f.affected_radius_m || '—') + 'm</span></div>' +
      '<div class="agent-finding-row"><span class="finding-label">Fire Risk</span><span class="finding-value">' + (f.fire_risk || '—') + '</span></div>';

  } else if (agent.agent_name === 'Analysis Agent') {
    var cause = (f.primary_cause || '—').substring(0, 28);
    findingRows =
      '<div class="agent-finding-row"><span class="finding-label">Primary Cause</span><span class="finding-value" style="font-size:11px">' + cause + '</span></div>' +
      '<div class="agent-finding-row"><span class="finding-label">Probability</span><span class="finding-value">' + (f.primary_probability || '—') + '%</span></div>' +
      '<div class="agent-finding-row"><span class="finding-label">Factor Type</span><span class="finding-value">' + (f.primary_factor_type || '—') + '</span></div>' +
      '<div class="agent-finding-row"><span class="finding-label">Risk Factors</span><span class="finding-value">' + (f.risk_factors || []).length + '</span></div>';
  }

  var card = document.createElement('div');
  card.className = 'agent-card ' + (agent.status === 'Waiting' ? 'waiting' : agent.status === 'Analyzing' ? 'analyzing' : 'completed') + ' fade-in-up';
  var innerHtml = '<div class="agent-card-header">' +
    '<div class="agent-icon ' + meta.cls + '">' + meta.icon + '</div>' +
    '<div><div class="agent-name">' + agent.agent_name + '</div><div class="text-xs text-muted">Multi-Agent System</div></div>' +
    '<span class="agent-status-badge ' + statusCls + '">' + agent.status + '</span>' +
    '</div>';

  if (agent.status === 'Analyzing') {
    innerHtml += '<div class="flex-gap-8 mb-8"><div class="spinner"></div><span class="text-sm text-muted">Processing incident data...</span></div>';
  }
  if (agent.status === 'Completed') {
    innerHtml +=
      '<div class="agent-findings">' + findingRows + '</div>' +
      '<div class="mt-12">' + riskBadge(agent.risk_level) +
      '<div class="confidence-bar mt-8"><div class="confidence-fill" style="width:' + conf + '%"></div></div>' +
      '<div class="flex-between mt-4"><span class="text-xs text-muted">Confidence</span><span class="text-xs font-mono text-cyan">' + conf + '%</span></div>' +
      '</div>' +
      '<div class="alert alert-info mt-12" style="padding:8px 12px"><span style="font-size:10px;line-height:1.5">' + agent.recommendation + '</span></div>';
  }
  if (agent.status === 'Waiting') {
    innerHtml += '<div class="text-xs text-muted" style="padding-top:8px">Standby — waiting for incident data...</div>';
  }

  card.innerHTML = innerHtml;
  container.appendChild(card);
  return card;
}

function renderAllAgents(agentResponses, containerId) {
  var container = document.getElementById(containerId);
  if (!container) return;
  container.innerHTML = '';
  agentResponses.forEach(function(a) { renderAgentCard(a, container); });
}

// ── EV ETA Dashboard Panel ────────────────────────────────────────────────────
function renderEvEtaPanel(agentResponses, containerId) {
  var container = document.getElementById(containerId);
  if (!container) return;
  var emergency = null;
  agentResponses.forEach(function(a) { if (a.agent_name === 'Emergency Agent') emergency = a; });
  if (!emergency) { container.innerHTML = ''; return; }

  var f = emergency.findings || {};
  var sv = f.selected_vehicle || {};
  if (!sv.unitId && !f.ev_normal_eta) { container.innerHTML = ''; return; }

  var evCong = sv.currentCongestionLevel || f.ev_congestion_level || 'Unknown';
  var evCongColor = congestionColor(evCong);
  var normalEta = sv.normalEta || f.ev_normal_eta || '—';
  var priorityEta = sv.priorityEta || f.ev_priority_eta || '—';
  var timeSaved = sv.timeSaved || f.ev_time_saved || '—';
  var routeStatus = sv.routeStatus || f.ev_route_status || '—';
  var unitId = sv.unitId || '—';
  var unitType = sv.type || '—';
  var distance = sv.distanceToIncident || f.ev_distance_km || '—';
  var stuckMsg = sv.stuckInCongestion ? ('⚠️ Stuck in ' + evCong + ' congestion') : ('🟢 En route — ' + evCong + ' congestion');
  var routeProvider = sv.routeProvider === 'google_routes' ? 'Google Routes API' : (sv.routeProvider === 'osrm' ? 'OSRM / OpenStreetMap' : 'Fallback Route');
  var routeProviderColor = (sv.routeProvider === 'google_routes' || sv.routeProvider === 'osrm') ? '#10b981' : '#eab308';
  var navRows = '';
  (sv.navigationSteps || []).slice(0, 6).forEach(function(step, i) {
    navRows += '<div style="display:flex;gap:8px;padding:5px 0;border-bottom:1px solid rgba(255,255,255,0.04)">' +
      '<span style="font-size:12px;color:#06b6d4;font-weight:900">' + (i + 1) + '</span>' +
      '<div style="flex:1"><div style="font-size:11px;color:var(--text-primary);font-weight:700">' + (step.maneuver || 'STEP') + '</div>' +
      '<div style="font-size:10px;color:#94a3b8;line-height:1.4">' + (step.instruction || 'Continue') + '</div></div>' +
      '</div>';
  });

  var intersectionRows = '';
  (sv.priorityIntersections || f.ev_priority_intersections || []).forEach(function(int, i) {
    var c = { 'Critical': '#ef4444', 'High': '#f97316', 'Medium': '#eab308' }[int.priorityLevel] || '#eab308';
    intersectionRows += '<div style="display:flex;align-items:center;gap:8px;padding:5px 0;border-bottom:1px solid rgba(255,255,255,0.04)">' +
      '<span style="font-size:13px">🚦</span>' +
      '<div style="flex:1"><div style="font-size:11px;font-weight:700;color:var(--text-primary)">' + int.name + '</div>' +
      '<div style="font-size:10px;color:#94a3b8">' + int.action + '</div></div>' +
      '<span style="font-size:10px;font-weight:800;color:' + c + ';background:' + c + '22;padding:2px 6px;border-radius:4px">' + int.priorityLevel + '</span>' +
      '</div>';
  });

  container.innerHTML =
    '<div class="card" style="border:1px solid rgba(6,182,212,0.3);box-shadow:0 0 24px rgba(6,182,212,0.08)">' +
    '<div class="card-header" style="background:linear-gradient(135deg,rgba(6,182,212,0.12),rgba(249,115,22,0.08))">' +
    '<span>⚡</span><h3 style="color:#06b6d4">Emergency ETA Optimization</h3>' +
    '<span class="card-badge" style="background:rgba(6,182,212,0.2);color:#06b6d4;animation:pulse 2s infinite">ACTIVE</span>' +
    '</div>' +
    '<div class="card-body">' +

    // Header info row
    '<div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr 1fr;gap:12px;margin-bottom:16px">' +
    '<div style="background:var(--bg-primary);padding:10px;border-radius:8px;border:1px solid rgba(255,255,255,0.06)">' +
    '<div style="font-size:10px;color:#94a3b8;font-weight:700;margin-bottom:4px">SELECTED UNIT</div>' +
    '<div style="font-size:14px;font-weight:900;color:var(--text-primary)">' + unitType + '</div>' +
    '<div style="font-size:11px;color:#06b6d4;font-weight:700">' + unitId + '</div>' +
    '</div>' +

    '<div style="background:var(--bg-primary);padding:10px;border-radius:8px;border:1px solid ' + evCongColor + '44">' +
    '<div style="font-size:10px;color:#94a3b8;font-weight:700;margin-bottom:4px">CONGESTION STATUS</div>' +
    '<div style="font-size:13px;font-weight:900;color:' + evCongColor + '">' + evCong + '</div>' +
    '<div style="font-size:10px;color:' + evCongColor + '">' + stuckMsg + '</div>' +
    '</div>' +

    '<div style="background:var(--bg-primary);padding:10px;border-radius:8px;border:1px solid rgba(255,255,255,0.06)">' +
    '<div style="font-size:10px;color:#94a3b8;font-weight:700;margin-bottom:4px">DISTANCE</div>' +
    '<div style="font-size:20px;font-weight:900;color:var(--text-primary)">' + distance + '</div>' +
    '<div style="font-size:10px;color:#94a3b8">km to incident</div>' +
    '</div>' +

    '<div style="background:rgba(249,115,22,0.1);padding:10px;border-radius:8px;border:1px solid rgba(249,115,22,0.3)">' +
    '<div style="font-size:10px;color:#94a3b8;font-weight:700;margin-bottom:4px">ROUTE STATUS</div>' +
    '<div style="font-size:11px;font-weight:900;color:#f97316">' + routeStatus + '</div>' +
    '</div>' +

    '<div style="background:rgba(16,185,129,0.06);padding:10px;border-radius:8px;border:1px solid ' + routeProviderColor + '44">' +
    '<div style="font-size:10px;color:#94a3b8;font-weight:700;margin-bottom:4px">ROUTE SOURCE</div>' +
    '<div style="font-size:11px;font-weight:900;color:' + routeProviderColor + '">' + routeProvider + '</div>' +
    '</div>' +
    '</div>' + // end grid

    // ETA Comparison
    '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:16px">' +
    '<div style="background:rgba(148,163,184,0.06);padding:14px;border-radius:10px;border:1px solid rgba(148,163,184,0.15);text-align:center">' +
    '<div style="font-size:10px;color:#94a3b8;font-weight:700;margin-bottom:6px">🕐 NORMAL ETA</div>' +
    '<div style="font-size:32px;font-weight:900;color:#64748b;text-decoration:line-through">' + normalEta + '</div>' +
    '<div style="font-size:11px;color:#64748b">minutes (congested)</div>' +
    '</div>' +
    '<div style="background:rgba(16,185,129,0.08);padding:14px;border-radius:10px;border:2px solid rgba(16,185,129,0.3);text-align:center">' +
    '<div style="font-size:10px;color:#10b981;font-weight:700;margin-bottom:6px">⚡ PRIORITY ETA</div>' +
    '<div style="font-size:32px;font-weight:900;color:#10b981">' + priorityEta + '</div>' +
    '<div style="font-size:11px;color:#10b981">minutes (corridor active)</div>' +
    '</div>' +
    '<div style="background:rgba(6,182,212,0.08);padding:14px;border-radius:10px;border:2px solid rgba(6,182,212,0.3);text-align:center">' +
    '<div style="font-size:10px;color:#06b6d4;font-weight:700;margin-bottom:6px">⏱️ TIME SAVED</div>' +
    '<div style="font-size:32px;font-weight:900;color:#06b6d4">-' + timeSaved + '</div>' +
    '<div style="font-size:11px;color:#06b6d4">minutes faster</div>' +
    '</div>' +
    '</div>' + // end ETA grid

    // Signal Priority Intersections
    (intersectionRows ? (
    '<div style="margin-bottom:12px">' +
    '<div style="font-size:11px;font-weight:800;color:#f97316;letter-spacing:0.05em;margin-bottom:8px">🚦 TRAFFIC SIGNAL PRIORITY ACTIONS</div>' +
    intersectionRows +
    '</div>'
    ) : '') +

    (navRows ? (
    '<div style="margin-bottom:12px;padding:10px;background:rgba(6,182,212,0.04);border:1px solid rgba(6,182,212,0.18);border-radius:8px">' +
    '<div style="font-size:11px;font-weight:800;color:#06b6d4;letter-spacing:0.05em;margin-bottom:8px">🧭 TURN-BY-TURN ROUTE PREVIEW</div>' +
    navRows +
    '</div>'
    ) : '') +

    // Clearance action
    (sv.recommendedClearanceAction || f.ev_summary ? (
    '<div style="margin-top:12px;padding:10px;background:rgba(249,115,22,0.06);border:1px solid rgba(249,115,22,0.2);border-radius:8px">' +
    '<div style="font-size:10px;color:#f97316;font-weight:800;margin-bottom:4px">📋 RECOMMENDED ACTION</div>' +
    '<div style="font-size:11px;color:var(--text-secondary);line-height:1.6">' + (sv.recommendedClearanceAction || f.ev_summary || '') + '</div>' +
    '</div>'
    ) : '') +

    '</div></div>'; // end card-body, card
}

function renderTimeline(timeline, containerId) {
  var container = document.getElementById(containerId);
  if (!container) return;
  container.innerHTML = '';
  var timelineIcons = {
    'System': '📡', 'Traffic Agent': '🚦', 'Emergency Agent': '🚑',
    'Environment Agent': '🌿', 'Analysis Agent': '🔬',
    'Coordinator Agent': '🎯', 'Emergency Services': '🚨',
    'Traffic Control': '🚧', 'All Agencies': '✅'
  };
  timeline.forEach(function(item, i) {
    var div = document.createElement('div');
    div.className = 'timeline-item';
    div.innerHTML =
      '<div class="timeline-dot ' + (item.status === 'done' ? 'active' : '') + '">' + (timelineIcons[item.actor] || '📋') + '</div>' +
      '<div class="timeline-content">' +
      '<div class="timeline-actor">' + item.actor + '</div>' +
      '<div class="timeline-event">' + item.event + '</div>' +
      '<div class="timeline-time">' + item.time + '</div>' +
      '</div>';
    container.appendChild(div);
    setTimeout(function() { div.classList.add('visible'); }, i * 200);
  });
}

function renderCoordinatorDecision(fd, containerId) {
  var container = document.getElementById(containerId);
  if (!container) return;
  var conf = Math.round((fd.confidence_score || 0.9) * 100);
  var immediateHTML = (fd.immediate_actions || []).map(function(a) { return '<li>' + a + '</li>'; }).join('');
  var preventionHTML = (fd.prevention_recommendations || []).map(function(r) { return '<li>💡 ' + r + '</li>'; }).join('');
  var combinedComm = (fd.agent_communication_log || []).concat((fd.ollama_agent_communication_log || []).map(function(x){ return Object.assign({}, x, { agent: x.agent || 'Qwen / Ollama' }); }));
  var commHTML = combinedComm.map(function(item) {
    return '<div style="padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.05)"><b style="color:#06b6d4">' + (item.agent || 'Agent') + '</b><br><span style="font-size:12px;color:var(--text-secondary)">' + (item.message || '') + '</span><br><span style="font-size:10px;color:#10b981">Impact: ' + (item.decision_impact || '—') + '</span></div>';
  }).join('');

  // EV ETA in coordinator summary
  var evSection = '';
  var ep = fd.emergency_plan || {};
  var ar = fd.agent_responses || [];
  var emergAgent = null;
  ar.forEach(function(a) { if (a.agent_name === 'Emergency Agent') emergAgent = a; });
  if (emergAgent) {
    var ef = emergAgent.findings || {};
    var sv = ef.selected_vehicle || {};
    if (sv.unitId || ef.ev_normal_eta) {
      var normalEta = sv.normalEta || ef.ev_normal_eta || '—';
      var priorityEta = sv.priorityEta || ef.ev_priority_eta || '—';
      var timeSaved = sv.timeSaved || ef.ev_time_saved || '—';
      var routeStatus = sv.routeStatus || ef.ev_route_status || '—';
      evSection =
        '<div style="margin-top:16px;padding:14px;background:rgba(6,182,212,0.06);border:1px solid rgba(6,182,212,0.25);border-radius:10px">' +
        '<div style="font-size:11px;font-weight:800;color:#06b6d4;letter-spacing:0.05em;margin-bottom:10px">⚡ EMERGENCY VEHICLE ETA OPTIMIZATION — COORDINATOR APPROVED</div>' +
        '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px">' +
        '<div style="text-align:center"><div style="font-size:10px;color:#94a3b8">UNIT</div><div style="font-weight:900;color:#f97316">' + (sv.type || '—') + ' ' + (sv.unitId || '') + '</div></div>' +
        '<div style="text-align:center"><div style="font-size:10px;color:#94a3b8">NORMAL ETA</div><div style="font-weight:900;color:#64748b;text-decoration:line-through">' + normalEta + ' min</div></div>' +
        '<div style="text-align:center"><div style="font-size:10px;color:#94a3b8">PRIORITY ETA</div><div style="font-weight:900;color:#10b981">' + priorityEta + ' min</div></div>' +
        '<div style="text-align:center"><div style="font-size:10px;color:#94a3b8">TIME SAVED</div><div style="font-weight:900;color:#06b6d4">-' + timeSaved + ' min</div></div>' +
        '</div>' +
        '<div style="margin-top:8px;font-size:11px;color:#f97316;font-weight:700">✅ Emergency corridor approved — ' + routeStatus + '</div>' +
        '</div>';
    }
  }

  container.innerHTML =
    '<div class="coordinator-card fade-in-up">' +
    '<div class="flex-between mb-16">' +
    '<div><div class="text-xs text-muted mb-4">COORDINATOR AGENT — FINAL DECISION</div>' +
    '<div class="coordinator-priority">' + (fd.priority_level || 'N/A') + '</div></div>' +
    '<div style="text-align:right"><div class="text-xs text-muted mb-4">SYSTEM CONFIDENCE</div>' +
    '<div style="font-size:32px;font-weight:900;color:#06b6d4;font-family:\'JetBrains Mono\',monospace">' + conf + '%</div></div>' +
    '</div>' +

    '<div class="alert alert-danger mb-16" style="font-size:13px;line-height:1.7">' + (fd.final_summary || '') + '</div>' +

    evSection +

    '<div class="section-title" style="margin-top:16px">🚨 Immediate Actions</div>' +
    '<ul class="action-list mb-16">' + immediateHTML + '</ul>' +

    '<div class="grid-2">' +
    '<div><div class="section-title">🚦 Traffic Plan</div><div class="text-sm text-secondary">' +
    '<div class="agent-finding-row"><span class="finding-label">Congestion</span><span class="finding-value">' + (fd.traffic_plan && fd.traffic_plan.congestion_level || '—') + '</span></div>' +
    '<div class="agent-finding-row"><span class="finding-label">Delay Reduction</span><span class="finding-value text-green">' + (fd.traffic_plan && fd.traffic_plan.delay_reduction_min || '—') + ' min</span></div>' +
    '<div class="agent-finding-row"><span class="finding-label">Status</span><span class="finding-value">' + (fd.traffic_plan && fd.traffic_plan.traffic_status || '—') + '</span></div>' +
    '</div></div>' +
    '<div><div class="section-title">⚠️ Environment Plan</div><div class="text-sm text-secondary">' +
    '<div class="agent-finding-row"><span class="finding-label">Risk Level</span><span class="finding-value">' + (fd.environment_plan && fd.environment_plan.risk_level || '—') + '</span></div>' +
    '<div class="agent-finding-row"><span class="finding-label">Exclusion Zone</span><span class="finding-value">' + (fd.environment_plan && fd.environment_plan.exclusion_zone_m || '—') + 'm</span></div>' +
    '<div class="agent-finding-row"><span class="finding-label">AQI</span><span class="finding-value">' + (fd.environment_plan && fd.environment_plan.projected_aqi || '—') + '</span></div>' +
    '</div></div>' +
    '</div>' +

    (commHTML ? '<div class="section-title mt-16">🤝 Agent Communication Log</div><div style="padding:12px;background:rgba(6,182,212,0.04);border:1px solid rgba(6,182,212,0.16);border-radius:10px">' + commHTML + '</div>' : '') +

    '<div class="section-title mt-16">🔬 Root Cause</div>' +
    '<div class="text-sm" style="color:var(--text-secondary)"><b style="color:var(--text-primary)">' + (fd.cause_analysis && fd.cause_analysis.primary_cause || '—') + '</b>' +
    '&nbsp;<span class="text-muted">(' + (fd.cause_analysis && fd.cause_analysis.cause_probability || '—') + ' probability)</span></div>' +

    '<div class="section-title mt-16">💡 Prevention Recommendations</div>' +
    '<ul class="action-list">' + preventionHTML + '</ul>' +

    (fd.ai_enhanced ? '<div class="alert alert-info mt-16">✨ <b>Qwen / Ollama Enhanced</b> — Local model added report wording, communication insights, and conflict explanations.</div>' : '') +
    '</div>';
}

window.renderAgentCard = renderAgentCard;
window.renderAllAgents = renderAllAgents;
window.renderTimeline = renderTimeline;
window.renderCoordinatorDecision = renderCoordinatorDecision;
window.renderEvEtaPanel = renderEvEtaPanel;
window.AGENT_META = AGENT_META;
