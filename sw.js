/* Service worker: makes the site installable and lets it open offline.
   Online: every request goes to the network (so the data is always fresh) and the
   answer is saved. Offline: the saved copy is used and marked (x-from-cache) so the
   page can say it is showing the last data it loaded. */
const CACHE = 'job-watcher-v1';
const SHELL = [
  './', 'index.html', 'browse.html', 'market.html', 'manifest.webmanifest',
  'assets/style.css', 'assets/common.js', 'assets/charts.js', 'assets/market-calc.js',
  'assets/icons/icon-192.png', 'assets/icons/icon-512.png',
  'data/status.json', 'data/history.csv'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) =>
      // one missing file (for example data before the first run) must not stop the install
      Promise.all(SHELL.map((url) => cache.add(url).catch(() => null)))
    ).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

function marked(response) {
  const headers = new Headers(response.headers);
  headers.set('x-from-cache', '1');
  return response.blob().then((body) => new Response(body, { status: response.status, statusText: response.statusText, headers }));
}

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== self.location.origin) return;
  event.respondWith(
    fetch(req, { cache: 'no-cache' })
      .then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((cache) => cache.put(req, copy));
        }
        return res;
      })
      .catch(() =>
        caches.match(req, { ignoreSearch: true }).then((hit) => {
          if (hit) return marked(hit);
          if (req.mode === 'navigate') return caches.match('index.html').then((p) => p || Response.error());
          return Response.error();
        })
      )
  );
});
