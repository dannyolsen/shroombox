// Enhanced service-worker.js with better cache control
const CACHE_NAME = 'shroombox-cache-v2';
const STATIC_CACHE_URLS = [
  '/',
  '/static/js/main.js',
  '/static/style.css',
  '/static/css/navbar.css',
  '/static/js/navbar.js',
  '/static/images/logo.png'
];

// Install event - cache basic assets
self.addEventListener('install', event => {
  console.log('Service Worker installing');
  self.skipWaiting();
  
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Service Worker caching static assets');
        return cache.addAll(STATIC_CACHE_URLS);
      })
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
  console.log('Service Worker activating');
  self.clients.claim();
  
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.filter(cacheName => {
          return cacheName !== CACHE_NAME;
        }).map(cacheName => {
          console.log('Service Worker: clearing old cache', cacheName);
          return caches.delete(cacheName);
        })
      );
    })
  );
});

// Helper function to determine if a request is for an API endpoint
function isApiRequest(url) {
  return url.pathname.startsWith('/api/');
}

// Helper function to determine if a request is for a static asset
function isStaticAsset(url) {
  return url.pathname.startsWith('/static/') || 
         STATIC_CACHE_URLS.includes(url.pathname);
}

// Fetch event - network-first strategy for API, cache-first for static assets
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  
  // Skip non-GET requests
  if (event.request.method !== 'GET') {
    return;
  }
  
  // Skip cache for API requests - use network-first strategy
  if (isApiRequest(url)) {
    event.respondWith(
      fetch(event.request)
        .catch(() => {
          console.log('Service Worker: API fetch failed, returning error response');
          return new Response('Network error - API unavailable', {
            status: 503,
            headers: { 'Content-Type': 'text/plain' }
          });
        })
    );
    return;
  }
  
  // Cache-first strategy for static assets
  if (isStaticAsset(url)) {
    event.respondWith(
      caches.match(event.request)
        .then(cachedResponse => {
          if (cachedResponse) {
            // Return cached response immediately
            return cachedResponse;
          }
          
          // If not in cache, fetch from network and cache for future
          return fetch(event.request)
            .then(response => {
              // Don't cache non-successful responses
              if (!response || response.status !== 200) {
                return response;
              }
              
              // Clone the response to cache it and return it
              const responseToCache = response.clone();
              caches.open(CACHE_NAME)
                .then(cache => {
                  cache.put(event.request, responseToCache);
                });
                
              return response;
            })
            .catch(() => {
              console.log('Service Worker: fetch failed for static asset');
              return new Response('Network error - You are offline', {
                status: 503,
                headers: { 'Content-Type': 'text/plain' }
              });
            });
        })
    );
    return;
  }
  
  // For all other requests, try network first, then cache
  event.respondWith(
    fetch(event.request)
      .then(response => {
        // Cache successful responses for non-API requests
        if (response && response.status === 200 && !isApiRequest(url)) {
          const responseToCache = response.clone();
          caches.open(CACHE_NAME)
            .then(cache => {
              cache.put(event.request, responseToCache);
            });
        }
        return response;
      })
      .catch(() => {
        // If network fails, try to serve from cache
        return caches.match(event.request)
          .then(cachedResponse => {
            if (cachedResponse) {
              return cachedResponse;
            }
            
            // If not in cache either, return offline message
            return new Response('You are offline and this resource is not cached', {
              status: 503,
              headers: { 'Content-Type': 'text/plain' }
            });
          });
      })
  );
}); 