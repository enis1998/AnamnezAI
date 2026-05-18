/**
 * AnamnezAI — Service Worker v5.0
 * Sprint 4: Offline support, background sync, cache strategy
 */

const CACHE_NAME = 'anamnezai-v31';
const APP_VERSION = '2026.05.18-v31-no-swupdate';
const STATIC_ASSETS = [
  '/',
  // HTML files intentionally excluded — always fetch from network (must be fresh)
  '/manifest.json',
];

// ── Install: cache static shell
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return Promise.allSettled(
        STATIC_ASSETS.map(url => cache.add(url).catch(() => { /* ignore missing */ }))
      );
    })
  );
  self.skipWaiting();
});

// ── Activate: clean old caches + notify clients of update (only when upgrading)
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => {
      const oldCacheExists = keys.some(k => k !== CACHE_NAME && k.startsWith('anamnezai-'));
      return Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
      ).then(() => {
        self.clients.claim();
        // SW update notifications removed - pages should not reload on SW update
        }););
          });
        }
      });
    })
  );
});

// ── Fetch: network-first for API, cache-first for static
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);

  // API & auth calls: network only (never cache patient data)
  // /p/ = neutral proxy path for OAuth bypass
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/auth/') || url.pathname.startsWith('/p/')) {
    event.respondWith(
      fetch(event.request).catch(() =>
        new Response(JSON.stringify({ error: 'offline', message: 'No network connection.' }), {
          status: 503,
          headers: { 'Content-Type': 'application/json' },
        })
      )
    );
    return;
  }

  // HTML files: ALWAYS network-only (must be fresh, never stale)
  if (url.pathname.endsWith('.html') || url.pathname === '/' || url.pathname === '/clearcache.html') {
    event.respondWith(
      fetch(event.request, { cache: 'no-store' })
        .catch(() => new Response('Offline', { status: 503 }))
    );
    return;
  }

  // Static assets: network-first, fallback to cache
  event.respondWith(
    fetch(event.request)
      .then(response => {
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        }
        return response;
      })
      .catch(() => caches.match(event.request).then(cached => {
        if (cached) return cached;
        // Offline fallback page
        if (event.request.mode === 'navigate') {
          return caches.match('/index.html');
        }
        return new Response('Offline', { status: 503 });
      }))
  );
});

// ── Background Sync: retry failed API calls when online
self.addEventListener('sync', event => {
  if (event.tag === 'anamnez-sync') {
    event.waitUntil(syncPendingAnswers());
  }
});

async function syncPendingAnswers() {
  // Retrieve any cached offline answers from IndexedDB and retry
  // This is a placeholder — full offline queue stored in IDB
  console.log('[SW] Background sync triggered');
}

// ── Push: triage result notification (Sprint 4)
self.addEventListener('push', event => {
  if (!event.data) return;
  const data = event.data.json();
  event.waitUntil(
    self.registration.showNotification(data.title || 'AnamnezAI', {
      body: data.body || 'Triaj durumunuzda güncelleme var.',
      icon: '/manifest.json',
      badge: '/manifest.json',
      tag: data.tag || 'anamnezai',
      data: { url: data.url || '/' },
    })
  );
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const url = event.notification.data?.url || '/';
  event.waitUntil(clients.openWindow(url));
});
