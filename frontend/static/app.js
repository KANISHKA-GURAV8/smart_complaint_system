/* app.js — Shared utilities used across all pages */

const API = '';  // same origin

/* ── Toast ──────────────────────────────────────────────────────────────────── */
function showToast(msg, type = 'info', duration = 3500) {
  const icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span class="toast-icon">${icons[type] || 'ℹ️'}</span><span>${msg}</span>`;
  container.appendChild(toast);
  setTimeout(() => { toast.style.animation = 'none'; toast.style.opacity = '0'; toast.style.transition = 'opacity .3s'; setTimeout(() => toast.remove(), 300); }, duration);
}

/* ── Loading overlay ────────────────────────────────────────────────────────── */
function showLoader(msg = 'Processing…') {
  let el = document.getElementById('global-loader');
  if (!el) {
    el = document.createElement('div');
    el.id = 'global-loader';
    el.className = 'loading-overlay';
    el.innerHTML = `<div class="spinner"></div><p id="loader-msg">${msg}</p>`;
    document.body.appendChild(el);
  } else {
    document.getElementById('loader-msg').textContent = msg;
    el.classList.remove('hidden');
  }
}
function hideLoader() {
  const el = document.getElementById('global-loader');
  if (el) el.classList.add('hidden');
}

/* ── API helpers ────────────────────────────────────────────────────────────── */
async function apiGet(url) {
  const r = await fetch(API + url, { credentials: 'include' });
  if (!r.ok) throw new Error((await r.json()).error || r.statusText);
  return r.json();
}

async function apiPost(url, body, isForm = false) {
  const opts = { method: 'POST', credentials: 'include' };
  if (isForm) { opts.body = body; }
  else { opts.headers = { 'Content-Type': 'application/json' }; opts.body = JSON.stringify(body); }
  const r = await fetch(API + url, opts);
  if (!r.ok) throw new Error((await r.json()).error || r.statusText);
  return r.json();
}

/* ── Status helpers ─────────────────────────────────────────────────────────── */
const STATUS_ORDER = ['received', 'assigned', 'in_progress', 'resolved'];
const STATUS_LABELS = {
  received:    { label: 'Received',    icon: '📥', desc: 'Your complaint has been registered.' },
  assigned:    { label: 'Assigned',    icon: '🏢', desc: 'Assigned to a nearby NGO / officer.' },
  in_progress: { label: 'In Progress', icon: '🔧', desc: 'Active investigation / work underway.' },
  resolved:    { label: 'Resolved',    icon: '✅', desc: 'Issue has been addressed and closed.' }
};

function statusBadge(status) {
  const s = STATUS_LABELS[status] || { label: status, icon: '❓' };
  return `<span class="badge badge-${status} badge-dot">${s.icon} ${s.label}</span>`;
}

function buildTimeline(currentStatus, logs = []) {
  const currentIdx = STATUS_ORDER.indexOf(currentStatus);
  return STATUS_ORDER.map((s, i) => {
    const info = STATUS_LABELS[s];
    const isDone   = i < currentIdx;
    const isActive = i === currentIdx;
    const cls = isDone ? 'done' : (isActive ? 'active' : '');
    const log = logs.find(l => l.action.toLowerCase().includes(s));
    const time = log ? fmtDate(log.timestamp) : '';
    return `
      <div class="timeline-step ${cls}">
        <div class="timeline-icon">${isDone ? '✓' : info.icon}</div>
        <div class="timeline-content">
          <div class="timeline-title">${info.label}</div>
          <div class="timeline-time">${time || info.desc}</div>
        </div>
      </div>`;
  }).join('');
}

/* ── Drag-and-drop upload zone ──────────────────────────────────────────────── */
function initUploadZone(zoneId, inputId, previewId) {
  const zone    = document.getElementById(zoneId);
  const input   = document.getElementById(inputId);
  const preview = document.getElementById(previewId);
  if (!zone || !input) return;

  zone.addEventListener('click', () => input.click());
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault(); zone.classList.remove('drag-over');
    addFiles(e.dataTransfer.files);
  });
  input.addEventListener('change', () => addFiles(input.files));

  function addFiles(files) {
    if (!preview) return;
    for (const file of files) {
      if (!file.type.startsWith('image/')) continue;
      const reader = new FileReader();
      reader.onload = e => {
        const div = document.createElement('div');
        div.className = 'preview-item';
        div.innerHTML = `<img src="${e.target.result}" alt="proof"><button class="preview-remove" title="Remove">✕</button>`;
        div.querySelector('.preview-remove').onclick = () => div.remove();
        preview.appendChild(div);
      };
      reader.readAsDataURL(file);
    }
  }
}

/* ── Geolocation ────────────────────────────────────────────────────────────── */
async function getLocation() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) { reject(new Error('Geolocation not supported')); return; }
    navigator.geolocation.getCurrentPosition(
      async pos => {
        const { latitude: lat, longitude: lon } = pos.coords;
        let name = `${lat.toFixed(4)}, ${lon.toFixed(4)}`;
        try {
          const r = await fetch(`https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lon}&format=json`);
          const d = await r.json();
          name = d.display_name || name;
        } catch (_) {}
        resolve({ lat, lon, name });
      },
      err => reject(err),
      { enableHighAccuracy: true, timeout: 8000 }
    );
  });
}

/* ── Date format ───────────────────────────────────────────────────────── */
function fmtDate(iso) {
  if (!iso) return '—';
  // Backend stores UTC without 'Z' suffix — append it so JS treats it as UTC
  const utcStr = (iso.endsWith('Z') || iso.includes('+')) ? iso : iso + 'Z';
  return new Date(utcStr).toLocaleString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
    timeZone: 'Asia/Kolkata'   // ← always show IST regardless of server timezone
  });
}

/* ── Copy to clipboard ──────────────────────────────────────────────────────── */
function copyText(text) {
  navigator.clipboard.writeText(text).then(() => showToast('Copied to clipboard!', 'success', 1800));
}
