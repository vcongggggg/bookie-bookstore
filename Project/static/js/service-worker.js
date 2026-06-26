/**
 * Bookie Reader – Service Worker
 * Caches reader pages for offline reading.
 *
 * Strategy:
 *  - App Shell (CSS, JS, fonts): Cache-First
 *  - Reader pages (/books/<id>/read/): Network-First, fallback to cache
 *  - API calls: Network-Only
 */

const CACHE_VERSION = 'bookie-v2';
const STATIC_CACHE = `static-${CACHE_VERSION}`;
const READER_CACHE = `reader-${CACHE_VERSION}`;

// Static assets to pre-cache on install
const PRECACHE_URLS = [
    '/static/manifest.json',
];

// ─── Install ────────────────────────────────────────────────────
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then((cache) => cache.addAll(PRECACHE_URLS))
            .then(() => self.skipWaiting())
    );
});

// ─── Activate – clean old caches ────────────────────────────────
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(
                keys
                    .filter((key) => (
                        key !== STATIC_CACHE &&
                        key !== READER_CACHE &&
                        (
                            key.startsWith('static-bookie-') ||
                            key.startsWith('reader-bookie-') ||
                            key.startsWith('static-') ||
                            key.startsWith('reader-')
                        )
                    ))
                    .map((key) => caches.delete(key))
            )
        ).then(() => self.clients.claim())
    );
});

// ─── Fetch ──────────────────────────────────────────────────────
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // Skip non-GET and cross-origin requests
    if (request.method !== 'GET' || url.origin !== self.location.origin) {
        return;
    }

    // Skip API, admin, and auth routes
    if (
        url.pathname.startsWith('/api/') ||
        url.pathname.startsWith('/admin/') ||
        url.pathname.startsWith('/login') ||
        url.pathname.startsWith('/logout') ||
        url.pathname.startsWith('/password-reset')
    ) {
        return;
    }

    // Reader pages → Network-First with cache fallback
    if (/\/books\/\d+\/read\/?$/.test(url.pathname)) {
        event.respondWith(networkFirstWithCache(request, READER_CACHE));
        return;
    }

    // Static assets (CSS, JS, fonts, images) → Cache-First
    if (
        url.pathname.startsWith('/static/') ||
        url.hostname === 'fonts.googleapis.com' ||
        url.hostname === 'fonts.gstatic.com' ||
        url.hostname === 'cdn.jsdelivr.net'
    ) {
        event.respondWith(cacheFirst(request, STATIC_CACHE));
        return;
    }
});

// ─── Strategies ─────────────────────────────────────────────────

/**
 * Network-First: try network, fall back to cache.
 * On success, update the cache for next offline use.
 */
async function networkFirstWithCache(request, cacheName) {
    try {
        const networkResponse = await fetch(request);
        if (networkResponse.ok) {
            const cache = await caches.open(cacheName);
            cache.put(request, networkResponse.clone());
        }
        return networkResponse;
    } catch {
        const cached = await caches.match(request);
        if (cached) {
            return cached;
        }
        return new Response(
            offlineFallbackHTML(),
            { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } }
        );
    }
}

/**
 * Cache-First: serve from cache if available, else fetch and cache.
 */
async function cacheFirst(request, cacheName) {
    const cached = await caches.match(request);
    if (cached) {
        return cached;
    }
    try {
        const networkResponse = await fetch(request);
        if (networkResponse.ok) {
            const cache = await caches.open(cacheName);
            cache.put(request, networkResponse.clone());
        }
        return networkResponse;
    } catch {
        return new Response('', { status: 504 });
    }
}

// ─── Offline fallback page ──────────────────────────────────────
function offlineFallbackHTML() {
    return `<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Bookie – Đang ngoại tuyến</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: #F7F2EA;
            color: #2D2A26;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            text-align: center;
            padding: 2rem;
        }
        .offline-card {
            max-width: 420px;
            background: #fff;
            border-radius: 16px;
            padding: 3rem 2rem;
            box-shadow: 0 8px 32px rgba(0,0,0,.08);
        }
        .offline-icon {
            font-size: 3.5rem;
            margin-bottom: 1rem;
        }
        h1 {
            font-size: 1.5rem;
            margin-bottom: .5rem;
            color: #2D2A26;
        }
        p {
            color: #6B5E52;
            line-height: 1.6;
            margin-bottom: 1.5rem;
        }
        .btn-retry {
            display: inline-block;
            padding: .75rem 2rem;
            background: #2D2A26;
            color: #fff;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            cursor: pointer;
            transition: opacity .2s;
        }
        .btn-retry:hover { opacity: .85; }
    </style>
</head>
<body>
    <div class="offline-card">
        <div class="offline-icon">📚</div>
        <h1>Bạn đang ngoại tuyến</h1>
        <p>Chỉ có thể đọc các trang sách đã tải về trước đó.
           Hãy kết nối mạng để tiếp tục duyệt sách.</p>
        <button class="btn-retry" onclick="location.reload()">Thử lại</button>
    </div>
</body>
</html>`;
}
