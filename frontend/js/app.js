// ── Toast notifications ───────────────────────────────────────────────────────
function showToast(message, type = 'info', duration = 4000) {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  const icons = { success: '✅', error: '❌', info: 'ℹ️', warn: '⚠️' };
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${icons[type] || 'ℹ️'}</span><span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => { toast.style.opacity = '0'; toast.style.transform = 'translateX(20px)'; toast.style.transition = 'all 0.3s'; setTimeout(() => toast.remove(), 300); }, duration);
}
window.showToast = showToast;

// ── Clock ─────────────────────────────────────────────────────────────────────
function updateClock() {
  const el = document.getElementById('live-clock');
  if (el) el.textContent = new Date().toLocaleTimeString('en-US', { hour12: false });
}
setInterval(updateClock, 1000);
updateClock();

// ── Active nav ────────────────────────────────────────────────────────────────
function setActiveNav() {
  const path = window.location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.nav-item').forEach(item => {
    const href = item.getAttribute('href') || '';
    item.classList.toggle('active', href.includes(path) || (path === 'index.html' && href === '/'));
  });
}
document.addEventListener('DOMContentLoaded', setActiveNav);

// ── Incident badge count ──────────────────────────────────────────────────────
async function refreshNavBadge() {
  try {
    const incidents = await api.getIncidents();
    const active = incidents.filter(i => i.status === 'Active').length;
    document.querySelectorAll('.incident-badge').forEach(b => {
      b.textContent = active;
      b.style.display = active > 0 ? 'inline-block' : 'none';
    });
  } catch (_) {}
}

// ── Format helpers ────────────────────────────────────────────────────────────
function severityColor(sev) {
  return { Low: 'sev-low', Medium: 'sev-medium', High: 'sev-high', Critical: 'sev-critical' }[sev] || '';
}
function riskBadge(level) {
  const cls = { Low: 'risk-low', Medium: 'risk-medium', High: 'risk-high', Critical: 'risk-critical' }[level] || 'risk-medium';
  return `<span class="risk-badge ${cls}">${level || 'N/A'}</span>`;
}
function formatDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-GB', { day:'2-digit', month:'short', hour:'2-digit', minute:'2-digit' });
}
function pct(v) { return `${Math.round((v || 0) * 100)}%`; }

window.severityColor = severityColor;
window.riskBadge = riskBadge;
window.formatDate = formatDate;
window.pct = pct;
window.refreshNavBadge = refreshNavBadge;
