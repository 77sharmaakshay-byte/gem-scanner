/* Scan by Akshay -- service worker.
   Shell cache se chalta hai (app turant khulta hai), feed hamesha network
   se pehle try hoti hai aur fail hone par cache se aati hai. */
var CACHE = 'sba-v21';
var SHELL = [
  './',
  'index.html',
  'styles.css?v=21',
  'shell.js?v=21',
  'app.js?v=21',
  'views.js?v=21',
  'screens.js?v=21',
  'scan.js?v=21',
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

  // Page khud hamesha network se pehle. Pehle ye bhi cache-first tha, to
  // home screen wali app har baar PURANA index.html kholti thi -- usme
  // purane script version likhe hote hain, aur naya code kabhi pahunchta
  // hi nahi tha. Network fail ho to cache se (offline bhi chalti rahe).
  var isPage = req.mode === 'navigate' ||
    (req.headers.get('accept') || '').indexOf('text/html') >= 0;
  if (isPage) {
    ev.respondWith(
      fetch(req).then(function (res) {
        if (res.ok) {
          var copy = res.clone();
          caches.open(CACHE).then(function (c) {
            c.put('index.html', copy.clone());
            c.put('./', copy);
          });
        }
        return res;
      }).catch(function () {
        return caches.match('index.html').then(function (hit) {
          return hit || caches.match('./');
        });
      })
    );
    return;
  }

  // Baaki sab cache-first -- unke URL mein version hai, to badalne par
  // naya URL khud ba khud naya fetch karta hai.
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
