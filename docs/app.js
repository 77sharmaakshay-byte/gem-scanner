/* Scan by Akshay -- data, routing, aur on-demand scan.
   Feed ek static JSON hai jo scanner har run par commit karta hai; filter
   sab kuch phone ke andar hota hai, to koi server nahi chahiye. */
(function (global) {
  'use strict';

  var FEED_URL = 'feed.json';

  var LS_TOKEN = 'sba.token';
  var LS_FEED = 'sba.feed';
  var LS_FILTER = 'sba.filter';
  var LS_SQ = 'sba.sq';
  var LS_TV = 'sba.tv';

  var st = {
    feed: null,
    allAlerts: [],
    alerts: [],
    universe: [],
    feedTfs: [],
    univTfs: [],
    filter: { setups: [], tfs: [], side: '', maxBars: 999, maxWidth: 0 },
    sq: { tf: '1D', band: 'rsi', scale: 'rel', view: 'tight', top: 25, bars: 4 },
    runNote: '',
    loadError: ''
  };

  var app = document.getElementById('app');
  var stampEl = document.getElementById('stamp');
  var refreshBtn = document.getElementById('refresh');
  var backBtn = document.getElementById('back');
  var ptrEl = document.getElementById('ptr');
  var lastKey = '';

  /* ---------------- storage ---------------- */

  function readJSON(key, fallback) {
    try {
      var raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch (e) {
      return fallback;
    }
  }

  function writeJSON(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* private mode */ }
  }

  function token() {
    try { return localStorage.getItem(LS_TOKEN) || ''; } catch (e) { return ''; }
  }

  /* ---------------- feed ---------------- */

  function toObjects(block) {
    if (!block || !block.cols || !block.rows) return [];
    var cols = block.cols;
    return block.rows.map(function (row) {
      var obj = {};
      for (var i = 0; i < cols.length; i++) obj[cols[i]] = row[i];
      return obj;
    });
  }

  // Har timeframe ke itne sabse patli band wale apne channel mein aate hain.
  var ABS_TOP = 10;

  // Absolute channels app khud banata hai -- scanner inka alert nahi
  // bhejta. Universe mein har stock x TF ka row hota hai, usi se har TF ke
  // sabse patli band wale nikal kar alert jaisa row ban jaata hai, taaki ye
  // Feed, Channels aur Filter -- teeno mein apne aap aa jayein.
  function absoluteRows(universe) {
    var out = [];
    [['rsiw', 'RSI_Band_Absolute'], ['prw', 'Price_Band_Absolute']].forEach(function (pair) {
      var field = pair[0], setup = pair[1];
      var byTf = {};
      universe.forEach(function (r) {
        if (r[field] == null) return;
        (byTf[r.tf] = byTf[r.tf] || []).push(r);
      });
      Object.keys(byTf).forEach(function (tf) {
        byTf[tf].slice().sort(function (a, b) { return a[field] - b[field]; })
          .slice(0, ABS_TOP).forEach(function (r) {
            out.push({
              setup: setup, tf: r.tf, sym: r.sym, side: '',
              close: r.close, sq: r.sq, rsibb: r.rsibb,
              sqz_ago: field === 'prw' ? r.psqz_ago : r.sqz_ago,
              entry: null, ts: r.ts
            });
          });
      });
    });
    return out;
  }

  function adopt(feed) {
    st.feed = feed;
    st.universe = toObjects(feed.universe);
    st.allAlerts = toObjects(feed.alerts).concat(absoluteRows(st.universe));

    var seen = {};
    st.universe.forEach(function (r) { seen[r.tf] = true; });
    st.allAlerts.forEach(function (a) { seen[a.tf] = true; });
    st.feedTfs = Object.keys(seen).sort(function (a, b) {
      return V.tfRank(a) - V.tfRank(b);
    });
    // Squeeze funnel sirf universe rows par chalta hai. Alert mein 1D ho
    // sakta hai jabki uska universe abhi scan nahi hua (higher TF 3:35 par
    // chalta hai) -- isliye uske chips alag list se aate hain.
    var seenU = {};
    st.universe.forEach(function (r) { seenU[r.tf] = true; });
    st.univTfs = Object.keys(seenU).sort(function (a, b) {
      return V.tfRank(a) - V.tfRank(b);
    });
    // Alert rows mein band ki chaudai nahi hoti -- feed halki rakhne ke
    // liye. Universe se jod kar har jagah dikha dete hain.
    st.uidx = {};
    st.universe.forEach(function (r) { st.uidx[r.sym + '|' + r.tf] = r; });
    if (st.univTfs.length && st.univTfs.indexOf(st.sq.tf) < 0) {
      st.sq.tf = st.univTfs.indexOf('1D') >= 0 ? '1D' : st.univTfs[st.univTfs.length - 1];
    }
    applyFilter();
  }

  function applyFilter() {
    var f = st.filter;
    st.alerts = st.allAlerts.filter(function (a) {
      if (f.setups.length && f.setups.indexOf(a.setup) < 0) return false;
      if (f.tfs.length && f.tfs.indexOf(a.tf) < 0) return false;
      if (f.side && a.side && a.side !== f.side) return false;
      if (f.side && !a.side) return false;
      if (f.maxBars !== 999) {
        var bars = a.sqz_ago;
        if (bars === null || bars === undefined || bars > f.maxBars) return false;
      }
      if (f.maxWidth) {
        var u = st.uidx[a.sym + '|' + a.tf];
        if (!u || u.rsiw == null || u.rsiw > f.maxWidth) return false;
      }
      return true;
    });
  }

  function setStamp() {
    if (st.loadError) {
      stampEl.textContent = st.loadError;
      return;
    }
    if (!st.feed || !st.feed.scanned) { stampEl.textContent = 'feed khali'; return; }
    stampEl.innerHTML = V.esc(st.feed.scanned) + ago(st.feed.updated_utc);
  }

  // "12:31 PM · 8m" -- data kitna purana hai ye ek nazar mein dikhe.
  function ago(utc) {
    if (!utc) return '';
    var mins = Math.round((Date.now() - new Date(utc).getTime()) / 60000);
    if (isNaN(mins) || mins < 0) return '';
    var txt = mins < 60 ? mins + 'm' : Math.round(mins / 60) + 'h';
    var old = mins > 40 && Shell.marketHours();
    return ' <span class="age' + (old ? ' old' : '') + '">· ' + txt + '</span>';
  }

  function load(force) {
    refreshBtn.setAttribute('data-busy', '1');
    var url = FEED_URL + '?t=' + Date.now();
    return fetch(url, { cache: force ? 'reload' : 'default' })
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then(function (feed) {
        st.loadError = '';
        adopt(feed);
        writeJSON(LS_FEED, feed);
      })
      .catch(function (err) {
        var cached = readJSON(LS_FEED, null);
        if (cached) {
          adopt(cached);
          st.loadError = 'offline -- purani feed';
        } else {
          st.loadError = 'feed nahi mili';
        }
        console.warn('Feed load fail:', err);
      })
      .then(function () {
        refreshBtn.removeAttribute('data-busy');
        setStamp();
        render();
      });
  }

  /* ---------------- TradingView ---------------- */

  function tvMode() {
    try { return localStorage.getItem(LS_TV) || 'app'; } catch (e) { return 'app'; }
  }

  function tvShortcutName() {
    try { return localStorage.getItem('sba.tvshortcut') || 'TradingView Chart'; }
    catch (e) { return 'TradingView Chart'; }
  }

  // iOS par app kholne ki koshish. Scheme registered na ho to Safari ek
  // error dialog dikhata hai aur page wahin rehta hai -- isliye 1.2 sec
  // baad website par chale jaate hain. Agar app khul gaya to tab tak page
  // chhup chuka hoga, aur hum kuch nahi karte (warna wapas aate hi
  // website khul jaati).
  function openTV(sym, webUrl) {
    var mode = tvMode();
    if (mode === 'web') { location.href = webUrl; return; }

    if (mode === 'shortcut') {
      location.href = 'shortcuts://run-shortcut?name=' +
        encodeURIComponent(tvShortcutName()) +
        '&input=text&text=' + encodeURIComponent('NSE:' + sym);
      return;
    }

    var hidden = false;
    var mark = function () { hidden = true; };
    document.addEventListener('visibilitychange', mark);
    window.addEventListener('pagehide', mark);
    setTimeout(function () {
      document.removeEventListener('visibilitychange', mark);
      window.removeEventListener('pagehide', mark);
      if (!hidden && !document.hidden) location.href = webUrl;
    }, 1200);
    location.href = 'tradingview://chart?symbol=NSE%3A' + encodeURIComponent(sym);
  }

  /* ---------------- routing ---------------- */

  function parseRoute() {
    var hash = location.hash.replace(/^#\/?/, '') || 'feed';
    var qi = hash.indexOf('?');
    var query = {};
    if (qi >= 0) {
      hash.slice(qi + 1).split('&').forEach(function (bit) {
        var kv = bit.split('=');
        query[decodeURIComponent(kv[0])] = decodeURIComponent(kv[1] || '');
      });
      hash = hash.slice(0, qi);
    }
    return { parts: hash.split('/').map(decodeURIComponent), query: query };
  }

  function render() {
    var r = parseRoute();
    var page = r.parts[0] || 'feed';

    // Channel par click = "sirf ye channel dikhao". Pehle ye sirf setups
    // badalta tha aur TF/side/bars wale filter laga rehte the -- to purana
    // atka hua TF ya side har channel ko khali kar deta tha. Ab poora
    // filter saaf hota hai. '*' ka matlab "saare signals".
    if (page === 'feed' && r.query.setup) {
      st.filter = {
        setups: r.query.setup === '*' ? [] : [r.query.setup],
        tfs: [], side: '', maxBars: 999, maxWidth: 0
      };
      writeJSON(LS_FILTER, st.filter);
      applyFilter();
      history.replaceState(null, '', '#/feed');
    }

    if (!st.feed) {
      app.innerHTML = st.loadError
        ? '<p class="empty">Abhi tak koi scan nahi hua.<br>' +
          'Market hours mein har 15 minute par run hota hai, aur 3:35 PM ke ' +
          'EOD run ke baad saare timeframes bhar jaate hain.</p>'
        : '<div class="skel"><div class="s1"></div><div class="s2"></div><div class="s3"></div></div>';
      return;
    }

    var html;
    if (page === 'channels') html = V.channels(st);
    else if (page === 'squeeze') html = V.squeeze(st);
    else if (page === 'filter') html = V.filter(st);
    else if (page === 'settings') html = Scan.view();
    else if (page === 'stock') html = V.stock(st, r.parts[1] || '', r.parts[2] || '');
    else html = V.feed(st);

    if (page === 'feed') html = Shell.hintHTML() + html;

    // Wahi screen dobara bani (feed refresh hui, slider badla) -- to scroll
    // chhedo mat aur animation bhi mat chalao, warna padhte-padhte jhatka
    // lagta hai. Screen badli tabhi upar/yaad wali jagah par jao.
    var key = r.parts.join('/');
    var same = key === lastKey;
    var keepY = global.scrollY;

    app.innerHTML = html;
    document.body.setAttribute('data-detail', page === 'stock' ? '1' : '0');

    if (same) {
      global.scrollTo(0, keepY);
    } else {
      Shell.restore(key, false);
      app.classList.remove('in');
      void app.offsetWidth;
      app.classList.add('in');
    }
    lastKey = key;

    // Chuna hua TF chip strip se bahar ho sakta hai -- use dikhao.
    var picked = app.querySelector('.chips.scroll .chip[aria-pressed="true"]');
    if (picked && picked.scrollIntoView) {
      picked.scrollIntoView({ block: 'nearest', inline: 'center' });
    }

    var tab = page === 'stock' ? 'feed' : page;
    Array.prototype.forEach.call(document.querySelectorAll('.tabbar a'), function (a) {
      if (a.getAttribute('data-tab') === tab) a.setAttribute('aria-current', 'page');
      else a.removeAttribute('aria-current');
    });
  }

  /* ---------------- actions ---------------- */

  function toggle(list, value) {
    var i = list.indexOf(value);
    if (i >= 0) list.splice(i, 1);
    else list.push(value);
  }

  function patchFunnel() {
    var res = V.funnelRows(st);
    var countEl = document.getElementById('sq-count');
    var listEl = document.getElementById('sq-list');
    var valEl = document.getElementById('sq-val');
    if (countEl) countEl.textContent = res.rows.length;
    if (listEl) listEl.innerHTML = V.funnelList(st, res);
    var noteEl = document.getElementById('sq-note');
    if (noteEl && st.sq.view !== 'open') {
      noteEl.textContent = 'stock · ' + res.pool + ' mein se (' + st.sq.tf + ')' +
        (res.cut != null ? ' · cutoff ' + V.cutText(st.sq.band, res.cut, res.scale) : '');
    }
    if (valEl) {
      valEl.textContent = st.sq.view === 'open'
        ? '≤ ' + st.sq.bars
        : 'top ' + res.rows.length;
    }
  }

  document.addEventListener('click', function (ev) {
    var el = ev.target.closest ? ev.target.closest('[data-act]') : null;
    if (!el) return;
    var act = el.getAttribute('data-act');
    var val = el.getAttribute('data-v');
    Shell.haptic();

    if (act === 'tv') {
      ev.preventDefault();
      openTV(val, el.getAttribute('href'));
      return;
    }
    if (act === 'tv-mode') {
      try { localStorage.setItem(LS_TV, val); } catch (e) { /* ignore */ }
      st.runNote = 'TradingView ab ' + (val === 'app' ? 'app mein kholne ki koshish karega'
        : val === 'shortcut' ? 'Apple Shortcut se khulega' : 'website mein khulega') + '.';
      render();
      return;
    }

    if (act === 'hint-off') { Shell.hintOff(); render(); return; }

    if (act === 'sq-tf') { st.sq.tf = val; writeJSON(LS_SQ, st.sq); render(); }
    else if (act === 'sq-band') { st.sq.band = val; writeJSON(LS_SQ, st.sq); render(); }
    else if (act === 'sq-view') { st.sq.view = val; writeJSON(LS_SQ, st.sq); render(); }
    else if (act === 'sq-scale') { st.sq.scale = val; writeJSON(LS_SQ, st.sq); render(); }
    else if (act === 'f-setup') {
      if (val === '*') st.filter.setups = [];
      else toggle(st.filter.setups, val);
      writeJSON(LS_FILTER, st.filter); applyFilter(); render();
    } else if (act === 'f-tf') {
      if (val === '*') st.filter.tfs = [];
      else toggle(st.filter.tfs, val);
      writeJSON(LS_FILTER, st.filter); applyFilter(); render();
    } else if (act === 'f-side') {
      st.filter.side = val === '*' ? '' : val;
      writeJSON(LS_FILTER, st.filter); applyFilter(); render();
    } else if (act === 'f-width') {
      st.filter.maxWidth = parseFloat(val) || 0;
      writeJSON(LS_FILTER, st.filter); applyFilter(); render();
    } else if (act === 'f-bars') {
      st.filter.maxBars = parseInt(val, 10);
      writeJSON(LS_FILTER, st.filter); applyFilter(); render();
    } else if (act === 'f-reset') {
      st.filter = { setups: [], tfs: [], side: '', maxBars: 999, maxWidth: 0 };
      writeJSON(LS_FILTER, st.filter); applyFilter(); render();
    } else if (act === 'scan-now') {
      Scan.now(el);
    } else if (act === 'check-run') {
      Scan.check();
    } else if (act === 'save-token') {
      var input = document.getElementById('tok');
      var v = input && input.value.trim();
      if (v) {
        try { localStorage.setItem(LS_TOKEN, v); st.runNote = 'Token save ho gaya.'; }
        catch (e) { st.runNote = 'Token save nahi hua (private mode?).'; }
      } else {
        st.runNote = 'Token khali hai.';
      }
      render();
    } else if (act === 'clear-token') {
      try { localStorage.removeItem(LS_TOKEN); } catch (e) { /* ignore */ }
      st.runNote = 'Token hata diya.';
      render();
    } else if (act === 'reload') {
      load(true);
    }
  });

  document.addEventListener('input', function (ev) {
    if (!ev.target || ev.target.getAttribute('data-act') !== 'sq-range') return;
    var v = parseFloat(ev.target.value);
    if (st.sq.view === 'open') st.sq.bars = Math.round(v);
    else st.sq.top = Math.round(v);
    writeJSON(LS_SQ, st.sq);
    patchFunnel();
  });

  refreshBtn.addEventListener('click', function () { Shell.haptic(); load(true); });
  backBtn.addEventListener('click', function () {
    Shell.haptic();
    if (history.length > 1) history.back();
    else location.hash = '#/feed';
  });
  window.addEventListener('hashchange', function () {
    if (lastKey) Shell.remember(lastKey);
    render();
  });

  // Link par ungli rakhte hi scroll yaad -- taaki wapas aakar wahin milein.
  document.addEventListener('click', function (ev) {
    var a = ev.target.closest ? ev.target.closest('a[href^="#/"]') : null;
    if (a && lastKey) Shell.remember(lastKey);
  }, true);

  /* ---------------- boot ---------------- */

  st.filter = readJSON(LS_FILTER, st.filter);
  if (!st.filter || typeof st.filter !== 'object') {
    st.filter = { setups: [], tfs: [], side: '', maxBars: 999 };
  }
  ['setups', 'tfs'].forEach(function (k) {
    if (!Array.isArray(st.filter[k])) st.filter[k] = [];
  });
  if (typeof st.filter.maxBars !== 'number') st.filter.maxBars = 999;
  if (typeof st.filter.maxWidth !== 'number') st.filter.maxWidth = 0;
  if (typeof st.filter.side !== 'string') st.filter.side = '';

  var savedSq = readJSON(LS_SQ, null);
  if (savedSq && typeof savedSq === 'object') {
    st.sq.tf = savedSq.tf || st.sq.tf;
    // 'rsinum' alag band hua karta tha; ab wo RSI band + absolute scale hai.
    st.sq.band = savedSq.band === 'rsinum' ? 'rsi' : (savedSq.band || st.sq.band);
    st.sq.scale = savedSq.band === 'rsinum' ? 'abs'
      : (savedSq.scale === 'abs' ? 'abs' : 'rel');
    st.sq.view = savedSq.view === 'open' ? 'open' : 'tight';
    if (typeof savedSq.top === 'number') st.sq.top = savedSq.top;
    if (typeof savedSq.bars === 'number') st.sq.bars = savedSq.bars;
  }

  // Pehli render se PEHLE -- cached feed hone par boot par hi render
  // chalta hai, aur agar us waqt route #/settings hua to Scan ke paas
  // token/render nahi hote aur screen crash kar jaati hai.
  Scan.init({ st: st, render: render, token: token, tvMode: tvMode });

  var cached = readJSON(LS_FEED, null);
  if (cached) { adopt(cached); setStamp(); render(); }
  load(false);

  Shell.init(ptrEl, function () { return load(true); });
  setInterval(setStamp, 60000);

  if ('serviceWorker' in navigator) {
    // Naya worker control le to ek baar page reload -- warna purani screen
    // chalti rehti hai aur user ko lagta hai update aaya hi nahi.
    var reloaded = false;
    navigator.serviceWorker.addEventListener('controllerchange', function () {
      if (reloaded) return;
      reloaded = true;
      location.reload();
    });
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('sw.js').then(function (reg) {
        reg.update();
        // App dobara saamne aate hi naya version check karo.
        document.addEventListener('visibilitychange', function () {
          if (document.visibilityState === 'visible') reg.update();
        });
      }).catch(function (err) {
        console.warn('SW register fail:', err);
      });
    });
  }
})(window);
