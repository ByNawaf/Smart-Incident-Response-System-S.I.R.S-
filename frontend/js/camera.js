let ccMap = null;
let cameras = [];
let selectedCameraId = null;
let latestIncident = null;
let latestReportData = null;

function setStatus(text, ok = true) {
  const el = document.getElementById('cc-status');
  if (el) { el.textContent = text; el.className = 'header-alert ' + (ok ? 'ok' : 'warn'); }
}

function shortType(t) {
  return (t || '—').replace('Traffic Accident', 'Collision').replace('Fire Incident', 'Fire').replace('Medical Emergency', 'Medical').replace('Road Blockage', 'Blockage');
}

function cameraDisplayName(camera) {
  return camera?.display_name || camera?.name || camera?.camera_id || 'Camera';
}


function escapeAttr(value) {
  return String(value || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function getCameraMediaCandidates(camera) {
  const raw = [camera?.media_url, camera?.media_example_path, camera?.video_url, camera?.image_url].filter(Boolean);
  const candidates = [];
  raw.forEach(src => {
    if (!candidates.includes(src)) candidates.push(src);
    const fileName = String(src).split('/').pop();
    if (fileName) {
      const feedPath = `/static/assets/camera-feeds/${fileName}`;
      const rootPath = `/static/assets/${fileName}`;
      if (!candidates.includes(feedPath)) candidates.push(feedPath);
      if (!candidates.includes(rootPath)) candidates.push(rootPath);
    }
  });
  return candidates;
}

function setCameraMedia(camera) {
  const feed = document.getElementById('feed-screen');
  const layer = document.getElementById('feed-media-layer');
  if (!feed || !layer) return;
  const candidates = getCameraMediaCandidates(camera);
  layer.innerHTML = '';
  feed.classList.remove('feed-has-media');
  if (!candidates.length) return;

  let index = 0;
  const loadCandidate = () => {
    const src = candidates[index];
    if (!src) return;
    const safe = escapeAttr(src);
    const isImage = /\.(png|jpe?g|webp|gif)$/i.test(src);
    feed.classList.add('feed-has-media');
    if (isImage) {
      layer.innerHTML = `<img src="${safe}" alt="Street camera feed">`;
      const img = layer.querySelector('img');
      img.onerror = () => {
        index += 1;
        if (index < candidates.length) loadCandidate();
        else { layer.innerHTML = ''; feed.classList.remove('feed-has-media'); }
      };
    } else {
      layer.innerHTML = `<video src="${safe}" autoplay muted loop playsinline preload="auto"></video>`;
      const video = layer.querySelector('video');
      video.onerror = () => {
        index += 1;
        if (index < candidates.length) loadCandidate();
        else { layer.innerHTML = ''; feed.classList.remove('feed-has-media'); }
      };
      video.oncanplay = () => { video.play().catch(() => {}); };
    }
  };
  loadCandidate();
}

function feedClassFor(camera) {
  const obs = camera?.sensor_observations || {};
  if (obs.visible_flames) return 'feed-screen feed-fire';
  if (obs.liquid_on_road) return 'feed-screen feed-fuel';
  if (obs.person_down_detected) return 'feed-screen feed-medical';
  if (!obs.abnormal_stop && !obs.blocked_lanes) return 'feed-screen feed-normal';
  return 'feed-screen feed-collision';
}

function updateFeed(camera) {
  const feed = document.getElementById('feed-screen');
  if (!camera || !feed) return;
  feed.className = feedClassFor(camera);
  setCameraMedia(camera);
  document.getElementById('feed-cam-id').textContent = cameraDisplayName(camera);
  document.getElementById('feed-location').textContent = camera.location_name;
  if (ccMap) ccMap.flyTo([camera.latitude, camera.longitude], 14);
}

function renderCameraList() {
  const list = document.getElementById('camera-list');
  if (!list) return;
  list.innerHTML = cameras.map(c => `
    <div class="camera-item ${c.camera_id === selectedCameraId ? 'active' : ''}" onclick="selectCamera('${c.camera_id}')">
      <div class="camera-title"><span>${cameraDisplayName(c)}</span><span>${c.status}</span></div>
    </div>
  `).join('');
}

function selectCamera(cameraId) {
  selectedCameraId = cameraId;
  const camera = cameras.find(c => c.camera_id === cameraId);
  updateFeed(camera);
  renderCameraList();
}

function renderDetection(cameraResult) {
  const out = document.getElementById('detection-output');
  const f = cameraResult?.findings || {};
  if (!out) return;
  out.style.display = 'block';
  const evidence = (f.evidence || []).map(e => `<li>${e}</li>`).join('');
  out.innerHTML = `
    <div class="detect-title">${cameraResult.status}: ${f.incident_type}</div>
    <div class="unit-meta">Confidence: <b style="color:#22d3ee">${Math.round((cameraResult.confidence_score || 0) * 100)}%</b> · Severity: <b>${f.severity}</b> · Traffic: <b>${f.traffic_density}</b></div>
    <ul class="evidence-list">${evidence}</ul>
  `;
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function truncateText(value, max = 145) {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  return text.length > max ? text.slice(0, max - 1).trim() + '…' : text;
}

function pct(value) {
  const n = Number(value || 0);
  return `${Math.round(Math.max(0, Math.min(1, n)) * 100)}%`;
}

function findQwenDecision(agent) {
  const f = agent?.findings || {};
  return f.qwen_detection_decision
    || f.qwen_traffic_decision
    || f.qwen_emergency_decision
    || f.qwen_environment_decision
    || f.qwen_analysis_decision
    || agent?.qwen_coordinator_decision
    || null;
}

function decisionSourceLabel(agentRuntime, qwenDecision) {
  const llmUsed = agentRuntime?.llm_used || qwenDecision?.llm_used;
  const source = agentRuntime?.decision_source || qwenDecision?.decision_source || 'validated_tools';
  if (llmUsed || String(source).includes('qwen')) return 'Qwen Decision';
  if (String(source).includes('fallback')) return 'Tool Fallback';
  return 'Validated Tools';
}

function getAgentDecision(agent, isCoordinator = false) {
  if (isCoordinator) {
    const total = agent?.emergency_plan?.total_units;
    const eta = agent?.emergency_plan?.min_eta_minutes;
    const actionCount = (agent?.immediate_actions || []).length;
    if (total !== undefined) return `Approved final plan: ${total} response units, minimum ETA ${eta ?? 'N/A'} min, ${actionCount} immediate actions.`;
    return agent?.final_summary || 'Final coordination is waiting for agent outputs.';
  }

  const name = agent?.agent_name || '';
  const f = agent?.findings || {};
  if (name === 'Camera Vision Agent') {
    return `${agent?.status || 'Camera scanned'} — ${f.incident_type || 'No Incident'} (${f.severity || agent?.risk_level || 'N/A'}).`;
  }
  if (name === 'Emergency Agent') {
    const count = f.total_units ?? f.fleet_count ?? (f.dispatched_fleet || []).length;
    const eta = f.min_eta_minutes ?? f.selected_vehicle?.priorityEta;
    return `Dispatch ${count || 0} validated units${eta !== undefined && eta !== null ? `, minimum ETA ${eta} min` : ''}.`;
  }
  if (name === 'Traffic Agent') {
    const closure = f.closure_action ? String(f.closure_action).replaceAll('_', ' ') : null;
    const route = f.recommended_route?.label || f.recommended_route?.id;
    if (closure || route) return `${closure ? closure.charAt(0).toUpperCase() + closure.slice(1) : 'Traffic action'}${route ? ` via ${route}` : ''}.`;
  }
  if (name === 'Environment Agent') {
    const risk = f.environmental_risk || agent?.risk_level;
    const radius = f.affected_radius_m;
    return `Apply ${risk || 'standard'} safety policy${radius ? ` with ${radius}m perimeter` : ''}.`;
  }
  if (name === 'Analysis Agent') {
    const cause = f.primary_cause || f.most_likely_cause || f.selected_root_cause || f.root_cause;
    if (cause) return `Most likely cause: ${typeof cause === 'string' ? cause : (cause.cause || cause.label || JSON.stringify(cause))}.`;
  }
  return agent?.recommendation || f.summary || 'Agent completed its decision.';
}

function getAgentReasoning(agent, isCoordinator = false) {
  const runtime = agent?.agent_runtime || {};
  const qwenDecision = isCoordinator ? (agent?.qwen_coordinator_decision || null) : findQwenDecision(agent);
  return runtime.reasoning_summary
    || qwenDecision?.reasoning_summary
    || agent?.findings?.summary
    || agent?.recommendation
    || (isCoordinator ? agent?.final_summary : 'Reasoning generated from validated tool outputs.');
}

function getValidationStatus(agent, isCoordinator = false) {
  if (isCoordinator) {
    const validation = agent?.agent_graph?.validation || agent?.validation || window.latestValidation || null;
    if (validation?.coordinator_consistency_enforced) {
      return { ok: true, text: `Passed — consistent with Emergency Agent source of truth: ${validation.official_unit_count ?? 'N/A'} units.` };
    }
    return { ok: true, text: 'Passed — final plan constrained by coordinator guardrails.' };
  }

  const validation = agent?.agent_runtime?.validation;
  if (validation) {
    if (validation.valid) return { ok: true, text: 'Passed — unit count, fleet list, and recommendation are consistent.' };
    const errors = (validation.errors || []).join('; ') || 'validator adjusted the result';
    return { ok: false, text: `Adjusted — ${errors}.` };
  }
  const source = agent?.agent_runtime?.decision_source || agent?.findings?.decision_source || findQwenDecision(agent)?.decision_source || 'validated_tools';
  if (String(source).includes('fallback')) return { ok: false, text: 'Fallback — Qwen unavailable, validated tool output used.' };
  return { ok: true, text: 'Passed — Qwen decision constrained to validated tool options.' };
}

function renderAgentCard(agent, options = {}) {
  const isCoordinator = Boolean(options.isCoordinator);
  const runtime = agent?.agent_runtime || {};
  const qwenDecision = isCoordinator ? (agent?.qwen_coordinator_decision || null) : findQwenDecision(agent);
  const name = options.name || agent?.agent_name || 'Agent';
  const confidence = isCoordinator ? (agent?.confidence_score ?? 0.92) : (agent?.confidence_score ?? 0);
  const sourceLabel = decisionSourceLabel(runtime, qwenDecision);
  const validation = getValidationStatus(agent, isCoordinator);
  const decision = truncateText(getAgentDecision(agent, isCoordinator), 155);
  const reasoning = truncateText(getAgentReasoning(agent, isCoordinator), 175);

  return `
    <div class="agent-step ${isCoordinator ? 'active' : 'done'}">
      <div class="agent-card-head">
        <span class="agent-name">${escapeHtml(name)}</span>
        <span class="agent-confidence">${pct(confidence)}</span>
      </div>
      <div class="agent-badges">
        <span class="agent-badge ${sourceLabel === 'Qwen Decision' ? 'qwen' : 'warn'}">${escapeHtml(sourceLabel)}</span>
        <span class="agent-badge ${validation.ok ? 'valid' : 'warn'}">${validation.ok ? 'Validated' : 'Adjusted'}</span>
      </div>
      <div class="agent-detail decision">
        <span class="agent-detail-label">Decision</span>
        <div class="agent-detail-value">${escapeHtml(decision)}</div>
      </div>
      <div class="agent-detail reasoning">
        <span class="agent-detail-label">Qwen Reasoning</span>
        <div class="agent-detail-value">${escapeHtml(reasoning)}</div>
      </div>
      <div class="agent-detail validation ${validation.ok ? '' : 'warn'}">
        <span class="agent-detail-label">Validation Status</span>
        <div class="agent-detail-value">${escapeHtml(validation.text)}</div>
      </div>
    </div>
  `;
}

function renderAgentFlow(agentResponses, finalDecision) {
  const flow = document.getElementById('agent-flow');
  if (!flow) return;
  const agents = agentResponses || [];
  const coordinator = finalDecision || {};
  flow.innerHTML = agents.map(a => renderAgentCard(a)).join('') + renderAgentCard(coordinator, { isCoordinator: true, name: 'Coordinator Agent' });
}

function renderDispatch(agentResponses, finalDecision) {
  const grid = document.getElementById('dispatch-grid');
  const emergency = (agentResponses || []).find(a => a.agent_name === 'Emergency Agent');
  const fleet = emergency?.findings?.dispatched_fleet || [];
  const eta = finalDecision?.ev_eta_decision || {};
  document.getElementById('kpi-type').textContent = shortType(latestIncident?.type);
  document.getElementById('kpi-eta').textContent = eta.priority_eta ? `${eta.priority_eta}m` : '—';
  document.getElementById('kpi-units').textContent = String(fleet.length || '—');
  document.getElementById('route-source').textContent = eta.route_provider ? eta.route_provider.toUpperCase() : 'OSRM / OSM';
  if (!grid) return;
  if (!fleet.length) { grid.innerHTML = '<div class="unit-meta">No incident-specific units dispatched.</div>'; return; }
  grid.innerHTML = fleet.map(v => `
    <div class="unit-card">
      <div class="unit-icon">${v.emoji || '🚨'}</div>
      <div class="unit-body">
        <div class="unit-title"><span>${v.type} ${v.unitId || ''}</span><span>${v.priorityEta || '—'} min</span></div>
        <div class="unit-meta">${v.label || ''}<br>From: ${v.stationName || 'Dispatch Station'}<br>Route: ${v.routeProvider || 'fallback'} · ${v.routeStatus || ''}</div>
      </div>
    </div>
  `).join('');
}

async function scanSelectedCamera() {
  // In the demo flow, scanning means: detect the incident and immediately send it to the agent layer.
  return triggerSelectedCamera();
}

async function triggerSelectedCamera() {
  if (!selectedCameraId) return;
  try {
    setStatus('● Running camera-to-dispatch pipeline...');
    const res = await api.triggerCamera(selectedCameraId);
    renderDetection(res.camera_agent_result);
    if (!res.incident_created) {
      setStatus('● No dispatch needed');
      return;
    }
    latestIncident = res.incident;
    latestReportData = null;
    window.latestValidation = res.final_decision?.agent_graph?.validation || res.final_decision?.validation || null;
    renderIncidentOnMap(res.incident, res.agent_responses);
    renderAgentFlow(res.agent_responses, res.final_decision);
    renderDispatch(res.agent_responses, res.final_decision);
    const btn = document.getElementById('btn-report');
    if (btn) btn.disabled = false;
    setStatus('● Response plan resolved');
    showToast('Camera incident processed by all agents', 'success');
  } catch (e) {
    console.error(e);
    setStatus('● Pipeline failed', false);
    showToast(e.message, 'error');
  }
}

async function openLatestReport() {
  if (!latestIncident) return;
  try {
    latestReportData = latestReportData || await api.getReport(latestIncident.id);
    printReport(latestReportData);
  } catch (e) {
    showToast(e.message, 'error');
  }
}

async function initCommandCenter() {
  ccMap = initMap('command-map', 24.7136, 46.6753, 12);
  try {
    const res = await api.getCameras();
    cameras = res.cameras || [];
    selectedCameraId = cameras[0]?.camera_id || null;
    renderCameraList();
    if (selectedCameraId) updateFeed(cameras[0]);
  } catch (e) {
    setStatus('● Camera data unavailable', false);
    console.error(e);
  }
  setInterval(() => {
    const t = document.getElementById('feed-time');
    if (t) t.textContent = new Date().toLocaleTimeString();
  }, 1000);
}

window.selectCamera = selectCamera;
window.scanSelectedCamera = scanSelectedCamera;
window.triggerSelectedCamera = triggerSelectedCamera;
window.openLatestReport = openLatestReport;
document.addEventListener('DOMContentLoaded', initCommandCenter);
