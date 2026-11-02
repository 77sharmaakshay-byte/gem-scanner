/* Scan by Akshay -- data, routing, aur on-demand scan.
   Feed ek static JSON hai jo scanner har run par commit karta hai; filter
   sab kuch phone ke andar hota hai, to koi server nahi chahiye. */
(function () {
  'use strict';

  var REPO = '77sharmaakshay-byte/gem-scanner';
  var WORKFLOW = 'scanner.yml';
  var FEED_URL = 'feed.json';
  var ACTIONS_URL = 'https://github.com/' + REPO + '/actions/workflows/' + WORKFLOW;

  var LS_TOKEN = 'sba.token';
  var LS_FEED = 'sba.feed';
  var LS_FILTER = 'sba.filter';
  var LS_SQ = 'sba.sq';

  var st = {
    feed: null,
    allAlerts: [],
    alerts: [],
    universe: [],
    feedTfs: [],
    filter: { setups: [], tfs: [], side: '', maxBars: 999 },
    sq: { tf: '1D', band: 'rsi', view: 'tight', thresh: 1.10, bars: 4 },
    runNote: '',
    loadError: ''
  };

  var app = document.getElementById('app');
  var stampEl = document.getElementById('stamp');
  var refreshBtn = document.getElementById('refresh');

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

  function adopt(feed) {
    st.feed = feed;
    st.allAlerts = toObjects(feed.alerts);
    st.universe = toObjects(feed.universe);

    var seen = {};
    st.universe.forEach(function (r) { seen[r.tf] = true; });
    st.allAlerts.forEach(function (a) { seen[a.tf] = true; });
    st.feedTfs = Object.keys(seen).sort(function (a, b) {
      return V.tfRank(a) - V.tfRank(b);
    });
    if (st.feedTfs.length && st.feedTfs.indexOf(st.sq.tf) < 0) {
      st.sq.tf = st.feedTfs.indexOf('1D') >= 0 ? '1D' : st.feedTfs[0];
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
      return true;
    });
  }

  function setStamp() {
    if (st.loadError) {
      stampEl.textContent = st.loadError;
      return;
    }
    stampEl.textContent = st.feed && st.feed.scanned ? st.feed.scanned : 'feed khali';
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

  /* ---------------- on-demand scan ---------------- */

  function scanNow(btn) {
    var tok = token();
    if (!tok) {
      st.runNote = 'Pehle neeche token daalo, ya GitHub par khud chalao.';
      render();
      return;
    }
    btn.disabled = true;
    st.runNote = 'Scan trigger kar raha hoon…';
    render();

    fetch('https://api.github.com/repos/' + REPO + '/actions/workflows/' + WORKFLOW + '/dispatches', {
      method: 'POST',
      headers: {
        'Authorization': 'Bearer ' + tok,
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ ref: 'main', inputs: { force: 'true' } })
    })
      .then(function (res) {
        if (res.status === 204) {
          st.runNote = 'Scan queue mein lag gaya. Poora scan ~20 min leta hai; ' +
            'ho jaane par upar wala refresh button dabao.';
        } else if (res.status === 401 || res.status === 403) {
          st.runNote = 'Token ne mana kar diya (' + res.status + '). ' +
            'Scope mein "Actions: read and write" hona chahiye.';
        } else if (res.status === 404) {
          st.runNote = 'Repo ya workflow nahi mila (404). Token ka access check karo.';
        } else {
          st.runNote = 'GitHub ne ' + res.status + ' bheja.';
        }
      })
      .catch(function (err) {
        st.runNote = 'Trigger fail: ' + err.message;
      })
      .then(function () {
        render();
      });
  }

  function checkRun() {
    var tok = token();
    if (!tok) return;
    st.runNote = 'Status dekh raha hoon…';
    render();
    fetch('https://api.github.com/repos/' + REPO + '/actions/workflows/' + WORKFLOW +
      '/runs?per_page=1', {
      headers: {
        'Authorization': 'Bearer ' + tok,
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28'
      }
    })
      .then(function (res) { return res.ok ? res.json() : Promise.reject(new Error('HTTP ' + res.status)); })
      .then(function (data) {
        var run = data.workflow_runs && data.workflow_runs[0];
        if (!run) { st.runNote = 'Koi run nahi mila.'; return; }
        var when = new Date(run.created_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' });
        st.runNote = 'Aakhri run: ' + run.status +
          (run.conclusion ? ' / ' + run.conclusion : '') + ' · ' + when;
      })
      .catch(function (err) { st.runNote = 'Status nahi mila: ' + err.message; })
      .then(render);
  }

  /* ---------------- settings view ---------------- */

  function viewSettings() {
    var tok = token();
    var feed = st.feed || {};
    var html = '<div class="label">ON-DEMAND SCAN</div>' +
      '<div class="btnrow">' +
      '<button class="btn wide" type="button" data-act="scan-now">Scan abhi chalao</button>' +
      '</div>' +
      '<div class="btnrow">' +
      '<button class="btn ghost wide" type="button" data-act="check-run">Run ka status</button>' +
      '</div>';

    if (st.runNote) {
      html += '<div class="note"><b>' + V.esc(st.runNote) + '</b></div>';
    }

    html += '<div class="note">Scan GitHub Actions par chalta hai, phone par nahi. ' +
      'Poora scan ~20 minute leta hai, phir feed apne aap update ho jaati hai.</div>';

    html += '<label class="field"><span>GITHUB TOKEN</span>' +
      '<input id="tok" type="password" autocomplete="off" spellcheck="false"' +
      ' placeholder="' + (tok ? 'saved hai -- badalna ho to naya daalo' : 'github_pat_…') + '"></label>' +
      '<div class="btnrow">' +
      '<button class="btn wide" type="button" data-act="save-token">Token save karo</button>' +
      (tok ? '<button class="btn ghost" type="button" data-act="clear-token">Hatao</button>' : '') +
      '</div>';

    html += '<div class="note">Token sirf <b>isi phone ke browser</b> mein rehta hai -- ' +
      'na feed mein jaata hai, na GitHub repo mein. Fine-grained token banao jisme ' +
      'sirf <b>is ek repo</b> ka <b>Actions: read and write</b> ho, aur kuch nahi. ' +
      '<span class="warn">Jiske haath ye phone lage wo scan chala sakta hai</span> -- ' +
      'isliye isse zyada permission mat do.</div>';

    html += '<div class="note">Token nahi dena? <a href="' + ACTIONS_URL +
      '" target="_blank" rel="noopener" style="color:#7AA2FF">GitHub Actions par khud "Run workflow"</a> ' +
      'dabane se bhi wahi scan chalta hai.</div>';

    html += '<div class="label">FEED</div>' +
      '<div class="note">Aakhri scan: <b>' + V.esc(feed.scanned || '--') + '</b><br>' +
      'Alerts: <b>' + (st.allAlerts.length) + '</b> · Universe rows: <b>' + st.universe.length + '</b><br>' +
      'Timeframes: <b>' + V.esc(st.feedTfs.join(', ') || '--') + '</b></div>' +
      '<div class="btnrow"><button class="btn ghost wide" type="button" data-act="reload">' +
      'Feed dobara load karo</button></div>';

    return html + '<div class="spacer"></div>';
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

    if (page === 'feed' && r.query.setup) {
      st.filter.setups = [r.query.setup];
      writeJSON(LS_FILTER, st.filter);
      applyFilter();
      history.replaceState(null, '', '#/feed');
    }

    if (!st.feed) {
      app.innerHTML = st.loadError
        ? '<p class="empty">Abhi tak koi scan nahi hua.<br>' +
          'Market hours mein har 15 minute par run hota hai, aur 3:35 PM ke ' +
          'EOD run ke baad saare timeframes bhar jaate hain.</p>'
        : '<p class="empty">Feed load ho rahi hai…</p>';
      return;
    }

    var html;
    if (page === 'channels') html = V.channels(st);
    else if (page === 'squeeze') html = V.squeeze(st);
    else if (page === 'filter') html = V.filter(st);
    else if (page === 'settings') html = viewSettings();
    else if (page === 'stock') html = V.stock(st, r.parts[1] || '', r.parts[2] || '');
    else html = V.feed(st);

    app.innerHTML = html;
    window.scrollTo(0, 0);

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
    if (valEl) {
      valEl.textContent = st.sq.view === 'open'
        ? '≤ ' + st.sq.bars
        : '≤ ' + st.sq.thresh.toFixed(2) + 'x';
    }
  }

  document.addEventListener('click', function (ev) {
    var el = ev.target.closest ? ev.target.closest('[data-act]') : null;
    if (!el) return;
    var act = el.getAttribute('data-act');
    var val = el.getAttribute('data-v');

    if (act === 'sq-tf') { st.sq.tf = val; writeJSON(LS_SQ, st.sq); render(); }
    else if (act === 'sq-band') { st.sq.band = val; writeJSON(LS_SQ, st.sq); render(); }
    else if (act === 'sq-view') { st.sq.view = val; writeJSON(LS_SQ, st.sq); render(); }
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
    } else if (act === 'f-bars') {
      st.filter.maxBars = parseInt(val, 10);
      writeJSON(LS_FILTER, st.filter); applyFilter(); render();
    } else if (act === 'f-reset') {
      st.filter = { setups: [], tfs: [], side: '', maxBars: 999 };
      writeJSON(LS_FILTER, st.filter); applyFilter(); render();
    } else if (act === 'scan-now') {
      scanNow(el);
    } else if (act === 'check-run') {
      checkRun();
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
    else st.sq.thresh = v;
    writeJSON(LS_SQ, st.sq);
    patchFunnel();
  });

  refreshBtn.addEventListener('click', function () { load(true); });
  window.addEventListener('hashchange', render);

  /* ---------------- boot ---------------- */

  st.filter = readJSON(LS_FILTER, st.filter);
  if (!st.filter || typeof st.filter !== 'object') {
    st.filter = { setups: [], tfs: [], side: '', maxBars: 999 };
  }
  ['setups', 'tfs'].forEach(function (k) {
    if (!Array.isArray(st.filter[k])) st.filter[k] = [];
  });
  if (typeof st.filter.maxBars !== 'number') st.filter.maxBars = 999;
  if (typeof st.filter.side !== 'string') st.filter.side = '';

  var savedSq = readJSON(LS_SQ, null);
  if (savedSq && typeof savedSq === 'object') {
    st.sq.tf = savedSq.tf || st.sq.tf;
    st.sq.band = savedSq.band || st.sq.band;
    st.sq.view = savedSq.view === 'open' ? 'open' : 'tight';
    if (typeof savedSq.thresh === 'number') st.sq.thresh = savedSq.thresh;
    if (typeof savedSq.bars === 'number') st.sq.bars = savedSq.bars;
  }

  var cached = readJSON(LS_FEED, null);
  if (cached) { adopt(cached); setStamp(); render(); }
  load(false);

  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('sw.js').catch(function (err) {
        console.warn('SW register fail:', err);
      });
    });
  }
})();
