function generateReportHTML(report) {
  const inc = report.incident || {};
  const fd = report.final_decision || {};
  const agents = report.agent_analyses || [];
  const timeline = report.response_timeline || [];

  const agentRows = agents.map(a => {
    const f = a.findings || {};
    return `
      <tr>
        <td><b>${a.agent_name}</b></td>
        <td>${a.risk_level || '—'}</td>
        <td>${Math.round((a.confidence_score || 0) * 100)}%</td>
        <td style="font-size:12px">${(f.summary || a.recommendation || '').substring(0, 120)}...</td>
      </tr>`;
  }).join('');

  const timelineRows = timeline.map(t => `
    <tr>
      <td class="font-mono">${t.time}</td>
      <td>${t.actor}</td>
      <td>${t.event}</td>
      <td><span style="color:${t.status === 'done' ? '#10b981' : '#eab308'}">${t.status === 'done' ? '✅ Done' : '⏳ Pending'}</span></td>
    </tr>`).join('');

  const preventionList = (fd.prevention_recommendations || []).map(r => `<li style="padding:4px 0">💡 ${r}</li>`).join('');
  const immediateList = (fd.immediate_actions || []).map(a => `<li style="padding:4px 0">${a}</li>`).join('');
  const combinedComm = (fd.agent_communication_log || []).concat((fd.ollama_agent_communication_log || []).map(x => ({...x, agent: x.agent || 'Qwen / Ollama'})));
  const commRows = combinedComm.map(c => `
    <tr><td><b>${c.agent || 'Agent'}</b></td><td>${c.message || '—'}</td><td>${c.decision_impact || '—'}</td></tr>`).join('');
  const conflictRows = (fd.conflict_resolution || fd.ai_conflict_resolution || []).map(c => `
    <tr><td>${c.conflict || '—'}</td><td>${c.resolution || '—'}</td><td>${c.reason || '—'}</td></tr>`).join('');
  const eta = fd.ev_eta_decision || {};
  const transfer = fd.emergency_plan?.patient_transfer_plan || null;
  const ambulanceOrigin = fd.emergency_plan?.ambulance_origin || '—';

  return `
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>S.I.R.S Incident Report — ${report.report_id}</title>
<style>
  body { font-family: Arial, sans-serif; max-width: 900px; margin: 0 auto; padding: 32px; color: #1e293b; background: #fff; }
  .report-header { background: linear-gradient(135deg, #060b18, #0d1526); color: #fff; padding: 28px 32px; border-radius: 8px; margin-bottom: 28px; }
  .report-header h1 { font-size: 28px; font-weight: 900; letter-spacing: 2px; margin: 0 0 4px; }
  .report-header .subtitle { color: #94a3b8; font-size: 13px; }
  .report-header .report-meta { margin-top: 16px; display: flex; gap: 24px; flex-wrap: wrap; }
  .report-header .meta-item { font-size: 12px; }
  .report-header .meta-label { color: #64748b; margin-bottom: 2px; }
  .report-header .meta-value { color: #e2e8f0; font-weight: 700; }
  .section { margin-bottom: 28px; }
  .section-title { font-size: 14px; font-weight: 800; text-transform: uppercase; letter-spacing: 1px; color: #0f172a; border-left: 4px solid #06b6d4; padding-left: 12px; margin-bottom: 14px; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th { background: #f1f5f9; text-align: left; padding: 8px 12px; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: #475569; }
  td { padding: 10px 12px; border-bottom: 1px solid #e2e8f0; color: #334155; }
  tr:last-child td { border-bottom: none; }
  .badge { display: inline-block; padding: 2px 10px; border-radius: 20px; font-size: 11px; font-weight: 700; }
  .badge-critical { background: #fee2e2; color: #dc2626; }
  .badge-high { background: #ffedd5; color: #ea580c; }
  .badge-medium { background: #fefce8; color: #ca8a04; }
  .badge-low { background: #dcfce7; color: #16a34a; }
  .summary-box { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; font-size: 13px; line-height: 1.8; color: #334155; }
  .footer { margin-top: 32px; padding-top: 20px; border-top: 1px solid #e2e8f0; font-size: 11px; color: #94a3b8; text-align: center; }
  .conf-bar { height: 6px; background: #e2e8f0; border-radius: 3px; overflow: hidden; margin-top: 4px; }
  .conf-fill { height: 100%; background: linear-gradient(90deg, #3b82f6, #06b6d4); border-radius: 3px; }
  @media print { body { padding: 16px; } }
</style>
</head>
<body>
  <div class="report-header">
    <div class="subtitle">S.I.R.S — Smart Incident Response System</div>
    <h1>INCIDENT RESPONSE REPORT</h1>
    <div class="report-meta">
      <div class="meta-item"><div class="meta-label">Report ID</div><div class="meta-value">${report.report_id}</div></div>
      <div class="meta-item"><div class="meta-label">Generated</div><div class="meta-value">${new Date(report.generated_at).toLocaleString()}</div></div>
      <div class="meta-item"><div class="meta-label">Priority</div><div class="meta-value" style="color:#f97316">${report.priority_level}</div></div>
      <div class="meta-item"><div class="meta-label">AI Enhanced</div><div class="meta-value">${report.ai_enhanced ? '✅ Yes' : '⚙️ Rule-Based'}</div></div>
    </div>
  </div>

  <div class="section">
    <div class="section-title">1. Executive Summary</div>
    <div class="summary-box">${report.executive_summary}</div>
  </div>


  ${report.camera_detection_summary ? `<div class="section">
    <div class="section-title">2. Camera Detection Evidence</div>
    <div class="summary-box">${report.camera_detection_summary}</div>
  </div>` : ''}

  ${(report.dispatch_summary || report.route_eta_summary || report.final_status_summary) ? `<div class="section">
    <div class="section-title">3. Response Decision Summary</div>
    <table>
      <tr><th>Area</th><th>Summary</th></tr>
      ${report.dispatch_summary ? `<tr><td>Dispatch</td><td>${report.dispatch_summary}</td></tr>` : ''}
      ${report.route_eta_summary ? `<tr><td>Route & ETA</td><td>${report.route_eta_summary}</td></tr>` : ''}
      ${report.final_status_summary ? `<tr><td>Final Status</td><td>${report.final_status_summary}</td></tr>` : ''}
      <tr><td>Report Source</td><td>${report.report_generated_by || 'deterministic_report_builder'}${report.report_model ? ` — ${report.report_model}` : ''}</td></tr>
    </table>
  </div>` : ''}

  ${fd.ai_enhanced ? `<div class="section">
    <div class="section-title">2. Local Qwen / Ollama Role</div>
    <div class="summary-box">Qwen/Ollama was used as a local reasoning and reporting assistant. It did not calculate routes or directly control dispatch. It enriched the Coordinator output by improving the executive summary, explaining agent cooperation, and documenting conflict resolution. ${fd.ai_insight ? `<br><br><b>AI Insight:</b> ${fd.ai_insight}` : ''}</div>
  </div>` : ''}

  <div class="section">
    <div class="section-title">${fd.ai_enhanced ? '3' : '2'}. Incident Details</div>
    <table>
      <tr><th>Field</th><th>Value</th></tr>
      <tr><td>Incident ID</td><td><b>${inc.id}</b></td></tr>
      <tr><td>Type</td><td>${inc.type}</td></tr>
      <tr><td>Severity</td><td><span class="badge badge-${(inc.severity||'').toLowerCase()}">${inc.severity}</span></td></tr>
      <tr><td>Location</td><td>${inc.location_name} (${inc.latitude?.toFixed(4)}, ${inc.longitude?.toFixed(4)})</td></tr>
      <tr><td>Time</td><td>${inc.time} — ${new Date(inc.created_at).toLocaleDateString()}</td></tr>
      <tr><td>Weather</td><td>${inc.weather}</td></tr>
      <tr><td>Traffic Density</td><td>${inc.traffic_density}</td></tr>
      <tr><td>Affected Vehicles</td><td>${inc.affected_vehicles}</td></tr>
      <tr><td>Affected People</td><td>${inc.affected_people}</td></tr>
      <tr><td>Status</td><td>${inc.status}</td></tr>
      ${inc.source ? `<tr><td>Detection Source</td><td>${inc.source}${inc.camera_id ? ` — ${inc.camera_id}` : ''}</td></tr>` : ''}
      ${inc.description ? `<tr><td>Description</td><td>${inc.description}</td></tr>` : ''}
    </table>
  </div>

  <div class="section">
    <div class="section-title">Agent Analyses</div>
    <table>
      <tr><th>Agent</th><th>Risk Level</th><th>Confidence</th><th>Key Finding</th></tr>
      ${agentRows}
    </table>
  </div>

  <div class="section">
    <div class="section-title">Coordinator Final Decision</div>
    <table>
      <tr><th>Aspect</th><th>Decision</th></tr>
      <tr><td>Priority Level</td><td><b style="color:#f97316">${fd.priority_level}</b></td></tr>
      <tr><td>Emergency Plan</td><td>${fd.emergency_plan?.total_units || '—'} suitable units dispatched — ETA ${fd.emergency_plan?.first_responder_eta_min || '—'} min</td></tr>
      <tr><td>Ambulance Origin Policy</td><td>Ambulance origin: ${ambulanceOrigin}. Hospitals are used as patient destinations, not dispatch origins.</td></tr>
      ${transfer ? `<tr><td>Patient Transfer Destination</td><td>${transfer.destination?.name || '—'}${transfer.eta_min ? ` — estimated transfer ETA ${transfer.eta_min} min` : ''}</td></tr>` : ''}
      <tr><td>Route Optimisation</td><td>${eta.unit || '—'} | Normal ETA: ${eta.normal_eta || '—'} min → Priority ETA: ${eta.priority_eta || '—'} min | Saved: ${eta.time_saved || '—'} min | Provider: ${eta.route_provider || '—'}</td></tr>
      <tr><td>Traffic Plan</td><td>Congestion: ${fd.traffic_plan?.congestion_level} — Delay reduction: ${fd.traffic_plan?.delay_reduction_min} min</td></tr>
      <tr><td>Environment Plan</td><td>Risk: ${fd.environment_plan?.risk_level} — Zone: ${fd.environment_plan?.exclusion_zone_m}m — AQI: ${fd.environment_plan?.projected_aqi}</td></tr>
      <tr><td>Root Cause</td><td>${fd.cause_analysis?.primary_cause} (${fd.cause_analysis?.cause_probability})</td></tr>
      <tr><td>Overall Confidence</td><td>
        <b>${Math.round((fd.confidence_score||0)*100)}%</b>
        <div class="conf-bar"><div class="conf-fill" style="width:${Math.round((fd.confidence_score||0)*100)}%"></div></div>
      </td></tr>
    </table>

    <div style="margin-top:16px"><b>Immediate Actions:</b><ul>${immediateList}</ul></div>
  </div>

  ${commRows ? `<div class="section">
    <div class="section-title">Agent Communication Log</div>
    <table>
      <tr><th>Agent</th><th>Message</th><th>Decision Impact</th></tr>
      ${commRows}
    </table>
  </div>` : ''}

  ${conflictRows ? `<div class="section">
    <div class="section-title">Coordinator Conflict Resolution</div>
    <table>
      <tr><th>Conflict</th><th>Resolution</th><th>Reason</th></tr>
      ${conflictRows}
    </table>
  </div>` : ''}

  <div class="section">
    <div class="section-title">Response Timeline</div>
    <table>
      <tr><th>Time</th><th>Actor</th><th>Event</th><th>Status</th></tr>
      ${timelineRows}
    </table>
  </div>


  ${(report.lessons_learned || []).length ? `<div class="section">
    <div class="section-title">Lessons Learned</div>
    <ul style="padding-left:20px;line-height:2">${(report.lessons_learned || []).map(x => `<li>${x}</li>`).join('')}</ul>
  </div>` : ''}
  <div class="section">
    <div class="section-title">Prevention Recommendations</div>
    <ul style="padding-left:20px;line-height:2">${preventionList}</ul>
  </div>

  <div class="footer">
    <b>S.I.R.S — Smart Incident Response System</b> | Multi-Agent Architecture | ${new Date().getFullYear()}<br>
    This report was generated automatically by the S.I.R.S Multi-Agent Engine with local Ollama support when available. For official use only.
  </div>
</body>
</html>`;
}

function printReport(reportData) {
  const html = generateReportHTML(reportData);
  const win = window.open('', '_blank');
  win.document.write(html);
  win.document.close();
  setTimeout(() => win.print(), 800);
}

function renderInlineReport(reportData, containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;
  const html = generateReportHTML(reportData);
  const iframe = document.createElement('iframe');
  iframe.style.width = '100%';
  iframe.style.height = '700px';
  iframe.style.border = 'none';
  iframe.style.borderRadius = '8px';
  container.innerHTML = '';
  container.appendChild(iframe);
  iframe.contentDocument.write(html);
  iframe.contentDocument.close();
}

window.generateReportHTML = generateReportHTML;
window.printReport = printReport;
window.renderInlineReport = renderInlineReport;
