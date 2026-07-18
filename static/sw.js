// 這個版本號只影響「整批清掉重建」，不是檔案新不新的唯一依據——下面的
// static asset 策略是 stale-while-revalidate（先回快取，同時在背景重新
// 打一次網路更新快取），忘記把版本號往上加也只會晚一次載入才拿到新檔案，
// 不會像純 cache-first 那樣永久卡住（這件事已經因為忘記加版本號發生過
// 兩次事故，改成這個策略是為了不要再依賴「記得手動加版本號」這件事）。
const CACHE_VERSION = 'v4';
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
    // stale-while-revalidate：有快取先立刻回應（快、離線也能用），同時
    // 在背景重新打網路更新快取——這次沒趕上，下一次載入就會是新的，
    // 不必靠手動加版本號才能讓使用者拿到新檔案。
    event.respondWith(
      caches.open(STATIC_CACHE).then((cache) =>
        cache.match(request).then((cached) => {
          const network = fetch(request)
            .then((response) => {
              if (response.ok) cache.put(request, response.clone());
              return response;
            })
            .catch(() => cached);
          return cached || network;
        })
      )
    );
    return;
  }

  // 首頁這種會動態變化的 HTML：先試網路，失敗（離線）才顯示離線頁。
  if (request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(fetch(request).catch(() => caches.match(OFFLINE_URL)));
  }
});
