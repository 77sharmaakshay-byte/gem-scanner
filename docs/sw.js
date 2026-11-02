/* Scan by Akshay -- service worker.
   Shell cache se chalta hai (app turant khulta hai), feed hamesha network
   se pehle try hoti hai aur fail hone par cache se aati hai. */
var CACHE = 'sba-v10';
var SHELL = [
  './',
  'index.html',
  'styles.css?v=10',
  'shell.js?v=10',
  'app.js?v=10',
  'views.js?v=10',
  'manifest.webmanifest',
  'icon.svg'
];

self.addEventListener('install', function (ev) {
  ev.waitUntil(
    caches.open(CACHE).then(function (cache) {
      return cache.addAll(SHELL);
    }).then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener('activate', function (ev) {
  ev.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.map(function (k) {
        return k === CACHE ? null : caches.delete(k);
      }));
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener('fetch', function (ev) {
  var req = ev.request;
  if (req.method !== 'GET') return;

  var url = new URL(req.url);
  if (url.origin !== self.location.origin) return;   // GitHub API ko chhod do

  if (url.pathname.indexOf('feed.json') >= 0) {
    ev.respondWith(
      fetch(req).then(function (res) {
        var copy = res.clone();
        caches.open(CACHE).then(function (c) { c.put('feed.json', copy); });
        return res;
      }).catch(function () {
        return caches.match('feed.json');
      })
    );
    return;
  }

  ev.respondWith(
    caches.match(req).then(function (hit) {
      if (hit) return hit;
      return fetch(req).then(function (res) {
        if (res.ok && res.type === 'basic') {
          var copy = res.clone();
          caches.open(CACHE).then(function (c) { c.put(req, copy); });
        }
        return res;
      });
    })
  );
});
