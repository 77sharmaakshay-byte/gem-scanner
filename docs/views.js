/* Scan by Akshay -- screens. Sirf HTML banata hai, data app.js se aata hai. */
(function (global) {
  'use strict';

  // Naam wahi jo setup asal mein karta hai. Pehle 'Price-BB squeeze' aur
  // 'RSI-BB squeeze' se lagta tha ki ek price ka squeeze hai doosra RSI ka
  // -- asal mein teeno aapas mein alag-alag hain: sirf price, sirf RSI, ya
  // dono. Jiska jo haal hai wahi likha hai.
  var SETUPS = [
    { id: 'RSI_BB_Cross_Setup', name: 'RSI band tod kar nikla', kind: 'cross',
      desc: 'RSI apni Bollinger band ke bahar nikla, pichhli candle andar thi' },
    { id: 'Gem_Setup_Intraday', name: 'Gem · intraday', kind: 'gem',
      desc: 'Intraday ka composite gem setup' },
    { id: 'Gem_Setup_HigherTF', name: 'Gem · higher TF', kind: 'gem',
      desc: '1D/2D/3D par gem setup -- sirf EOD run mein bharta hai' },
    { id: 'Price_BB_Squeeze', name: 'Sirf price tight', kind: 'sqz',
      desc: 'Price bands tight, RSI ke nahi' },
    { id: 'RSI_BB_Squeeze', name: 'Sirf RSI tight', kind: 'sqz',
      desc: 'RSI bands tight, price ke nahi' },
    { id: 'Both_Squeeze', name: 'Price + RSI dono tight', kind: 'sqz',
      desc: 'Dono bands ek saath tight' },
    { id: 'New_HA_Squeeze_Setup', name: 'Squeeze se breakout', kind: 'ha',
      desc: 'HA close band ke bahar, squeeze pichhli 3 candle mein tha' },
    { id: 'Mid_BB_Reversal_Setup', name: 'Middle BB palta', kind: 'mid',
      desc: 'Strong HA candle middle BB cross karke pichhli 2 candle ke high/low se aage' },
    // Ye scanner ka setup nahi hai -- app khud universe se banata hai.
    // Baaki sab channels percentage/relative par chalte hain; ye seedha
    // band ke number par, taaki dono tarah ke natije saath-saath dikhein.
    { id: 'RSI_Band_Absolute', name: 'RSI band sabse patli', kind: 'abs',
      desc: 'Har timeframe ke 10 sabse patli RSI band wale -- seedha number, percentage nahi' },
    { id: 'Price_Band_Absolute', name: 'Price band sabse patli', kind: 'abs',
      desc: 'Har timeframe ke 10 sabse patli price band wale -- seedha %, apne low se nahi' }
  ];

  // App ke apne banaye channels -- in par scanner ka alert nahi hota.
  var APP_SETUPS = ['RSI_Band_Absolute', 'Price_Band_Absolute'];

  var TF_ORDER = ['5m', '15m', '30m', '45m', '1H', '75m', '90m', '2H', '150m',
    '3H', '4H', '1D', '2D', '3D', '1W', '1M', '6M'];
  var INTRADAY = ['5m', '15m', '30m', '45m', '1H', '75m', '90m', '2H', '150m', '3H', '4H'];
  var HIGHER = ['1D', '2D', '3D', '1W', '1M', '6M'];

  // 'rsi' tightness ko RELATIVE naapta hai -- width apne 20-bar low se
  // kitni guna. Isme do stock jinki band 12 aur 24 chaudi hai, dono 1.00x
  // par barabar lagte hain.
  // Har band do tareeke se naapi ja sakti hai:
  //   'rel'  -- width apne 20-bar low se kitni guna (1.00x = apne low par)
  //   'abs'  -- band ka seedha number (RSI points, ya price ka %)
  // Relative mein 12 aur 24 points chaudi band dono 1.00x par barabar lag
  // sakti hain. Absolute mein 12 wali hamesha jeetti hai. Dono alag list
  // dete hain, isliye switch har band par lagta hai -- Dono par bhi.
  // rel2 = wahi "apne low se" par 20-bar min mein aaj ka candle shaamil nahi.
  // Purane rel ka farsh 1.00x tha (16% bars wahin atke the, isliye slider
  // ek stock tak nahi pahunchta tha); rel2 naya low banne par 1.00 se neeche
  // jaata hai. Purana rel sirf fallback hai jab tak naya scan nahi chalta.
  // pctl = band apni 100-candle history mein kis percentile par -- naapa gaya
  // sabse majboot relative paimana (sabse tight 3% par band 1.30x failti hai).
  var BANDS = [
    { id: 'rsi', name: 'RSI', rel: 'rratio', rel2: 'rratio2', pctl: 'rpctl',
      abs: 'rsiw', unit: '', absUnit: ' pts' },
    { id: 'price', name: 'Price', rel: 'pratio', rel2: 'pratio2', pctl: 'ppctl',
      abs: 'prw', unit: '%', absUnit: '%' },
    { id: 'both', name: 'Dono', rel: 'both', rel2: 'both', pctl: 'both',
      abs: 'both', unit: '', absUnit: '' },
    { id: 'mid', name: 'Mid-BB', rel: 'rratio', rel2: 'rratio2', pctl: 'rpctl',
      abs: 'rsiw', unit: '', absUnit: ' pts' }
  ];

  // Tarteeb naapne se nikli hai (5 saal, 218 naam, 2.42 lakh bars -- 5 candle
  // baad band kitni guna failti hai, base 1.064x; sabse tight 3%):
  //   dono milakar 1.438x · seedha number 1.456x · 100 candle 1.302x · apne low se 1.126x
  // 'best' seedha number ka 96% faida deta hai par saal mein 191 alag naam
  // dikhata hai (seedha number sirf 155) -- rozana wahi low-vol naam nahi aate.
  // 'rel' sabse kamzor hai, isliye sabse aakhir mein.
  var SCALES = [
    { id: 'best', name: 'dono taraf se tight' },
    { id: 'abs', name: 'seedha number' },
    { id: 'pctl', name: '100 candle mein' },
    { id: 'rel', name: 'apne low se' }
  ];

  function bandOf(id) {
    for (var i = 0; i < BANDS.length; i++) if (BANDS[i].id === id) return BANDS[i];
    return BANDS[0];
  }

  // Band ki chaudai jo har jagah dikhti hai -- feed cards, channels aur
  // stock detail sab isi se bolte hain.
  function widthText(u, band) {
    if (!u) return '';
    var b = bandOf(band || 'rsi');
    var v = u[b.abs === 'both' ? 'rsiw' : b.abs];
    if (v == null) return '';
    return 'band ' + num(v, 2) + (b.abs === 'prw' ? '%' : ' pts');
  }

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

  // Ye "squeeze" nahi hai. Ye sirf itna hai ki band ki chaudai apne 20-bar
  // low par (ya 10% ke andar) hai -- jo har teesri-chauthi candle par ho
  // jaata hai. Pehle isko "SQZ" likha tha, jisse lagta tha ki chart wala
  // squeeze chal raha hai. Naam wahi rakho jo cheez hai.
  function sqzText(bars) {
    if (bars === null || bars === undefined || bars >= 999) return '';
    if (bars <= 0) return 'width 20-bar low par';
    return bars === 1 ? 'low se 1 candle' : 'low se ' + bars + ' candle';
  }

  function sqzTag(bars) {
    if (bars === null || bars === undefined || bars >= 999) return '';
    return bars <= 0 ? 'LOW PAR' : 'LOW +' + bars;
  }

  function sideTag(side) {
    if (side === 'BUY') return '<span class="tag buy">BUY</span>';
    if (side === 'SELL') return '<span class="tag sell">SELL</span>';
    return '';
  }

  /* ---------------- Feed ---------------- */

  function heroCard(a, u) {
    var sell = a.side === 'SELL';
    var sq = sqzTag(a.sqz_ago);
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
        (u && u.rsiw != null
          ? '<div><div class="k">RSI BAND</div><div class="v num">' + num(u.rsiw, 1) + '</div></div>' : '') +
        (u && u.prw != null
          ? '<div><div class="k">PRICE BB</div><div class="v num">' + num(u.prw, 1) + '%</div></div>' : '') +
        (a.entry ? '<div><div class="k">ENTRY</div><div class="v num">' + num(a.entry) + '</div></div>' : '') +
      '</div>' +
    '</a>';
  }

  function smallCard(a, u) {
    var sq = sqzText(a.sqz_ago);
    // Dono paimane card par. Absolute channels mein number pehle, kyunki
    // wahi unka matlab hai; baaki channels mein percentage pehle.
    var priceCh = a.setup === 'Price_Band_Absolute';
    var w = u == null ? ''
      : (priceCh
          ? (u.prw != null ? 'band ' + num(u.prw, 1) + '%' : '')
          : (u.rsiw != null ? 'band ' + num(u.rsiw, 1) + ' pts' : ''));
    if (APP_SETUPS.indexOf(a.setup) >= 0 && w) {
      var t = w; w = sq || ('SQ% ' + num(a.sq, 1)); sq = t;
    }
    return '<a class="card" href="#/stock/' + esc(a.sym) + '/' + esc(a.tf) + '">' +
      '<div class="card-top"><span class="tag">' + esc(a.tf) + '</span>' + sideTag(a.side) + '</div>' +
      '<div class="card-sym">' + esc(a.sym) + '</div>' +
      '<div class="card-price num">' + num(a.close) + '</div>' +
      '<div class="card-note' + (APP_SETUPS.indexOf(a.setup) >= 0 ? ' lead' : '') + '">' +
        esc(sq || ('SQ% ' + num(a.sq, 1))) + '</div>' +
      (w ? '<div class="card-note num">' + esc(w) + '</div>' : '') +
    '</a>';
  }

  // Channel mein ghusne par feed sirf usi channel ki reh jaati hai, par
  // wapas aane ka koi raasta nahi tha -- Feed tab pehle se chuna hua hota
  // hai aur back chevron sirf stock detail par dikhta tha. Ab upar ek
  // patti aati hai jo batati hai kya laga hai aur ek tap mein hata deti hai.
  function filterBar(st) {
    var f = st.filter;
    var on = [];
    f.setups.forEach(function (id) { on.push(setupName(id)); });
    if (f.tfs.length) on.push(f.tfs.join(', '));
    if (f.side) on.push(f.side);
    if (f.maxWidth) on.push('band ≤ ' + f.maxWidth + ' pts');
    if (f.maxBars !== 999) on.push('squeeze ke ' + f.maxBars + ' candle andar');
    if (!on.length) return '';
    return '<div class="fbar">' +
      '<span class="fbar-txt">' + esc(on.join(' · ')) + '</span>' +
      '<button class="fbar-x" type="button" data-act="f-reset">' +
        'Saare dikhao</button>' +
    '</div>';
  }

  function viewFeed(st) {
    var alerts = st.alerts;
    if (!alerts.length) {
      // Khali screen ko batana chahiye KYUN khali hai. Filter chup-chaap
      // laga reh jaata tha aur lagta tha ki scan hi nahi chala.
      var f = st.filter;
      var on = [];
      f.setups.forEach(function (id) { on.push(setupName(id)); });
      if (f.tfs.length) on.push(f.tfs.join(', '));
      if (f.side) on.push(f.side);
      if (f.maxBars !== 999) on.push('squeeze ke ' + f.maxBars + ' candle andar');

      if (!st.allAlerts.length) {
        return '<p class="empty">Feed mein abhi koi alert nahi.<br>' +
          'Agle scan ka intezaar karo.</p>';
      }
      return filterBar(st) +
        '<p class="empty">Is filter par koi alert nahi.<br>' +
        'Poori feed mein <b>' + st.allAlerts.length + '</b> alerts hain.</p>' +
        '<div class="btnrow"><button class="btn wide" type="button" data-act="f-reset">' +
        'Filter hatao</button></div>';
    }

    // Hero 'aaj ka top setup' kehta hai, isliye wahan sirf scanner ke asli
    // alerts aate hain -- app ke apne banaye channels nahi.
    var real = alerts.filter(function (a) { return APP_SETUPS.indexOf(a.setup) < 0; });
    var sorted = (real.length ? real : alerts).slice().sort(function (a, b) {
      var sa = a.sqz_ago >= 999 ? 500 : a.sqz_ago;
      var sb = b.sqz_ago >= 999 ? 500 : b.sqz_ago;
      if (sa !== sb) return sa - sb;
      return tfRank(b.tf) - tfRank(a.tf);
    });

    var U = st.uidx || {};
    var uOf = function (a) { return U[a.sym + '|' + a.tf]; };
    var html = filterBar(st) + heroCard(sorted[0], uOf(sorted[0]));
    var heroKey = sorted[0].setup + '|' + sorted[0].tf + '|' + sorted[0].sym;
    var rest = alerts.filter(function (a) {
      return (a.setup + '|' + a.tf + '|' + a.sym) !== heroKey;
    }).sort(function (a, b) {
      var sa = a.sqz_ago >= 999 ? 500 : a.sqz_ago;
      var sb = b.sqz_ago >= 999 ? 500 : b.sqz_ago;
      if (sa !== sb) return sa - sb;
      return tfRank(b.tf) - tfRank(a.tf);
    });

    SETUPS.forEach(function (s) {
      var mine = rest.filter(function (a) { return a.setup === s.id; });
      if (!mine.length) return;
      html += '<div class="rowhead" style="padding-top:22px">' +
        '<h2>' + esc(s.name) + '</h2><span class="n">' + mine.length + '</span></div>' +
        '<div class="rail">' + mine.map(function (a) { return smallCard(a, uOf(a)); }).join('') + '</div>';
    });

    return html + '<div class="spacer"></div>';
  }

  /* ---------------- Channels ---------------- */

  function channelRow(s, count, tfs, cls, avgW) {
    var sub = tfs.length ? tfs.join(' · ') : 'Aaj koi alert nahi';
    if (avgW != null) sub = 'band aausat ' + num(avgW, 1) + ' pts · ' + sub;
    return '<a class="row" href="#/feed?setup=' + esc(s.id) + '">' +
      '<span class="badge-sq ' + cls + '">' + esc(s.kind.toUpperCase().slice(0, 5)) + '</span>' +
      '<span class="grow"><span class="name">' + esc(s.name) + '</span>' +
      '<span class="meta">' + esc(s.desc || '') + '</span>' +
      '<span class="meta dim">' + esc(sub) + '</span></span>' +
      (count ? '<span class="pill">' + count + '</span>' : '<span class="pill quiet">0</span>') +
    '</a>';
  }

  function viewChannels(st) {
    var all = st.allAlerts;
    var html = '<a class="row" href="#/feed?setup=*">' +
      '<span class="badge-sq">ALL</span>' +
      '<span class="grow"><span class="name">Saare signals</span>' +
      '<span class="meta">Har setup, har timeframe -- ek jagah</span></span>' +
      '<span class="pill" style="background:#F2F4F7">' + all.length + '</span></a>';

    var groups = [
      { title: 'BAND TODNA', ids: ['RSI_BB_Cross_Setup'], cls: 'eod' },
      { title: 'GEM AUR TIGHT BANDS', ids: ['Gem_Setup_Intraday', 'Gem_Setup_HigherTF',
        'Price_BB_Squeeze', 'RSI_BB_Squeeze', 'Both_Squeeze', 'New_HA_Squeeze_Setup'], cls: '' },
      { title: 'PALATNA', ids: ['Mid_BB_Reversal_Setup'], cls: 'mid' },
      { title: 'SEEDHA NUMBER · APP KA APNA', cls: 'abs',
        ids: ['RSI_Band_Absolute', 'Price_Band_Absolute'] }
    ];

    groups.forEach(function (g) {
      html += '<div class="label">' + esc(g.title) + '</div>';
      g.ids.forEach(function (id) {
        var s = SETUPS.filter(function (x) { return x.id === id; })[0];
        var mine = all.filter(function (a) { return a.setup === id; });
        var tfs = [];
        mine.forEach(function (a) { if (tfs.indexOf(a.tf) < 0) tfs.push(a.tf); });
        tfs.sort(function (a, b) { return tfRank(a) - tfRank(b); });
        // Is channel ke stocks ki band kitni patli hai -- absolute paimana
        // channel ke level par bhi, taaki bina khole andaza lag jaye.
        var ws = [];
        mine.forEach(function (a) {
          var u = (st.uidx || {})[a.sym + '|' + a.tf];
          if (u && u.rsiw != null) ws.push(u.rsiw);
        });
        var avg = ws.length ? ws.reduce(function (x, y) { return x + y; }, 0) / ws.length : null;
        html += channelRow(s, mine.length, tfs, g.cls, avg);
      });
    });

    return html + '<div class="spacer"></div>';
  }

  // Screens do file mein bante hain -- ek file 500 line se badi na ho.
  // Yahan saanjhe helper aur Feed/Channels; baaki screens.js mein.
  global.V = {
    SETUPS: SETUPS,
    APP_SETUPS: APP_SETUPS,
    TF_ORDER: TF_ORDER,
    INTRADAY: INTRADAY,
    HIGHER: HIGHER,
    BANDS: BANDS,
    SCALES: SCALES,
    esc: esc,
    num: num,
    setupName: setupName,
    tfRank: tfRank,
    sqzText: sqzText,
    sqzTag: sqzTag,
    sideTag: sideTag,
    bandOf: bandOf,
    widthText: widthText,
    feed: viewFeed,
    channels: viewChannels
  };
})(window);
