const CACHE_NAME = "takapay-public-shell-v7";
const OFFLINE_PAGE = "/static/offline.html";

self.addEventListener("install", (event) => {
    event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.add(OFFLINE_PAGE)));
    self.skipWaiting();
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => Promise.all(
            cacheNames
                .filter((cacheName) => cacheName.startsWith("takapay-") && cacheName !== CACHE_NAME)
                .map((cacheName) => caches.delete(cacheName))
        )).then(() => self.clients.claim())
    );
});

self.addEventListener("fetch", (event) => {
    const request = event.request;
    const url = new URL(request.url);
    if (request.method !== "GET" || url.origin !== self.location.origin) return;

    if (request.mode === "navigate") {
        // Never store rendered pages: authenticated HTML can contain private data.
        event.respondWith(fetch(request).catch(() => caches.match(OFFLINE_PAGE)));
        return;
    }

    // Only public, same-origin static assets are eligible for offline caching.
    if (!url.pathname.startsWith("/static/")) return;
    event.respondWith(
        fetch(request).then((response) => {
            if (response.ok) {
                const copy = response.clone();
                return caches.open(CACHE_NAME).then((cache) => cache.put(request, copy)).then(() => response);
            }
            return response;
        }).catch(() => caches.match(request))
    );
});
