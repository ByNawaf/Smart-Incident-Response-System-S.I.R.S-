const API = window.location.origin + '/api';

async function request(method, path, body = null) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(API + path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

const api = {
  getCityData: () => request('GET', '/city-data'),
  getStats: () => request('GET', '/stats'),
  getIncidents: () => request('GET', '/incidents'),
  createIncident: (data) => request('POST', '/incidents', data),
  getIncident: (id) => request('GET', `/incidents/${id}`),
  deleteIncident: (id) => request('DELETE', `/incidents/${id}`),
  analyzeIncident: (id) => request('POST', `/incidents/${id}/analyze`),
  coordinateIncident: (id) => request('POST', `/incidents/${id}/coordinate`),
  getReport: (id) => request('GET', `/incidents/${id}/report`),
  runDemo: () => request('POST', '/demo/run'),
  getDemoCurrent: () => request('GET', '/demo/current'),
  getCameras: () => request('GET', '/cameras'),
  scanCamera: (id) => request('POST', `/cameras/${id}/scan`),
  triggerCamera: (id) => request('POST', `/cameras/${id}/trigger`),
  runCameraDemo: (cameraId) => request('POST', '/camera-demo/run', cameraId ? { camera_id: cameraId } : null),
  getSettings: () => request('GET', '/settings'),
  saveSettings: (data) => request('POST', '/settings', data),
  getFrontendConfig: () => request('GET', '/frontend-config'),
  previewRoute: (data) => request('POST', '/routes/preview', data),
};

window.api = api;
