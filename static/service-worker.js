const CACHE_NAME = "takapay-foundation-v1";
const APP_SHELL = ["/"];

self.addEventListener("install", (event) => {
    event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)));
});

self.addEventListener("fetch", (event) => {
    event.respondWith(caches.match(event.request).then((cached) => cached || fetch(event.request)));
});