/* Scan by Akshay -- Squeeze funnel, Filter aur Stock detail.
   Saanjhe helper views.js se aate hain; dono milkar global.V banate hain. */
(function (global) {
  'use strict';

  var V = global.V;
  var SETUPS = V.SETUPS, BANDS = V.BANDS, SCALES = V.SCALES;
  var INTRADAY = V.INTRADAY, HIGHER = V.HIGHER;
  var esc = V.esc, num = V.num, bandOf = V.bandOf;
  var setupName = V.setupName, tfRank = V.tfRank;
  var sqzText = V.sqzText, sideTag = V.sideTag;

  /* ---------------- Squeeze funnel ---------------- */

  // Jis number par list chalti hai. Chhota = zyada tight.
  // 'Dono' relative mein dono ratios ka bada wala leta hai. Absolute mein
  // RSI points aur price % ko seedha nahi jod sakte -- alag paimane hain --
  // isliye wahan har stock ki pool ke andar RANK li jaati hai aur dono
  // ranks ka bada wala sort key banta hai. Matlab wahi: tabhi upar aao jab
  // dono bands tight hon.
  // 'rel' ab pehle rel2 dekhta hai (farsh-mukt). Jab tak naya scan nahi chala,
  // feed mein rel2 nahi hoga -- tab purane rel par gir jaata hai.
  function relField(row, b) {
    if (b.rel2 !== 'both' && row[b.rel2] != null) return b.rel2;
    return b.rel;
  }

  function ratioOf(row, band, scale) {
    var b = bandOf(band);
    var key = scale === 'abs' ? b.abs
            : scale === 'pctl' ? b.pctl
            : relField(row, b);
    if (key === 'both') {
      var x, y;
      if (scale === 'abs') { x = row.rsiw; y = row.prw; }
      else if (scale === 'pctl') { x = row.rpctl; y = row.ppctl; }
      else {
        x = row.rratio2 != null ? row.rratio2 : row.rratio;
        y = row.pratio2 != null ? row.pratio2 : row.pratio;
      }
      if (x == null || y == null) return null;
      return scale === 'abs' ? null : Math.max(x, y);
    }
    return row[key];
  }

  function bothAbsKeys(pool) {
    var rank = function (field) {
      var sorted = pool.filter(function (r) { return r[field] != null; })
        .sort(function (a, b) { return a[field] - b[field]; });
      var map = {};
      sorted.forEach(function (r, i) { map[r.sym] = sorted.length > 1 ? i / (sorted.length - 1) : 0; });
      return map;
    };
    var ra = rank('rsiw'), pa = rank('prw');
    return function (r) {
      if (ra[r.sym] == null || pa[r.sym] == null) return null;
      return Math.max(ra[r.sym], pa[r.sym]);
    };
  }

  // "Squeeze kitni candle pehle tha" -- har band ka apna. Price BB tab par
  // RSI ka number dikhana galat hoga, dono alag cheezein hain.
  function agoOf(row, band) {
    var r = row.sqz_ago == null ? 999 : row.sqz_ago;
    var p = row.psqz_ago == null ? 999 : row.psqz_ago;
    if (band === 'price') return p;
    if (band === 'both') return Math.max(r, p);
    return r;  // rsi aur mid -- dono RSI ki umar dekhte hain
  }

  function funnelRows(st) {
    var s = st.sq;
    var pool = st.universe.filter(function (r) { return r.tf === s.tf; });

    if (s.band === 'mid') {
      pool = pool.filter(function (r) { return r.mbb_b || r.mbb_s; });
    }

    var rows, cut = null;
    if (s.view === 'open') {
      rows = pool.filter(function (r) {
        var ago = agoOf(r, s.band);
        return ago >= 1 && ago <= s.bars;
      }).sort(function (a, b) { return agoOf(a, s.band) - agoOf(b, s.band); });
      return { rows: rows, pool: pool.length, cut: null, max: pool.length };
    }

    // Ratio 1.00 se neeche ja hi nahi sakta -- width apne hi 20-bar low se
    // tulti hai aur low usi window mein hai. 3D par 19 stock ek saath
    // 1.000 par baith jaate hain, to ratio wala slider wahin ruk jaata
    // tha. Isliye slider ab GINTI chalata hai: sabse tight se N.
    //
    // Barabari ratio par tootti hai asli chaudai se -- dono 1.000x par
    // hon to jiski band sach much patli hai wo upar. Isi se slider 1 par
    // le jaane par sabse tight ek naam bachta hai.
    var band = bandOf(s.band);
    var scale = (s.scale === 'abs' || s.scale === 'pctl') ? s.scale : 'rel';
    var wkey = scale === 'abs' ? (band.abs === 'both' ? 'rsiw' : band.abs)
                               : (band.abs === 'both' ? 'rsiw' : band.abs);
    var bothAbs = (band.id === 'both' && scale === 'abs') ? bothAbsKeys(pool) : null;
    var keyOf = function (r) {
      return bothAbs ? bothAbs(r) : ratioOf(r, s.band, scale);
    };

    rows = pool.filter(function (r) {
      return keyOf(r) != null;
    }).sort(function (a, b) {
      var d = keyOf(a) - keyOf(b);
      if (d) return d;
      return (a[wkey] == null ? 1e9 : a[wkey]) - (b[wkey] == null ? 1e9 : b[wkey]);
    });

    var max = rows.length;
    var top = Math.max(1, Math.min(s.top || max, max));
    rows = rows.slice(0, top);
    // 'Dono' absolute ka key ek rank hai, number nahi -- uska cutoff
    // dikhana bhramit karega, isliye wahan chhod dete hain.
    cut = (rows.length && !bothAbs) ? keyOf(rows[rows.length - 1]) : null;
    return { rows: rows, pool: pool.length, cut: cut, max: max, scale: scale };
  }

  function funnelList(st, res) {
    var s = st.sq;
    var band = bandOf(s.band);
    if (!res.rows.length) {
      // Percentile wala field purane feed mein nahi hota. Aisa mat kehna ki
      // "koi tight nahi" -- asli wajah ye hai ki naya scan abhi chala nahi.
      var needScan = res.scale === 'pctl' && res.pool;
      return '<p class="empty">' + (needScan
        ? '100-candle percentile naye scan ke baad aayega. Tab tak "apne low se" ya "seedha number" use karo.'
        : res.pool
          ? 'Itna tight koi nahi. Slider thoda dheela karo.'
          : s.tf + ' ka data abhi feed mein nahi hai.') + '</p>';
    }
    var abs = res.scale === 'abs';
    var isPctl = res.scale === 'pctl';
    var wkey = band.abs === 'both' ? 'rsiw' : band.abs;
    var wunit = band.abs === 'prw' ? '%' : (band.id === 'price' ? '%' : '');
    return res.rows.map(function (r) {
      var rel = ratioOf(r, s.band, 'rel');
      var pc = ratioOf(r, s.band, 'pctl');
      var width = r[wkey];
      var frac = abs ? (width || 0) / (wkey === 'prw' ? 40 : 50)
               : isPctl ? (pc == null ? 1 : pc / 100)
               : (rel || 1) / 2;
      var pct = Math.max(4, Math.min(100, Math.round(frac * 100)));
      var ago = agoOf(r, s.band);
      var relTxt = rel != null ? num(rel, 2) + 'x apne low se' : '';
      var pcTxt = pc != null ? num(pc, 0) + ' percentile (100 candle)' : '';
      var absTxt = 'band ' + num(width, 2) + (wkey === 'prw' ? '%' : ' pts');
      var meta;
      if (s.view === 'open') {
        meta = sqzText(ago) + (rel != null ? ' · ab ' + num(rel, 2) + 'x' : '');
      } else if (s.band === 'mid') {
        meta = (r.mbb_b ? 'mid-BB ke upar close' : 'mid-BB ke neeche close') +
          ' · ' + (abs ? absTxt : isPctl ? pcTxt : relTxt);
      } else if (s.band === 'both') {
        meta = abs
          ? 'RSI ' + num(r.rsiw, 2) + ' pts · price ' + num(r.prw, 2) + '%'
          : isPctl
            ? 'RSI ' + num(r.rpctl, 0) + ' pctl · price ' + num(r.ppctl, 0) + ' pctl'
            : 'RSI ' + num(r.rratio2 != null ? r.rratio2 : r.rratio, 2) + 'x · price ' +
              num(r.pratio2 != null ? r.pratio2 : r.pratio, 2) + 'x';
      } else {
        // Dono paimane ek saath -- jo chuna hai wo pehle, doosra peeche,
        // taaki tulna karte waqt tab badalna na pade.
        meta = (abs ? absTxt + (relTxt ? ' · ' + relTxt : '')
                    : isPctl ? pcTxt + ' · ' + absTxt
                    : relTxt + ' · ' + absTxt) +
          (ago === 0 ? ' · low par' : '');
      }
      // Asli squeeze (BB, Keltner ke andar) alag se -- width low par hona
      // aur squeeze hona do alag baatein hain.
      var real = (s.band === 'price' ? r.psq : r.rsq)
        ? ' <span class="tag sqz">SQUEEZE</span>' : '';
      return '<a class="row" href="#/stock/' + esc(r.sym) + '/' + esc(r.tf) + '">' +
        '<span class="grow">' +
          '<span class="name">' + esc(r.sym) + real + '</span>' +
          '<span class="meta">' + esc(meta) + '</span>' +
          '<span class="bar"><i class="' + (s.view === 'open' ? 'open' : '') + '" style="width:' + pct + '%"></i></span>' +
        '</span>' +
        '<span class="right"><span class="big num">' + num(width, 2) + wunit + '</span>' +
        '<span class="small">width</span></span>' +
      '</a>';
    }).join('');
  }

  // Cutoff ka matlab mode ke saath badalta hai: relative mode mein guna,
  // number mode mein seedhe points.
  function cutText(bandId, cut, scale) {
    var b = bandOf(bandId);
    if (scale === 'pctl') return num(cut, 0) + ' percentile';
    if (scale !== 'abs') return num(cut, 2) + 'x';
    return num(cut, 2) + (b.abs === 'prw' ? '%' : ' pts');
  }

  function viewSqueeze(st) {
    var s = st.sq;
    var res = funnelRows(st);
    var tfs = (st.univTfs && st.univTfs.length) ? st.univTfs : st.feedTfs;

    var html = '<div class="chips scroll">' + tfs.map(function (tf) {
      return '<button class="chip" type="button" data-act="sq-tf" data-v="' + esc(tf) + '"' +
        ' aria-pressed="' + (tf === s.tf) + '">' + esc(tf) + '</button>';
    }).join('') + '</div>';

    // Funnel ko har stock ka data chahiye, sirf alert wale ka nahi. Jis TF
    // ka scan aaj abhi tak nahi chala uska chip dikhana bekaar hai -- par
    // bina bataye lagta hai ki wo TF app mein hai hi nahi.
    var pending = (st.feedTfs || []).filter(function (tf) {
      return tfs.indexOf(tf) < 0;
    });
    if (pending.length) {
      html += '<div class="sub">' + esc(pending.join(' · ')) +
        ' -- inka scan aaj abhi baaki hai, EOD ke baad yahan aa jayenge</div>';
    }

    html += '<div class="seg">' + BANDS.map(function (b) {
      return '<button type="button" data-act="sq-band" data-v="' + b.id + '"' +
        ' aria-pressed="' + (b.id === s.band) + '">' + esc(b.name) + '</button>';
    }).join('') + '</div>';

    // Ek hi switch saare bands ko relative se absolute par le jaata hai.
    var sc = (s.scale === 'abs' || s.scale === 'pctl') ? s.scale : 'rel';
    html += '<div class="seg small">' + SCALES.map(function (x) {
      return '<button type="button" data-act="sq-scale" data-v="' + x.id + '"' +
        ' aria-pressed="' + (x.id === sc) + '">' + esc(x.name) + '</button>';
    }).join('') + '</div>';

    var isOpen = s.view === 'open';
    var top = Math.max(1, Math.min(s.top || res.max, res.max || 1));
    html += '<div class="panel">' +
      '<div class="panel-head">' +
        '<label class="k" for="sq-range" id="sq-label">' +
          (isOpen ? 'SQUEEZE KITNE CANDLE PEHLE' : 'SABSE TIGHT KITNE') +
        '</label>' +
        '<span class="v num" id="sq-val">' +
          (isOpen ? '≤ ' + s.bars : 'top ' + top) +
        '</span>' +
      '</div>' +
      '<input id="sq-range" type="range" data-act="sq-range"' +
        ' min="1"' +
        ' max="' + (isOpen ? 20 : Math.max(1, res.max)) + '"' +
        ' step="1"' +
        ' value="' + (isOpen ? s.bars : top) + '">' +
      '<div class="ends"><span>' + (isOpen ? 'abhi khula' : 'sirf sabse tight') + '</span>' +
        '<span>' + (isOpen ? '20 candle' : 'sab ' + (res.max || 0)) + '</span></div>' +
      '<div class="count"><b class="num" id="sq-count">' + res.rows.length + '</b>' +
        '<span id="sq-note">stock · ' + res.pool + ' mein se (' + esc(s.tf) + ')' +
        (res.cut != null ? ' · cutoff ' + cutText(s.band, res.cut, res.scale) : '') + '</span></div>' +
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

    // Sirf wahi TF dikhao jo scanner asal mein scan karta hai. 5m kabhi
    // scan nahi hota -- uska chip hamesha 0 deta tha.
    var live = st.feedTfs && st.feedTfs.length ? st.feedTfs : INTRADAY.concat(HIGHER);
    var fi = INTRADAY.filter(function (t) { return live.indexOf(t) >= 0; });
    var fh = HIGHER.filter(function (t) { return live.indexOf(t) >= 0; });
    html += '<div class="label">TIMEFRAME</div>' +
      '<div class="chips"><button class="chip go" type="button" data-act="f-tf" data-v="*"' +
        ' aria-pressed="' + (!f.tfs.length) + '">Saare</button></div>' +
      (fi.length ? '<div class="sub">Intraday</div><div class="chips">' + chipRow('f-tf', fi, f.tfs) + '</div>' : '') +
      (fh.length ? '<div class="sub">Higher TF · EOD</div><div class="chips">' + chipRow('f-tf', fh, f.tfs) + '</div>' : '');

    html += '<div class="label">DIRECTION</div><div class="chips">' +
      ['*', 'BUY', 'SELL'].map(function (v) {
        return '<button class="chip' + (v === '*' ? ' go' : '') + '" type="button" data-act="f-side" data-v="' + v + '"' +
          ' aria-pressed="' + (f.side === v || (v === '*' && !f.side)) + '">' +
          (v === '*' ? 'Dono' : v) + '</button>';
      }).join('') + '</div>';

    // Absolute chhanni: sirf wahi alerts jinke stock ki RSI band itni
    // patli hai. Ye percentage se bilkul alag kaat deta hai.
    html += '<div class="label">BAND KI CHAUDAI · RSI</div><div class="chips">' +
      [[0, 'Koi bhi'], [25, '≤ 25 pts'], [20, '≤ 20 pts'], [15, '≤ 15 pts'], [12, '≤ 12 pts']]
        .map(function (p) {
          return '<button class="chip' + (p[0] === 0 ? ' go' : '') + '" type="button"' +
            ' data-act="f-width" data-v="' + p[0] + '"' +
            ' aria-pressed="' + ((f.maxWidth || 0) === p[0]) + '">' + esc(p[1]) + '</button>';
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

  // TradingView app mein kholo, website par nahi.
  //
  // Android: intent:// seedha app ke package par jaata hai, app na ho to
  // browser_fallback_url website khol deta hai. Ye bharosemand hai.
  //
  // iOS: TradingView ne koi URL scheme publish nahi kiya hai, aur saada
  // https link app ko hand off karega ya nahi ye app ke universal links
  // par nirbhar hai. Isliye teen tareeke rakhe hain aur chunav Setup
  // screen par hai -- jo aapke phone par chale wahi rakh lo.
  function tvLink(sym) {
    var web = 'https://www.tradingview.com/chart/?symbol=NSE%3A' + encodeURIComponent(sym);
    if (/Android/i.test(navigator.userAgent)) {
      var intent = 'intent://www.tradingview.com/chart/?symbol=NSE%3A' +
        encodeURIComponent(sym) +
        '#Intent;scheme=https;package=com.tradingview.tradingviewapp;' +
        'S.browser_fallback_url=' + encodeURIComponent(web) + ';end';
      return 'href="' + esc(intent) + '"';
    }
    // href website par rehta hai taaki long-press se copy/share kaam kare;
    // tap ko app.js pakad kar chune hue tareeke se kholta hai.
    return 'href="' + esc(web) + '" rel="noopener" data-act="tv" data-v="' + esc(sym) + '"';
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
        '<div><div class="k">BAND PTS</div><div class="v num">' + num(u.rsiw) +
          (u.rwlo != null ? '<span class="lo"> / ' + num(u.rwlo) + '</span>' : '') +
          '</div></div>' +
        '<div><div class="k">LOW SE</div><div class="v num">' +
          num(u.rratio2 != null ? u.rratio2 : u.rratio, 2) + 'x</div></div>' +
        '<div><div class="k">100 CANDLE</div><div class="v num">' +
          num(u.rpctl, 0) + '</div></div>' +
      '</div>';
      html += '<div class="kv">' +
        '<div><div class="k">SQ%</div><div class="v num">' + num(u.sq, 1) + '</div></div>' +
        '<div><div class="k">PRICE BB%</div><div class="v num">' + num(u.prw) +
          (u.pwlo != null ? '<span class="lo"> / ' + num(u.pwlo) + '</span>' : '') +
          '</div></div>' +
        '<div><div class="k">LOW SE</div><div class="v num">' +
          num(u.pratio2 != null ? u.pratio2 : u.pratio, 2) + 'x</div></div>' +
        '<div><div class="k">100 CANDLE</div><div class="v num">' +
          num(u.ppctl, 0) + '</div></div>' +
      '</div>';

      var bits = [];
      // "Kitni aur tight ho sakti hai" -- 7.99% apne aap mein tight lagta hai,
      // par is stock ki apni 100-candle low 4.53% ho to baat badal jaati hai.
      if (u.prw != null && u.pwlo != null && u.pwlo > 0) {
        var room = u.prw / u.pwlo;
        bits.push(room <= 1.05
          ? 'Price band <b>100 candle ki sabse patli</b> ke aas-paas (' + num(u.prw, 2) + '%)'
          : 'Price band <b>' + num(u.prw, 2) + '%</b> -- is stock ki 100-candle sabse patli <b>' +
            num(u.pwlo, 2) + '%</b> hai, yaani abhi <b>' + num(room, 1) + 'x</b> chaudi');
      }
      if (u.sqz_ago === 0) bits.push('RSI band ki chaudai <b>apne 20-bar low par</b>');
      else if (u.sqz_ago < 999) bits.push('RSI band chaudai low se <b>' + u.sqz_ago + ' candle</b> door');
      if (u.rsq) bits.push('RSI par <b>asli squeeze</b> (BB, Keltner ke andar)');
      if (u.psq) bits.push('Price par <b>asli squeeze</b> (BB, Keltner ke andar)');
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

    html += '<div class="btnrow"><a class="btn wide" ' + tvLink(sym) + '>' +
      'TradingView mein kholo</a></div><div class="spacer"></div>';
    return html;
  }

  V.squeeze = viewSqueeze;
  V.filter = viewFilter;
  V.stock = viewStock;
  V.funnelRows = funnelRows;
  V.funnelList = funnelList;
  V.cutText = cutText;
})(window);
