// 改 /static/ 底下任何檔案都要記得把這個版本號往上加一，
// 不然舊版會被下面的 cache-first 策略永久卡住，使用者裝置永遠抓不到新檔案。
const CACHE_VERSION = 'v2';
const STATIC_CACHE = 'static-' + CACHE_VERSION;
const OFFLINE_URL = '/offline';
const PRECACHE_ASSETS = [
  '/static/css/style.css',
  '/static/js/app.js',
  '/static/js/tour.js',
  '/static/icon-192.png',
  '/static/icon-512.png',
  '/static/manifest.json',
  OFFLINE_URL,
];

// 這些路徑一定要打真的網路——登入狀態、CSRF、排經文、留領受都在這裡，
// 快取回應等於給使用者看到過期或錯誤的頁面。
const NETWORK_ONLY_PREFIXES = ['/login', '/logout', '/line/', '/admin', '/reflections', '/settings', '/export', '/healthz'];

function isNetworkOnly(url) {
  return NETWORK_ONLY_PREFIXES.some((p) => url.includes(p));
}

function isStaticAsset(url) {
  return url.includes('/static/');
}

function isGoogleFont(url) {
  return url.includes('fonts.googleapis.com') || url.includes('fonts.gstatic.com');
}

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(STATIC_CACHE).then((cache) => cache.addAll(PRECACHE_ASSETS)));
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== STATIC_CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = request.url;

  if (request.method !== 'GET') return;
  if (isNetworkOnly(url)) return;

  if (isStaticAsset(url) || isGoogleFont(url)) {
    event.respondWith(
      caches.match(request).then((cached) => {
        if (cached) return cached;
        return fetch(request).then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(STATIC_CACHE).then((cache) => cache.put(request, clone));
          }
          return response;
        });
      })
    );
    return;
  }

  // 首頁這種會動態變化的 HTML：先試網路，失敗（離線）才顯示離線頁。
  if (request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(fetch(request).catch(() => caches.match(OFFLINE_URL)));
  }
});
