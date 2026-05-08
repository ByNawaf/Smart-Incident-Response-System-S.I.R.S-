// ══════════════════════════════════════════════════════════════════════════════
// S.I.R.S — Google Maps first, Leaflet fallback map adapter
// ══════════════════════════════════════════════════════════════════════════════

const NativeLeaflet = window.L || null;
let mapInstance = null;
let markers = [];
let routeLayers = [];
let mapAnimations = [];
let _frontendConfigPromise = null;
let _googleMapsPromise = null;

function latLngObj(latlng) {
  if (Array.isArray(latlng)) return { lat: Number(latlng[0]), lng: Number(latlng[1]) };
  if (latlng && typeof latlng.lat === 'function') return { lat: latlng.lat(), lng: latlng.lng() };
  return { lat: Number(latlng.lat), lng: Number(latlng.lng) };
}

function latLngArr(latlng) {
  const p = latLngObj(latlng);
  return [p.lat, p.lng];
}

function makeHtmlElement(html) {
  const el = document.createElement('div');
  el.innerHTML = html || '<div>📍</div>';
  return el.firstElementChild || el;
}

class MapAdapter {
  constructor(containerId, lat, lng, zoom) {
    this.containerId = containerId;
    this.lat = lat;
    this.lng = lng;
    this.zoom = zoom;
    this.provider = 'pending';
    this.map = null;
    this.ready = false;
    this.queue = [];
    this.clickListeners = [];
  }

  whenReady(fn) {
    if (this.ready && this.map) return fn(this.map, this.provider);
    this.queue.push(fn);
  }

  setReady(provider, map) {
    this.provider = provider;
    this.map = map;
    this.ready = true;
    const q = this.queue.splice(0);
    q.forEach(fn => { try { fn(this.map, this.provider); } catch (e) { console.warn(e); } });
    this.clickListeners.forEach(h => this.on('click', h));
    this.clickListeners = [];
  }

  remove() {
    try { [...markers, ...routeLayers].forEach(l => this.removeLayer(l)); } catch (_) {}
    const el = document.getElementById(this.containerId);
    if (el) el.innerHTML = '';
    this.ready = false;
    this.map = null;
  }

  removeLayer(layer) {
    if (!layer) return;
    if (typeof layer.remove === 'function') return layer.remove();
    if (typeof layer.setMap === 'function') return layer.setMap(null);
    if (NativeLeaflet && this.map && typeof this.map.removeLayer === 'function') {
      try { this.map.removeLayer(layer); } catch (_) {}
    }
  }

  flyTo(latlng, zoom) {
    const p = latLngObj(latlng);
    this.whenReady((map, provider) => {
      if (provider === 'google') {
        map.panTo(p);
        if (zoom) map.setZoom(zoom);
      } else if (map.flyTo) {
        map.flyTo([p.lat, p.lng], zoom || map.getZoom(), { duration: 1.2 });
      } else if (map.setView) {
        map.setView([p.lat, p.lng], zoom || 13);
      }
    });
  }

  on(eventName, handler) {
    if (eventName !== 'click') return;
    if (!this.ready) { this.clickListeners.push(handler); return; }
    if (this.provider === 'google') {
      google.maps.event.addListener(this.map, 'click', (ev) => {
        handler({ latlng: { lat: ev.latLng.lat(), lng: ev.latLng.lng() } });
      });
    } else if (this.map && this.map.on) {
      this.map.on('click', handler);
    }
  }
}

class MarkerAdapter {
  constructor(latlng, options = {}) {
    this.latlng = latLngArr(latlng);
    this.options = options;
    this.native = null;
    this.infoWindow = null;
    this.popupHtml = '';
  }
  addTo(mapAdapter) {
    mapAdapter.whenReady((map, provider) => {
      if (provider === 'google') {
        const icon = this.options.icon || {};
        const content = makeHtmlElement(icon.html || '<div style="font-size:26px">📍</div>');
        const labelText = (content.textContent || '📍').trim().slice(0, 12);
        this.native = new google.maps.Marker({
          map,
          position: { lat: this.latlng[0], lng: this.latlng[1] },
          label: { text: labelText, fontSize: '18px', fontWeight: '900' },
          zIndex: this.options.zIndexOffset || 1,
          optimized: false,
        });
        this.native.addListener('click', () => this.openPopup());
      } else if (NativeLeaflet) {
        const opts = { ...this.options };
        if (opts.icon && opts.icon.__divIcon) opts.icon = NativeLeaflet.divIcon(opts.icon);
        this.native = NativeLeaflet.marker(this.latlng, opts).addTo(map);
        if (this.popupHtml) this.native.bindPopup(this.popupHtml);
      }
    });
    return this;
  }
  bindPopup(html) { this.popupHtml = html; if (this.native && this.native.bindPopup) this.native.bindPopup(html); return this; }
  openPopup() {
    if (!this.native || !this.popupHtml) return this;
    if (this.native.openPopup) this.native.openPopup();
    else {
      this.infoWindow = this.infoWindow || new google.maps.InfoWindow();
      this.infoWindow.setContent(this.popupHtml);
      const gmap = this.native.getMap ? this.native.getMap() : this.native.map;
      this.infoWindow.open({ anchor: this.native, map: gmap });
    }
    return this;
  }
  setPopupContent(html) { this.popupHtml = html; if (this.native && this.native.setPopupContent) this.native.setPopupContent(html); return this; }
  setLatLng(latlng) {
    this.latlng = latLngArr(latlng);
    if (this.native) {
      if (this.native.setLatLng) this.native.setLatLng(this.latlng);
      else if (this.native.setPosition) this.native.setPosition({ lat: this.latlng[0], lng: this.latlng[1] });
      else if ('position' in this.native) this.native.position = { lat: this.latlng[0], lng: this.latlng[1] };
    }
    return this;
  }
  setIcon(icon) {
    this.options.icon = icon;
    if (this.native) {
      if (this.native.setIcon && NativeLeaflet && icon) {
        const nativeIcon = icon.__divIcon ? NativeLeaflet.divIcon(icon) : icon;
        this.native.setIcon(nativeIcon);
      }
      else if (this.native.setLabel && icon && icon.html) this.native.setLabel({ text: (makeHtmlElement(icon.html).textContent || '📍').trim().slice(0, 12), fontSize: '18px', fontWeight: '900' });
    }
    return this;
  }
  remove() {
    if (!this.native) return;
    if (this.native.remove) this.native.remove();
    else if (this.native.setMap) this.native.setMap(null);
    else if (this.native.map) this.native.map = null;
  }
}

class PolylineAdapter {
  constructor(coords, options = {}) { this.coords = coords || []; this.options = options; this.native = null; this.popupHtml = ''; }
  addTo(mapAdapter) {
    mapAdapter.whenReady((map, provider) => {
      if (provider === 'google') {
        this.native = new google.maps.Polyline({
          map,
          path: this.coords.map(c => latLngObj(c)),
          strokeColor: this.options.color || '#06b6d4',
          strokeOpacity: this.options.opacity ?? 0.9,
          strokeWeight: this.options.weight || 4,
        });
        if (this.popupHtml) {
          this.native.addListener('click', (ev) => {
            const info = new google.maps.InfoWindow({ content: this.popupHtml, position: ev.latLng });
            info.open({ map });
          });
        }
      } else if (NativeLeaflet) {
        this.native = NativeLeaflet.polyline(this.coords, this.options).addTo(map);
        if (this.popupHtml) this.native.bindPopup(this.popupHtml);
      }
    });
    return this;
  }
  bindPopup(html) { this.popupHtml = html; if (this.native && this.native.bindPopup) this.native.bindPopup(html); return this; }
  remove() { if (!this.native) return; if (this.native.remove) this.native.remove(); else if (this.native.setMap) this.native.setMap(null); }
}

class CircleAdapter {
  constructor(latlng, options = {}) { this.latlng = latLngObj(latlng); this.options = options; this.native = null; this.popupHtml = ''; }
  addTo(mapAdapter) {
    mapAdapter.whenReady((map, provider) => {
      if (provider === 'google') {
        this.native = new google.maps.Circle({
          map,
          center: this.latlng,
          radius: this.options.radius || 200,
          strokeColor: this.options.color || '#f97316',
          strokeOpacity: this.options.opacity ?? 0.7,
          strokeWeight: this.options.weight || 2,
          fillColor: this.options.fillColor || this.options.color || '#f97316',
          fillOpacity: this.options.fillOpacity ?? 0.08,
        });
        if (this.popupHtml) this.native.addListener('click', () => new google.maps.InfoWindow({ content: this.popupHtml, position: this.latlng }).open({ map }));
      } else if (NativeLeaflet) {
        this.native = NativeLeaflet.circle([this.latlng.lat, this.latlng.lng], this.options).addTo(map);
        if (this.popupHtml) this.native.bindPopup(this.popupHtml);
      }
    });
    return this;
  }
  bindPopup(html) { this.popupHtml = html; if (this.native && this.native.bindPopup) this.native.bindPopup(html); return this; }
  remove() { if (!this.native) return; if (this.native.remove) this.native.remove(); else if (this.native.setMap) this.native.setMap(null); }
}

// Override L with a compatibility layer. NativeLeaflet remains available for fallback map creation.
window.L = {
  divIcon: (opts) => ({ ...(opts || {}), __divIcon: true }),
  marker: (latlng, opts) => new MarkerAdapter(latlng, opts),
  polyline: (coords, opts) => new PolylineAdapter(coords, opts),
  circle: (latlng, opts) => new CircleAdapter(latlng, opts),
};

async function loadFrontendConfig() {
  if (_frontendConfigPromise) return _frontendConfigPromise;
  _frontendConfigPromise = fetch('/api/frontend-config')
    .then(r => r.ok ? r.json() : {})
    .catch(() => ({}));
  return _frontendConfigPromise;
}

function loadGoogleMaps(key) {
  if (window.google && window.google.maps) return Promise.resolve();
  if (_googleMapsPromise) return _googleMapsPromise;
  _googleMapsPromise = new Promise((resolve, reject) => {
    const cb = '__sirsGoogleMapsReady';
    window[cb] = () => resolve();
    const script = document.createElement('script');
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(key)}&libraries=marker&callback=${cb}`;
    script.async = true;
    script.defer = true;
    script.onerror = reject;
    document.head.appendChild(script);
  });
  return _googleMapsPromise;
}

function createLeafletMap(adapter) {
  const el = document.getElementById(adapter.containerId);
  if (!NativeLeaflet || !el) {
    if (el) el.innerHTML = '<div style="padding:20px;color:#ef4444">Map engine unavailable</div>';
    return;
  }
  const m = NativeLeaflet.map(adapter.containerId, { zoomControl: true, attributionControl: false }).setView([adapter.lat, adapter.lng], adapter.zoom);
  NativeLeaflet.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', { maxZoom: 19, subdomains: 'abcd' }).addTo(m);
  NativeLeaflet.control.attribution({ prefix: 'S.I.R.S Riyadh — OpenStreetMap' }).addTo(m);
  adapter.setReady('leaflet', m);
}

function createGoogleMap(adapter) {
  const el = document.getElementById(adapter.containerId);
  if (!el) return;
  const map = new google.maps.Map(el, {
    center: { lat: adapter.lat, lng: adapter.lng },
    zoom: adapter.zoom,
    streetViewControl: false,
    fullscreenControl: true,
    mapTypeControl: false,
    clickableIcons: true,
    gestureHandling: 'greedy',
    styles: [
      { featureType: 'poi', elementType: 'labels', stylers: [{ visibility: 'off' }] },
      { featureType: 'transit', elementType: 'labels', stylers: [{ visibility: 'off' }] },
    ],
  });
  adapter.setReady('google', map);
}

function initMap(containerId = 'map', lat = 24.7136, lng = 46.6753, zoom = 13) {
  if (mapInstance) { mapInstance.remove(); mapInstance = null; }
  mapInstance = new MapAdapter(containerId, lat, lng, zoom);

  loadFrontendConfig().then(cfg => {
    const key = cfg.google_maps_browser_key;
    if (cfg.google_maps_enabled && key) {
      loadGoogleMaps(key).then(() => createGoogleMap(mapInstance)).catch(() => createLeafletMap(mapInstance));
    } else {
      createLeafletMap(mapInstance);
    }
  });

  return mapInstance;
}

function clearMap() {
  mapAnimations.forEach(id => {
    try { cancelAnimationFrame(id); } catch (_) { try { clearTimeout(id); } catch (__) {} }
  });
  mapAnimations = [];
  markers.forEach(m => mapInstance && mapInstance.removeLayer(m));
  routeLayers.forEach(l => mapInstance && mapInstance.removeLayer(l));
  markers = []; routeLayers = [];
}

function makeIcon(emoji, color, size) {
  color = color || '#06b6d4';
  size = size || 36;
  return L.divIcon({
    className: '',
    html: '<div style="width:' + size + 'px;height:' + size + 'px;background:' + color + '22;border:2px solid ' + color + ';border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:' + Math.round(size * 0.45) + 'px;box-shadow:0 0 12px ' + color + '66">' + emoji + '</div>',
    iconSize: [size, size], iconAnchor: [size / 2, size / 2]
  });
}

function makeEvIcon(vehicleType, congestionLevel, arrived) {
  const emojis = { 'Ambulance': '🚑', 'Police Car': '🚔', 'Traffic Unit': '🚓', 'Road Service': '🛻', 'Fire Truck': '🚒', 'Civil Defense': '🛡️' };
  const emoji = arrived ? '✅' : (emojis[vehicleType] || '🚨');
  const colors = { 'Low': '#10b981', 'Medium': '#22d3ee', 'High': '#f97316', 'Critical': '#ef4444' };
  const color = arrived ? '#10b981' : (colors[congestionLevel] || '#22d3ee');
  const size = 38;
  return L.divIcon({
    className: '',
    html: '<div style="width:' + size + 'px;height:' + size + 'px;background:#020617ee;border:2px solid ' + color + ';border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:20px;box-shadow:0 0 16px ' + color + '88">' + emoji + '</div>',
    iconSize: [size, size], iconAnchor: [size / 2, size / 2]
  });
}

function makeIntersectionIcon(priorityLevel) {
  const colors = { 'Critical': '#ef4444', 'High': '#f97316', 'Medium': '#eab308' };
  const color = colors[priorityLevel] || '#f97316';
  return L.divIcon({
    className: '',
    html: '<div style="width:30px;height:30px;background:' + color + '33;border:2px solid ' + color + ';border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:16px;box-shadow:0 0 10px ' + color + 'aa">🚦</div>',
    iconSize: [30, 30], iconAnchor: [15, 15]
  });
}


function routeIsReal(evData) {
  return evData && (evData.routeProvider === 'osrm' || evData.routeProvider === 'google_routes');
}

function isRealTrafficRoute(trafficFindings) {
  return trafficFindings && (trafficFindings.traffic_route_source === 'osrm' || trafficFindings.traffic_route_source === 'google_routes');
}

function routeStyleForVehicle(evData, baseColor) {
  const isPrimary = evData.role === 'primary' || evData.vehicleIndex === 0;
  return {
    color: baseColor || evData.color || '#06b6d4',
    weight: isPrimary ? 6 : 3,
    opacity: isPrimary ? 0.95 : 0.55,
    dashArray: isPrimary ? '14,5' : '8,6'
  };
}

function isCommandCenterMap() {
  return /command-center/i.test(window.location.pathname || '') || !!document.getElementById('command-map');
}

function pointDistance(a, b) {
  const dx = (Number(a[0]) || 0) - (Number(b[0]) || 0);
  const dy = (Number(a[1]) || 0) - (Number(b[1]) || 0);
  return Math.sqrt(dx * dx + dy * dy);
}

function interpolateRoute(route, progress) {
  if (!route || route.length < 2) return route && route[0] ? route[0] : [0, 0];
  const lengths = [];
  let total = 0;
  for (let i = 0; i < route.length - 1; i++) {
    const d = Math.max(0.0000001, pointDistance(route[i], route[i + 1]));
    lengths.push(d); total += d;
  }
  let target = total * Math.max(0, Math.min(1, progress));
  for (let i = 0; i < lengths.length; i++) {
    if (target <= lengths[i]) {
      const t = target / lengths[i];
      return [
        route[i][0] + (route[i + 1][0] - route[i][0]) * t,
        route[i][1] + (route[i + 1][1] - route[i][1]) * t,
      ];
    }
    target -= lengths[i];
  }
  return route[route.length - 1];
}

function animateMarkerAlongRoute(marker, route, durationMs, onDone) {
  if (!marker || !route || route.length < 2) return;
  const started = performance.now();
  const run = (now) => {
    const p = Math.min(1, (now - started) / durationMs);
    marker.setLatLng(interpolateRoute(route, p));
    if (p < 1) {
      const id = requestAnimationFrame(run);
      mapAnimations.push(id);
    } else if (onDone) {
      onDone();
    }
  };
  const id = requestAnimationFrame(run);
  mapAnimations.push(id);
}


function addIncidentMarker(lat, lng, incType, severity) {
  if (!mapInstance) return;
  const emojis = { 'Traffic Accident': '💥', 'Fire Incident': '🔥', 'Road Blockage': '🚧', 'Fuel Spill': '⛽', 'Medical Emergency': '🚑' };
  const emoji = emojis[incType] || '🚨';
  const colors = { Low: '#10b981', Medium: '#eab308', High: '#f97316', Critical: '#ef4444' };
  const color = colors[severity] || '#ef4444';
  const m = L.marker([lat, lng], { icon: makeIcon(emoji, color, 42) })
    .addTo(mapInstance)
    .bindPopup('<b style="color:' + color + '">' + incType + '</b><br>Severity: ' + severity + '<br>📍 ' + Number(lat).toFixed(4) + ', ' + Number(lng).toFixed(4));
  setTimeout(() => m.openPopup(), 350);
  markers.push(m);
  mapInstance.flyTo([lat, lng], 14);
  return m;
}

function addCityInfrastructure(cityData) {
  if (!mapInstance || !cityData) return;
  (cityData.hospitals || []).forEach(function(h) {
    var m = L.marker([h.lat, h.lng], { icon: makeIcon('🏥', '#06b6d4', 30) })
      .addTo(mapInstance).bindPopup('<b>' + h.name + '</b><br>Capacity: ' + h.capacity + '<br>Ambulances: ' + h.ambulances);
    markers.push(m);
  });
  (cityData.fire_stations || []).forEach(function(f) {
    var m = L.marker([f.lat, f.lng], { icon: makeIcon('🚒', '#f97316', 30) })
      .addTo(mapInstance).bindPopup('<b>' + f.name + '</b><br>Units: ' + f.units);
    markers.push(m);
  });
  (cityData.police_stations || []).forEach(function(p) {
    var m = L.marker([p.lat, p.lng], { icon: makeIcon('👮', '#3b82f6', 30) })
      .addTo(mapInstance).bindPopup('<b>' + p.name + '</b><br>Units: ' + p.units);
    markers.push(m);
  });
  (cityData.ambulance_bases || []).forEach(function(a) {
    var m = L.marker([a.lat, a.lng], { icon: makeIcon('🚑', '#06b6d4', 28) })
      .addTo(mapInstance).bindPopup('<b>' + a.name + '</b><br>EMS dispatch base<br>Units: ' + (a.units || '—'));
    markers.push(m);
  });
  (cityData.traffic_units || []).forEach(function(t) {
    var m = L.marker([t.lat, t.lng], { icon: makeIcon('🚓', '#22c55e', 28) })
      .addTo(mapInstance).bindPopup('<b>' + t.name + '</b><br>Traffic response unit<br>Units: ' + (t.units || '—'));
    markers.push(m);
  });
  (cityData.road_service_units || []).forEach(function(r) {
    var m = L.marker([r.lat, r.lng], { icon: makeIcon('🛻', '#eab308', 28) })
      .addTo(mapInstance).bindPopup('<b>' + r.name + '</b><br>Road clearance / tow support<br>Units: ' + (r.units || '—'));
    markers.push(m);
  });
}

function drawRoute(coords, color, label) {
  color = color || '#ef4444';
  label = label || 'Emergency Route';
  if (!mapInstance || !coords || coords.length < 2) return;
  var line = L.polyline(coords, { color: color, weight: 4, opacity: 0.85, dashArray: '8,4' }).addTo(mapInstance);
  line.bindPopup('<b>' + label + '</b>');
  routeLayers.push(line);
  return line;
}

function drawRiskCircle(lat, lng, radiusM, color) {
  color = color || '#f97316';
  if (!mapInstance) return;
  var circle = L.circle([lat, lng], {
    radius: radiusM, color: color, fillColor: color,
    fillOpacity: 0.08, weight: 2, dashArray: '6,4', opacity: 0.6
  }).addTo(mapInstance);
  circle.bindPopup('⚠️ Environmental Risk Zone — ' + radiusM + 'm radius');
  routeLayers.push(circle);
}

function drawBlockedRoads(coords, color) {
  color = color || '#ef4444';
  if (!mapInstance || !coords || coords.length < 2) return;
  var line = L.polyline(coords, { color: color, weight: 5, opacity: 0.9 }).addTo(mapInstance);
  line.bindPopup('🚧 Road Blocked');
  routeLayers.push(line);
}

function drawAltRoute(coords) {
  if (!mapInstance || !coords || coords.length < 2) return;
  var line = L.polyline(coords, { color: '#10b981', weight: 3, opacity: 0.75, dashArray: '10,5' }).addTo(mapInstance);
  line.bindPopup('🔀 Alternative Route (Civilian Diversion)');
  routeLayers.push(line);
}

function renderEvOnMap(evData, options) {
  options = options || {};
  if (!mapInstance || !evData) return;
  var type = evData.type || 'Ambulance';
  var congestion = evData.currentCongestionLevel || 'High';
  var compactMode = options.compact !== undefined ? options.compact : isCommandCenterMap();
  var animateVehicle = options.animate !== undefined ? options.animate : isCommandCenterMap();
  var lat = evData.latitude;
  var lng = evData.longitude;
  if (!lat || !lng) return;

  var isRealRoute = routeIsReal(evData);
  var isPrimary = evData.role === 'primary' || evData.vehicleIndex === 0;
  var providerBadge = evData.routeProvider === 'google_routes' ? 'Google route' : (evData.routeProvider === 'osrm' ? 'OSRM/OpenStreetMap route' : 'Route unavailable');
  var stationBadge = evData.stationSource === 'google_places' ? 'Google Places' : (evData.stationSource === 'riyadh_local_real' ? 'Riyadh station data' : 'Local dispatch data');
  var stuckMsg = evData.stuckInCongestion
    ? 'DELAYED in ' + congestion + ' congestion'
    : 'En route — ' + congestion + ' congestion';

  var evMarker = L.marker([lat, lng], { icon: makeEvIcon(type, congestion) })
    .addTo(mapInstance)
    .bindPopup(
      '<div style="min-width:240px;font-family:monospace">' +
      '<div style="font-size:14px;font-weight:900;margin-bottom:6px">' + (evData.emoji || '🚨') + ' ' + type + ' — ' + (evData.unitId || '') + '</div>' +
      '<div style="color:' + (evData.stuckInCongestion ? '#ef4444' : '#10b981') + ';font-weight:700;margin-bottom:8px">' + stuckMsg + '</div>' +
      '<table style="width:100%;font-size:12px;border-collapse:collapse">' +
      '<tr><td style="color:#94a3b8;padding:2px 0">Route</td><td style="font-weight:700;text-align:right">' + providerBadge + '</td></tr>' +
      '<tr><td style="color:#94a3b8;padding:2px 0">Dispatch Origin</td><td style="font-weight:700;text-align:right;font-size:11px">' + (evData.stationName || 'Dispatch Station') + '</td></tr>' +
      '<tr><td style="color:#94a3b8;padding:2px 0">Origin Source</td><td style="font-weight:700;text-align:right;font-size:11px">' + stationBadge + '</td></tr>' +
      '<tr><td style="color:#94a3b8;padding:2px 0">Distance</td><td style="font-weight:700;text-align:right">' + (evData.distanceToIncident || '—') + ' km</td></tr>' +
      '<tr><td style="color:#94a3b8;padding:2px 0">Normal ETA</td><td style="font-weight:700;text-align:right;color:#94a3b8">' + (evData.normalEta || '—') + ' min</td></tr>' +
      '<tr><td style="color:#94a3b8;padding:2px 0">Priority ETA</td><td style="font-weight:900;text-align:right;color:#10b981">' + (evData.priorityEta || '—') + ' min</td></tr>' +
      '<tr><td style="color:#94a3b8;padding:2px 0">Status</td><td style="font-weight:700;text-align:right;color:#f97316;font-size:11px">' + (evData.routeStatus || '—') + '</td></tr>' +
      (!isRealRoute ? '<tr><td colspan="2" style="color:#f59e0b;padding-top:6px;font-size:10px">OSRM route unavailable. No straight fallback line is drawn.</td></tr>' : '') +
      '</table></div>'
    );
  markers.push(evMarker);

  var routeForVehicle = (evData.priorityRoute && evData.priorityRoute.length >= 2) ? evData.priorityRoute : [];

  // Important: never draw fallback geometry. It creates straight artificial
  // lines across buildings. Draw roads only when OSRM/Google returned real road geometry.
  if (!isRealRoute) return;

  if (!compactMode && evData.normalRoute && evData.normalRoute.length >= 2 && isPrimary) {
    var normalLine = L.polyline(evData.normalRoute, { color: '#64748b', weight: 2, opacity: 0.45, dashArray: '6,6' }).addTo(mapInstance);
    normalLine.bindPopup('Normal route — ETA: ' + (evData.normalEta || '?') + ' min');
    routeLayers.push(normalLine);
  }

  if (routeForVehicle.length >= 2) {
    var style = routeStyleForVehicle(evData, evData.color || '#06b6d4');
    if (compactMode) { style.weight = isPrimary ? 5 : 3; style.opacity = isPrimary ? 0.9 : 0.45; style.dashArray = isPrimary ? '10,5' : '5,7'; }
    var priorityLine = L.polyline(routeForVehicle, style).addTo(mapInstance);
    priorityLine.bindPopup('<b>Emergency Road Route</b><br>' + type + ' — ' + (evData.unitId || '') + '<br>Source: OSRM/OpenStreetMap<br>Priority ETA: ' + (evData.priorityEta || '?') + ' min');
    routeLayers.push(priorityLine);
    if (animateVehicle) {
      evMarker.setLatLng(routeForVehicle[0]);
      const duration = Math.min(18000, Math.max(8000, (Number(evData.priorityEta) || 6) * 1200));
      animateMarkerAlongRoute(evMarker, routeForVehicle, duration, function() {
        evMarker.setIcon(makeEvIcon(type, congestion, true));
        evMarker.setPopupContent('<b style="color:#10b981">✅ ' + (evData.label || type) + ' arrived</b><br>Priority ETA completed.<br>Route source: OSRM/OpenStreetMap');
      });
    }
  }

  if (!compactMode && isPrimary && evData.congestedSegments && evData.congestedSegments.length >= 2) {
    var congLine = L.polyline(evData.congestedSegments, { color: '#ef4444', weight: 5, opacity: 0.65 }).addTo(mapInstance);
    congLine.bindPopup('Congested section detected on route');
    routeLayers.push(congLine);
  }

  if (!compactMode && isPrimary && evData.clearedSegments && evData.clearedSegments.length >= 2) {
    var clearedLine = L.polyline(evData.clearedSegments, { color: '#10b981', weight: 4, opacity: 0.65, dashArray:'8,5' }).addTo(mapInstance);
    clearedLine.bindPopup('Emergency priority corridor / signal preemption zone');
    routeLayers.push(clearedLine);
  }

  if (!compactMode && isPrimary) {
    (evData.priorityIntersections || []).slice(0, 3).forEach(function(int, i) {
      var im = L.marker([int.lat, int.lng], { icon: makeIntersectionIcon(int.priorityLevel) })
        .addTo(mapInstance)
        .bindPopup('<div style="min-width:200px"><b style="color:#f97316">Signal Priority — Control Point ' + (i + 1) + '</b><br><b>' + int.name + '</b><br>Action: <b>' + int.action + '</b><br>Priority Level: <b style="color:' + (int.priorityLevel === 'Critical' ? '#ef4444' : '#eab308') + '">' + int.priorityLevel + '</b></div>');
      markers.push(im);
    });
  }
}

function renderIncidentOnMap(incident, agentResponses) {
  if (!mapInstance) return;
  clearMap();
  var lat = incident.latitude, lng = incident.longitude;
  addIncidentMarker(lat, lng, incident.type, incident.severity);

  var traffic = null, emergency = null, env = null;
  (agentResponses || []).forEach(function(a) {
    if (a.agent_name === 'Traffic Agent') traffic = a;
    if (a.agent_name === 'Emergency Agent') emergency = a;
    if (a.agent_name === 'Environment Agent') env = a;
  });

  if (traffic && !isCommandCenterMap()) {
    var tf = traffic.findings;
    // Traffic closure/diversion overlays are hidden in Command Center to avoid
    // noisy, unclear map lines. The Command Center map shows only emergency
    // vehicle road routes + incident/camera/hazard layers.
    if (isRealTrafficRoute(tf)) {
      if (tf.blocked_coords) drawBlockedRoads(tf.blocked_coords);
      if (tf.alt_route_coords) drawAltRoute(tf.alt_route_coords);
    }
  }
  if (emergency) {
    var ef = emergency.findings;
    if (ef.dispatched_fleet && ef.dispatched_fleet.length) {
      ef.dispatched_fleet.forEach(function(v) { renderEvOnMap(v, { animate: isCommandCenterMap(), compact: isCommandCenterMap() }); });
    } else if (ef.selected_vehicle) {
      renderEvOnMap(ef.selected_vehicle);
    } else if (ef.emergency_route_coords) {
      drawRoute(ef.emergency_route_coords, '#ef4444', 'Emergency Dispatch Route');
    }
  }
  if (incident.camera_detection && incident.camera_detection.coordinates) {
    var c = incident.camera_detection.coordinates;
    var camIcon = L.divIcon({ className:'', html:'<div style="background:#020617;border:2px solid #22d3ee;color:#22d3ee;border-radius:10px;padding:5px 8px;font-size:16px;box-shadow:0 0 16px #22d3ee55">📹</div>', iconAnchor:[18,18] });
    var cm = L.marker([c.lat, c.lng], { icon: camIcon }).addTo(mapInstance).bindPopup('<b>Camera Source</b><br>' + (incident.camera_id || incident.camera_detection.camera_id || 'Camera'));
    markers.push(cm);
  }
  if (env) {
    var envf = env.findings;
    if (envf.risk_coords) drawRiskCircle(envf.risk_coords.lat, envf.risk_coords.lng, envf.risk_coords.radius_m);
  }
}

window.initMap = initMap;
window.clearMap = clearMap;
window.makeIcon = makeIcon;
window.addIncidentMarker = addIncidentMarker;
window.addCityInfrastructure = addCityInfrastructure;
window.drawRoute = drawRoute;
window.drawRiskCircle = drawRiskCircle;
window.drawBlockedRoads = drawBlockedRoads;
window.drawAltRoute = drawAltRoute;
window.renderIncidentOnMap = renderIncidentOnMap;
window.renderEvOnMap = renderEvOnMap;
