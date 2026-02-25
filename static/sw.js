self.addEventListener('install', (e) => {
  console.log('[Service Worker] Install');
});
self.addEventListener('fetch', (e) => {
  // Standard Network fetch, später kann man hier Caching einbauen
  e.respondWith(fetch(e.request));
});