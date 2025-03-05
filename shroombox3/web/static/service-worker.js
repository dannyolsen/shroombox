// service-worker.js
self.addEventListener('install', event => {
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  event.respondWith(
    fetch(event.request).catch(() => new Response('Network error', {
      status: 408,
      headers: { 'Content-Type': 'text/plain' },
    }))
  );
}); 