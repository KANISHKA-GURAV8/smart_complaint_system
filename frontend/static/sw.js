/* Awaaz Service Worker — Offline support + fast loading */

const CACHE_NAME = 'awaaz-v1.0';
const STATIC_ASSETS = [
  '/static/style.css',
  '/static/app.js',
  '/static/voice.js',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/manifest.json',
];

/* Install — cache all static assets */
self.addEventListener('install', evt => {
  evt.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(STATIC_ASSETS))
      .then(() => self.skipWaiting())
  );
});

/* Activate — remove old caches */
self.addEventListener('activate', evt => {
  evt.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

/* Fetch — serve from cache first, fallback to network */
self.addEventListener('fetch', evt => {
  // Skip non-GET and API calls — always go to network for those
  if (evt.request.method !== 'GET' || evt.request.url.includes('/api/')) {
    return;
  }

  evt.respondWith(
    caches.match(evt.request).then(cached => {
      if (cached) return cached;

      return fetch(evt.request).then(response => {
        // Cache static assets on the fly
        if (response.ok && (
          evt.request.url.includes('/static/') ||
          evt.request.url.includes('/uploads/')
        )) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(evt.request, clone));
        }
        return response;
      }).catch(() => {
        // Offline fallback for HTML pages
        if (evt.request.headers.get('accept').includes('text/html')) {
          return new Response(
            `<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
            <title>Awaaz — Offline</title>
            <style>body{background:#0F0F1A;color:#e2e8f0;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;flex-direction:column;gap:1rem;text-align:center;padding:2rem}
            .icon{font-size:4rem}h1{font-size:1.5rem;font-weight:800}p{color:#94a3b8;font-size:.9rem}</style>
            </head><body>
            <div class="icon">📵</div>
            <h1>You're Offline</h1>
            <p>Please check your internet connection and try again.</p>
            <button onclick="location.reload()" style="background:#6C63FF;color:#fff;border:none;padding:.75rem 1.5rem;border-radius:8px;font-size:1rem;cursor:pointer;margin-top:1rem">🔄 Retry</button>
            </body></html>`,
            { headers: { 'Content-Type': 'text/html' } }
          );
        }
      });
    })
  );
});
