/* Scan by Akshay -- app ka khol: pull-to-refresh, haptic, scroll yaad
   rakhna, foreground par apne aap taaza karna, aur install ka ishara.
   Yahi cheezein browser page ko app jaisa banati hain. */
(function (global) {
  'use strict';

  var LS_HINT = 'sba.hint';
  var scrolls = {};
  var onRefresh = null;

  function standalone() {
    try {
      return global.matchMedia('(display-mode: standalone)').matches ||
        global.navigator.standalone === true;
    } catch (e) { return false; }
  }

  /* Halka sa kampan. Sirf asli ungli ke baad: mouse click Chrome ke liye
     "tap" nahi hai, to desktop par ye chup rehta hai -- aur wahan kampan ka
     matlab bhi nahi. iOS par vibrate hai hi nahi, wahan bhi chup. */
  var tapped = false;
  document.addEventListener('touchstart', function (ev) {
    if (ev.isTrusted) tapped = true;
  }, { capture: true, passive: true });

  function haptic(ms) {
    if (!tapped) return;
    try { if (navigator.vibrate) navigator.vibrate(ms || 8); } catch (e) { /* ignore */ }
  }

  /* ---------------- scroll yaad rakhna ---------------- */

  function remember(key) {
    scrolls[key] = global.scrollY || 0;
  }

  function restore(key, fresh) {
    // Nayi screen hamesha upar se; wapas aane par jahan chhoda tha wahin.
    var y = fresh ? 0 : (scrolls[key] || 0);
    global.scrollTo(0, y);
  }

  /* ---------------- pull to refresh ---------------- */

  function initPull(el) {
    var startY = 0;
    var pulling = false;
    var dist = 0;
    var MAX = 90;
    var TRIP = 64;

    function reset() {
      pulling = false;
      dist = 0;
      el.style.transform = '';
      el.style.opacity = '';
      el.classList.remove('spin');
    }

    document.addEventListener('touchstart', function (ev) {
      if (global.scrollY > 0 || ev.touches.length !== 1 || el.classList.contains('spin')) return;
      startY = ev.touches[0].clientY;
      pulling = true;
      dist = 0;
    }, { passive: true });

    document.addEventListener('touchmove', function (ev) {
      if (!pulling) return;
      dist = ev.touches[0].clientY - startY;
      if (dist <= 0 || global.scrollY > 0) { reset(); return; }
      // Jitna kheencho utna kam chale -- rubber band jaisa.
      var shown = Math.min(MAX, dist * 0.45);
      el.style.opacity = Math.min(1, shown / TRIP);
      el.style.transform = 'translateY(' + shown + 'px) rotate(' + (shown * 4) + 'deg)';
    }, { passive: true });

    document.addEventListener('touchend', function () {
      if (!pulling) return;
      var go = dist * 0.45 >= TRIP;
      if (!go) { reset(); return; }
      haptic(12);
      el.style.transform = 'translateY(' + TRIP + 'px)';
      el.style.opacity = 1;
      el.classList.add('spin');
      var done = function () { reset(); };
      if (onRefresh) {
        var p = onRefresh();
        if (p && p.then) p.then(done, done); else setTimeout(done, 600);
      } else { setTimeout(done, 600); }
    }, { passive: true });
  }

  /* ---------------- taaza rakhna ---------------- */

  function marketHours() {
    // IST 09:10--15:45, Mon--Fri. Iske bahar poll karne ka koi matlab nahi.
    var now = new Date();
    var ist = new Date(now.getTime() + (now.getTimezoneOffset() + 330) * 60000);
    var day = ist.getDay();
    if (day === 0 || day === 6) return false;
    var mins = ist.getHours() * 60 + ist.getMinutes();
    return mins >= 550 && mins <= 945;
  }

  function initFresh() {
    var last = Date.now();
    // App dobara saamne aate hi feed check -- purana data kabhi na dikhe.
    document.addEventListener('visibilitychange', function () {
      if (document.visibilityState !== 'visible') return;
      if (Date.now() - last < 30000) return;
      last = Date.now();
      if (onRefresh) onRefresh();
    });
    setInterval(function () {
      if (document.visibilityState !== 'visible' || !marketHours()) return;
      last = Date.now();
      if (onRefresh) onRefresh();
    }, 180000);
  }

  /* ---------------- install ka ishara ---------------- */

  function hintHTML() {
    if (standalone()) return '';
    try { if (localStorage.getItem(LS_HINT) === 'off') return ''; } catch (e) { /* ignore */ }
    var ios = /iPad|iPhone|iPod/.test(navigator.userAgent);
    var how = ios
      ? 'Share dabao, phir <b>Add to Home Screen</b>.'
      : 'Menu dabao, phir <b>Add to Home screen</b>.';
    return '<div class="hint"><p>Home screen par laga lo -- phir ye poore screen par ' +
      'app jaisa khulega. ' + how + '</p>' +
      '<button type="button" data-act="hint-off" aria-label="Hatao">&times;</button></div>';
  }

  function hintOff() {
    try { localStorage.setItem(LS_HINT, 'off'); } catch (e) { /* ignore */ }
  }

  global.Shell = {
    standalone: standalone,
    haptic: haptic,
    remember: remember,
    restore: restore,
    hintHTML: hintHTML,
    hintOff: hintOff,
    marketHours: marketHours,
    init: function (ptrEl, refreshFn) {
      onRefresh = refreshFn;
      if (ptrEl) initPull(ptrEl);
      initFresh();
    }
  };
})(window);
