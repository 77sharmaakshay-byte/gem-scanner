/* Scan by Akshay -- on-demand scan aur Setup screen.
   app.js se alag isliye ki koi bhi file 500 line se badi na ho.
   Token sirf isi phone ke localStorage mein rehta hai. */
(function (global) {
  'use strict';

  var REPO = '77sharmaakshay-byte/gem-scanner';
  var WORKFLOW = 'scanner.yml';
  var ACTIONS_URL = 'https://github.com/' + REPO + '/actions/workflows/' + WORKFLOW;

  var st, render, token;

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
    if (!tok) {
      // Chup-chaap wapas aana galat tha -- purana note pada rehta tha aur
      // lagta tha ki button chal gaya.
      st.runNote = 'Status dekhne ke liye bhi token chahiye.';
      render();
      return;
    }
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

  global.Scan = {
    init: function (deps) {
      st = deps.st; render = deps.render; token = deps.token;
    },
    now: scanNow,
    check: checkRun,
    view: viewSettings
  };
})(window);
