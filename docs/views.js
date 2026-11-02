/* Scan by Akshay -- screens. Sirf HTML banata hai, data app.js se aata hai. */
(function (global) {
  'use strict';

  var SETUPS = [
    { id: 'RSI_BB_Cross_Setup', name: 'RSI-BB cross', kind: 'cross' },
    { id: 'Gem_Setup_Intraday', name: 'Gem intraday', kind: 'gem' },
    { id: 'Gem_Setup_HigherTF', name: 'Gem higher TF', kind: 'gem' },
    { id: 'Price_BB_Squeeze', name: 'Price-BB squeeze', kind: 'sqz' },
    { id: 'RSI_BB_Squeeze', name: 'RSI-BB squeeze', kind: 'sqz' },
    { id: 'Both_Squeeze', name: 'Dono BB squeeze', kind: 'sqz' },
    { id: 'New_HA_Squeeze_Setup', name: 'Naya HA setup', kind: 'ha' },
    { id: 'Mid_BB_Reversal_Setup', name: 'Mid-BB reversal', kind: 'mid' }
  ];

  var TF_ORDER = ['5m', '15m', '30m', '45m', '1H', '75m', '90m', '2H', '150m',
    '3H', '4H', '1D', '2D', '3D', '1W', '1M', '6M'];
  var INTRADAY = ['5m', '15m', '30m', '45m', '1H', '75m', '90m', '2H', '150m', '3H', '4H'];
  var HIGHER = ['1D', '2D', '3D', '1W', '1M', '6M'];

  var BANDS = [
    { id: 'rsi', name: 'RSI BB', ratio: 'rratio', width: 'rsiw', unit: '' },
    { id: 'price', name: 'Price BB', ratio: 'pratio', width: 'prw', unit: '%' },
    { id: 'both', name: 'Dono', ratio: 'both', width: 'rsiw', unit: '' },
    { id: 'mid', name: 'Mid-BB', ratio: 'rratio', width: 'rsiw', unit: '' }
  ];

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function num(v, d) {
    if (v === null || v === undefined || v === '' || isNaN(v)) return '--';
    return Number(v).toFixed(d === undefined ? 2 : d);
  }

  function setupName(id) {
    for (var i = 0; i < SETUPS.length; i++) if (SETUPS[i].id === id) return SETUPS[i].name;
    return id;
  }

  function tfRank(tf) {
    var i = TF_ORDER.indexOf(tf);
    return i < 0 ? 99 : i;
  }

  function sqzText(bars) {
    if (bars === null || bars === undefined || bars >= 999) return '';
    if (bars <= 0) return 'SQZ abhi';
    return bars === 1 ? 'SQZ 1 candle pehle' : 'SQZ ' + bars + ' candles pehle';
  }

  function sideTag(side) {
    if (side === 'BUY') return '<span class="tag buy">BUY</span>';
    if (side === 'SELL') return '<span class="tag sell">SELL</span>';
    return '';
  }

  /* ---------------- Feed ---------------- */

  function heroCard(a) {
    var sell = a.side === 'SELL';
    var sq = sqzText(a.sqz_ago);
    return '<a class="hero' + (sell ? ' sell' : '') + '" href="#/stock/' + esc(a.sym) + '/' + esc(a.tf) + '">' +
      '<div class="hero-top">' +
        '<span class="hero-kicker">AAJ KA TOP SETUP</span>' +
        '<span style="flex:1 1 auto"></span>' +
        '<span class="stamp">' + esc(setupName(a.setup)) + '</span>' +
      '</div>' +
      '<div class="hero-sym">' + esc(a.sym) + '</div>' +
      '<div class="hero-mid">' +
        '<div class="badges">' +
          sideTag(a.side) +
          '<span class="tag">' + esc(a.tf) + '</span>' +
          (sq ? '<span class="tag sqz">' + esc(sq) + '</span>' : '') +
        '</div>' +
        '<div class="hero-price num">' + num(a.close) + '</div>' +
      '</div>' +
      '<div class="stats">' +
        '<div><div class="k">SQ%</div><div class="v num">' + num(a.sq, 1) + '</div></div>' +
        '<div><div class="k">RSI-BB%</div><div class="v num">' + num(a.rsibb, 1) + '</div></div>' +
        (a.entry ? '<div><div class="k">ENTRY</div><div class="v num">' + num(a.entry) + '</div></div>' : '') +
      '</div>' +
    '</a>';
  }

  function smallCard(a) {
    var sq = sqzText(a.sqz_ago);
    return '<a class="card" href="#/stock/' + esc(a.sym) + '/' + esc(a.tf) + '">' +
      '<div class="card-top"><span class="tag">' + esc(a.tf) + '</span>' + sideTag(a.side) + '</div>' +
      '<div class="card-sym">' + esc(a.sym) + '</div>' +
      '<div class="card-price num">' + num(a.close) + '</div>' +
      '<div class="card-note">' + esc(sq || ('SQ% ' + num(a.sq, 1))) + '</div>' +
    '</a>';
  }

  function viewFeed(st) {
    var alerts = st.alerts;
    if (!alerts.length) {
      return '<p class="empty">Is filter par koi alert nahi.<br>Filter kholo ya scan ka intezaar karo.</p>';
    }

    var sorted = alerts.slice().sort(function (a, b) {
      var sa = a.sqz_ago >= 999 ? 500 : a.sqz_ago;
      var sb = b.sqz_ago >= 999 ? 500 : b.sqz_ago;
      if (sa !== sb) return sa - sb;
      return tfRank(b.tf) - tfRank(a.tf);
    });

    var html = heroCard(sorted[0]);
    var rest = sorted.slice(1);

    SETUPS.forEach(function (s) {
      var mine = rest.filter(function (a) { return a.setup === s.id; });
      if (!mine.length) return;
      html += '<div class="rowhead" style="padding-top:22px">' +
        '<h2>' + esc(s.name) + '</h2><span class="n">' + mine.length + '</span></div>' +
        '<div class="rail">' + mine.map(smallCard).join('') + '</div>';
    });

    return html + '<div class="spacer"></div>';
  }

  /* ---------------- Channels ---------------- */

  function channelRow(s, count, tfs, cls) {
    var sub = tfs.length ? tfs.join(' · ') : 'Aaj koi alert nahi';
    return '<a class="row" href="#/feed?setup=' + esc(s.id) + '">' +
      '<span class="badge-sq ' + cls + '">' + esc(s.kind.toUpperCase().slice(0, 5)) + '</span>' +
      '<span class="grow"><span class="name">' + esc(s.name) + '</span>' +
      '<span class="meta">' + esc(sub) + '</span></span>' +
      (count ? '<span class="pill">' + count + '</span>' : '<span class="pill quiet">0</span>') +
    '</a>';
  }

  function viewChannels(st) {
    var all = st.allAlerts;
    var html = '<a class="row" href="#/feed">' +
      '<span class="badge-sq">ALL</span>' +
      '<span class="grow"><span class="name">Saare signals</span>' +
      '<span class="meta">Har setup, har timeframe -- ek jagah</span></span>' +
      '<span class="pill" style="background:#F2F4F7">' + all.length + '</span></a>';

    var groups = [
      { title: 'RSI-BB CROSS', ids: ['RSI_BB_Cross_Setup'], cls: 'eod' },
      { title: 'GEM & SQUEEZE', ids: ['Gem_Setup_Intraday', 'Gem_Setup_HigherTF',
        'Price_BB_Squeeze', 'RSI_BB_Squeeze', 'Both_Squeeze', 'New_HA_Squeeze_Setup'], cls: '' },
      { title: 'MID-BB REVERSAL', ids: ['Mid_BB_Reversal_Setup'], cls: 'mid' }
    ];

    groups.forEach(function (g) {
      html += '<div class="label">' + esc(g.title) + '</div>';
      g.ids.forEach(function (id) {
        var s = SETUPS.filter(function (x) { return x.id === id; })[0];
        var mine = all.filter(function (a) { return a.setup === id; });
        var tfs = [];
        mine.forEach(function (a) { if (tfs.indexOf(a.tf) < 0) tfs.push(a.tf); });
        tfs.sort(function (a, b) { return tfRank(a) - tfRank(b); });
        html += channelRow(s, mine.length, tfs, g.cls);
      });
    });

    return html + '<div class="spacer"></div>';
  }

  /* ---------------- Squeeze funnel ---------------- */

  function ratioOf(row, band) {
    if (band === 'both') {
      var a = row.rratio, b = row.pratio;
      if (a == null || b == null) return null;
      return Math.max(a, b);
    }
    var key = band === 'price' ? 'pratio' : 'rratio';
    return row[key];
  }

  // "Squeeze kitni candle pehle tha" -- har band ka apna. Price BB tab par
  // RSI ka number dikhana galat hoga, dono alag cheezein hain.
  function agoOf(row, band) {
    var r = row.sqz_ago == null ? 999 : row.sqz_ago;
    var p = row.psqz_ago == null ? 999 : row.psqz_ago;
    if (band === 'price') return p;
    if (band === 'both') return Math.max(r, p);
    return r;
  }

  function funnelRows(st) {
    var s = st.sq;
    var pool = st.universe.filter(function (r) { return r.tf === s.tf; });

    if (s.band === 'mid') {
      pool = pool.filter(function (r) { return r.mbb_b || r.mbb_s; });
    }

    var rows;
    if (s.view === 'open') {
      rows = pool.filter(function (r) {
        var ago = agoOf(r, s.band);
        return ago >= 1 && ago <= s.bars;
      }).sort(function (a, b) { return agoOf(a, s.band) - agoOf(b, s.band); });
    } else {
      rows = pool.filter(function (r) {
        var ratio = ratioOf(r, s.band);
        return ratio != null && ratio <= s.thresh;
      }).sort(function (a, b) { return ratioOf(a, s.band) - ratioOf(b, s.band); });
    }
    return { rows: rows, pool: pool.length };
  }

  function funnelList(st, res) {
    var s = st.sq;
    var band = BANDS.filter(function (b) { return b.id === s.band; })[0];
    if (!res.rows.length) {
      return '<p class="empty">' + (res.pool
        ? 'Itna tight koi nahi. Slider thoda dheela karo.'
        : s.tf + ' ka data abhi feed mein nahi hai.') + '</p>';
    }
    return res.rows.map(function (r) {
      var ratio = ratioOf(r, s.band);
      var width = r[band.width];
      var pct = Math.max(4, Math.min(100, Math.round(((ratio || 1) / 2) * 100)));
      var ago = agoOf(r, s.band);
      var meta;
      if (s.view === 'open') {
        meta = sqzText(ago) + ' · ab ' + num(ratio, 2) + 'x';
      } else if (s.band === 'mid') {
        meta = (r.mbb_b ? 'mid-BB ke upar close' : 'mid-BB ke neeche close') +
          ' · ' + num(ratio, 2) + 'x low se';
      } else {
        meta = num(ratio, 2) + 'x apne 20-bar low se' + (ago === 0 ? ' · SQZ abhi' : '');
      }
      return '<a class="row" href="#/stock/' + esc(r.sym) + '/' + esc(r.tf) + '">' +
        '<span class="grow">' +
          '<span class="name">' + esc(r.sym) + '</span>' +
          '<span class="meta">' + esc(meta) + '</span>' +
          '<span class="bar"><i class="' + (s.view === 'open' ? 'open' : '') + '" style="width:' + pct + '%"></i></span>' +
        '</span>' +
        '<span class="right"><span class="big num">' + num(width, 2) + band.unit + '</span>' +
        '<span class="small">width</span></span>' +
      '</a>';
    }).join('');
  }

  function viewSqueeze(st) {
    var s = st.sq;
    var res = funnelRows(st);
    var tfs = st.feedTfs;

    var html = '<div class="chips scroll">' + tfs.map(function (tf) {
      return '<button class="chip" type="button" data-act="sq-tf" data-v="' + esc(tf) + '"' +
        ' aria-pressed="' + (tf === s.tf) + '">' + esc(tf) + '</button>';
    }).join('') + '</div>';

    html += '<div class="seg">' + BANDS.map(function (b) {
      return '<button type="button" data-act="sq-band" data-v="' + b.id + '"' +
        ' aria-pressed="' + (b.id === s.band) + '">' + esc(b.name) + '</button>';
    }).join('') + '</div>';

    var isOpen = s.view === 'open';
    html += '<div class="panel">' +
      '<div class="panel-head">' +
        '<label class="k" for="sq-range" id="sq-label">' +
          (isOpen ? 'SQUEEZE KITNE CANDLE PEHLE' : 'WIDTH APNE 20-BAR LOW SE') +
        '</label>' +
        '<span class="v num" id="sq-val">' +
          (isOpen ? '≤ ' + s.bars : '≤ ' + s.thresh.toFixed(2) + 'x') +
        '</span>' +
      '</div>' +
      '<input id="sq-range" type="range" data-act="sq-range"' +
        ' min="' + (isOpen ? 1 : 1) + '"' +
        ' max="' + (isOpen ? 20 : 2) + '"' +
        ' step="' + (isOpen ? 1 : 0.01) + '"' +
        ' value="' + (isOpen ? s.bars : s.thresh) + '">' +
      '<div class="ends"><span>' + (isOpen ? 'abhi khula' : 'sabse tight') + '</span>' +
        '<span>' + (isOpen ? '20 candle' : 'sab kuch') + '</span></div>' +
      '<div class="count"><b class="num" id="sq-count">' + res.rows.length + '</b>' +
        '<span>stock · ' + res.pool + ' mein se (' + esc(s.tf) + ')</span></div>' +
    '</div>';

    html += '<div class="btnrow">' +
      '<button class="chip go" type="button" data-act="sq-view" data-v="tight"' +
        ' aria-pressed="' + (!isOpen) + '" style="flex:1 1 0;justify-content:center;min-height:38px">Tight ho raha</button>' +
      '<button class="chip go" type="button" data-act="sq-view" data-v="open"' +
        ' aria-pressed="' + isOpen + '" style="flex:1 1 0;justify-content:center;min-height:38px">Squeeze khul gaya</button>' +
    '</div>';

    html += '<div class="label">RESULT · WIDTH KE HISAAB SE</div>' +
      '<div id="sq-list">' + funnelList(st, res) + '</div><div class="spacer"></div>';
    return html;
  }

  /* ---------------- Filter ---------------- */

  function chipRow(act, values, chosen) {
    return values.map(function (v) {
      var on = chosen.indexOf(v) >= 0;
      return '<button class="chip" type="button" data-act="' + act + '" data-v="' + esc(v) + '"' +
        ' aria-pressed="' + on + '">' + esc(v) + '</button>';
    }).join('');
  }

  function viewFilter(st) {
    var f = st.filter;
    var html = '<div class="label">SETUP</div><div class="chips">' +
      '<button class="chip go" type="button" data-act="f-setup" data-v="*"' +
        ' aria-pressed="' + (!f.setups.length) + '">Saare</button>' +
      SETUPS.map(function (s) {
        var on = f.setups.indexOf(s.id) >= 0;
        return '<button class="chip" type="button" data-act="f-setup" data-v="' + esc(s.id) + '"' +
          ' aria-pressed="' + on + '">' + esc(s.name) + '</button>';
      }).join('') + '</div>';

    html += '<div class="label">TIMEFRAME</div>' +
      '<div class="chips"><button class="chip go" type="button" data-act="f-tf" data-v="*"' +
        ' aria-pressed="' + (!f.tfs.length) + '">Saare</button></div>' +
      '<div class="sub">Intraday</div><div class="chips">' + chipRow('f-tf', INTRADAY, f.tfs) + '</div>' +
      '<div class="sub">Higher TF · EOD</div><div class="chips">' + chipRow('f-tf', HIGHER, f.tfs) + '</div>';

    html += '<div class="label">DIRECTION</div><div class="chips">' +
      ['*', 'BUY', 'SELL'].map(function (v) {
        return '<button class="chip' + (v === '*' ? ' go' : '') + '" type="button" data-act="f-side" data-v="' + v + '"' +
          ' aria-pressed="' + (f.side === v || (v === '*' && !f.side)) + '">' +
          (v === '*' ? 'Dono' : v) + '</button>';
      }).join('') + '</div>';

    html += '<div class="label">SQUEEZE KE BAAD CROSS</div><div class="chips">' +
      [0, 2, 4, 999].map(function (v) {
        var name = v === 0 ? 'Usi candle' : (v === 999 ? 'Koi bhi' : v + ' tak');
        return '<button class="chip" type="button" data-act="f-bars" data-v="' + v + '"' +
          ' aria-pressed="' + (f.maxBars === v) + '">' + name + '</button>';
      }).join('') + '</div>';

    html += '<div class="btnrow">' +
      '<button class="btn ghost" type="button" data-act="f-reset">Reset</button>' +
      '<a class="btn wide" href="#/feed">' + st.alerts.length + ' alerts dikhao</a>' +
    '</div><div class="spacer"></div>';
    return html;
  }

  /* ---------------- Stock detail ---------------- */

  function viewStock(st, sym, tf) {
    var u = st.universe.filter(function (r) { return r.sym === sym && r.tf === tf; })[0];
    var mine = st.allAlerts.filter(function (a) { return a.sym === sym; })
      .sort(function (a, b) { return tfRank(a.tf) - tfRank(b.tf); });
    var here = mine.filter(function (a) { return a.tf === tf; });

    if (!u && !here.length) {
      return '<p class="empty">' + esc(sym) + ' ' + esc(tf) + ' ka data feed mein nahi hai.</p>';
    }

    var side = here.length ? here[0].side : '';
    var html = '<div class="wrap" style="padding-top:16px">' +
      '<div style="display:flex;align-items:flex-end;justify-content:space-between;gap:12px">' +
        '<div><div style="font-size:24px;font-weight:700;letter-spacing:-0.6px">' + esc(sym) + '</div>' +
        '<div class="stamp" style="margin-top:3px">NSE · F&amp;O · ' + esc(tf) + '</div></div>' +
        '<div style="text-align:right"><div style="font-size:22px;font-weight:600" class="num">' +
          num(u ? u.close : (here[0] && here[0].close)) + '</div>' +
          (side ? '<div style="margin-top:5px">' + sideTag(side) + '</div>' : '') +
        '</div></div></div>';

    if (u) {
      html += '<div class="kv">' +
        '<div><div class="k">RSI</div><div class="v num">' + num(u.rsi, 1) + '</div></div>' +
        '<div><div class="k">RSI WIDTH</div><div class="v num">' + num(u.rsiw) + '</div></div>' +
        '<div><div class="k">LOW SE</div><div class="v num">' + num(u.rratio, 2) + 'x</div></div>' +
      '</div>';
      html += '<div class="kv">' +
        '<div><div class="k">SQ%</div><div class="v num">' + num(u.sq, 1) + '</div></div>' +
        '<div><div class="k">PRICE BB%</div><div class="v num">' + num(u.prw) + '</div></div>' +
        '<div><div class="k">LOW SE</div><div class="v num">' + num(u.pratio, 2) + 'x</div></div>' +
      '</div>';

      var bits = [];
      if (u.sqz_ago === 0) bits.push('RSI squeeze <b>abhi</b> chal raha hai');
      else if (u.sqz_ago < 999) bits.push('RSI squeeze <b>' + u.sqz_ago + ' candle pehle</b> tha');
      if (u.psq) bits.push('Price BB squeeze <b>abhi</b>');
      if (u.hab) bits.push('HA close upper BB ke <b>upar</b>');
      if (u.hbl) bits.push('HA close lower BB ke <b>neeche</b>');
      if (u.mbb_b) bits.push('Mid-BB ke <b>upar</b> close');
      if (u.mbb_s) bits.push('Mid-BB ke <b>neeche</b> close');
      if (bits.length) html += '<div class="note">' + bits.join('<br>') + '</div>';
      html += '<div class="note">Candle: ' + esc(u.ts) + '</div>';
    }

    if (here.length && here[0].entry) {
      html += '<div class="panel" style="background:#121A16;border-color:#23312B">' +
        '<div class="panel-head"><span class="k" style="color:#3DDC97">ENTRY TRIGGER</span></div>' +
        '<div style="margin-top:7px;font-size:14px;font-weight:600;line-height:1.45">' +
        (side === 'SELL' ? 'Candle ka low ' : 'Candle ka high ') +
        '<span class="num">' + num(here[0].entry) + '</span> break ho to lena</div></div>';
    }

    if (mine.length) {
      html += '<div class="label">ISKE ALERTS</div>' + mine.map(function (a) {
        return '<a class="row" href="#/stock/' + esc(sym) + '/' + esc(a.tf) + '">' +
          '<span class="badge-sq">' + esc(a.tf) + '</span>' +
          '<span class="grow"><span class="name">' + esc(setupName(a.setup)) + '</span>' +
          '<span class="meta">' + esc(sqzText(a.sqz_ago) || ('SQ% ' + num(a.sq, 1))) + '</span></span>' +
          (a.side ? sideTag(a.side) : '') + '</a>';
      }).join('');
    }

    html += '<div class="btnrow"><a class="btn wide" target="_blank" rel="noopener"' +
      ' href="https://www.tradingview.com/chart/?symbol=NSE%3A' + encodeURIComponent(sym) + '">' +
      'TradingView mein kholo</a></div><div class="spacer"></div>';
    return html;
  }

  global.V = {
    SETUPS: SETUPS,
    TF_ORDER: TF_ORDER,
    BANDS: BANDS,
    esc: esc,
    tfRank: tfRank,
    feed: viewFeed,
    channels: viewChannels,
    squeeze: viewSqueeze,
    filter: viewFilter,
    stock: viewStock,
    funnelRows: funnelRows,
    funnelList: funnelList
  };
})(window);
