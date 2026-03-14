const CACHE = 'polymarket-v2';

const SHELL = [
    '/',
    '/index.html',
    '/css/app.css',
    '/js/app.js',
    '/js/api.js',
    '/js/config.js',
    '/js/charts.js',
    '/js/router.js',
    '/js/theme.js',
    '/js/utils.js',
    '/js/screens/home.js',
    '/js/screens/markets.js',
    '/js/screens/marketDetail.js',
    '/js/screens/signals.js',
    '/js/screens/performance.js',
    '/js/screens/news.js',
    '/manifest.json',
    '/icons/icon-192.svg',
];

const CDN = [
    'https://cdn.jsdelivr.net/npm/chart.js@4',
    'https://telegram.org/js/telegram-web-app.js',
];

self.addEventListener('install', e => {
    e.waitUntil(
        caches.open(CACHE)
            .then(c => c.addAll(SHELL))
            .then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', e => {
    e.waitUntil(
        caches.keys()
            .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
            .then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', e => {
    const url = new URL(e.request.url);

    if (e.request.method !== 'GET') return;

    if (CDN.some(c => e.request.url.startsWith(c))) {
        e.respondWith(staleWhileRevalidate(e.request));
        return;
    }

    if (url.origin === self.location.origin) {
        e.respondWith(cacheFirst(e.request));
        return;
    }
});

async function cacheFirst(req) {
    const cached = await caches.match(req);
    if (cached) return cached;
    try {
        const res = await fetch(req);
        if (res.ok) {
            const c = await caches.open(CACHE);
            c.put(req, res.clone());
        }
        return res;
    } catch {
        if (req.mode === 'navigate') return caches.match('/index.html');
        return new Response('', { status: 408 });
    }
}

async function staleWhileRevalidate(req) {
    const cached = await caches.match(req);
    const fetchPromise = fetch(req).then(res => {
        if (res.ok) caches.open(CACHE).then(c => c.put(req, res.clone()));
        return res;
    }).catch(() => cached);
    return cached || fetchPromise;
}
