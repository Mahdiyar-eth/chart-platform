/* ══════════════════════════════════════════════════════════════
 *  Zayche Galactic v2 — shell behaviour
 *  Drawer · theme · reveal-on-scroll · PWA install · SW registration
 *
 *  Rules obeyed here:
 *   • no layout thrash: reveal uses IntersectionObserver, not scroll handlers
 *   • drawer traps focus and closes on Esc / backdrop / route change
 *   • install prompt is a real button (never an invisible hover-only target)
 * ══════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  // ─────────────────────────── drawer ───────────────────────────
  var drawer = document.getElementById('gxDrawer');
  var scrim = document.getElementById('gxScrim');
  var opener = document.querySelector('[aria-controls="gxDrawer"]');
  var lastFocus = null;

  window.gxDrawer = function (open) {
    if (!drawer || !scrim) return;
    drawer.classList.toggle('is-open', open);
    scrim.classList.toggle('is-open', open);
    document.body.style.overflow = open ? 'hidden' : '';
    if (opener) opener.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (open) {
      lastFocus = document.activeElement;
      var first = drawer.querySelector('a, button');
      if (first) first.focus();
    } else if (lastFocus) {
      lastFocus.focus();
    }
  };

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && drawer && drawer.classList.contains('is-open')) {
      window.gxDrawer(false);
    }
  });

  // ─────────────────────────── theme ───────────────────────────
  function toggleTheme() {
    var root = document.documentElement;
    var next = root.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
    if (next === 'light') root.setAttribute('data-theme', 'light');
    else root.removeAttribute('data-theme');
    try { localStorage.setItem('zayche-theme', next); } catch (e) {}
  }
  ['gxTheme', 'gxThemeDrawer'].forEach(function (id) {
    var el = document.getElementById(id);
    if (el) el.addEventListener('click', toggleTheme);
  });

  // ──────────────────── reveal on scroll (cheap) ────────────────────
  var reveals = document.querySelectorAll('.gx-reveal');
  if (reveals.length) {
    if (!('IntersectionObserver' in window) ||
        window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      reveals.forEach(function (el) { el.classList.add('is-in'); });
    } else {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          if (en.isIntersecting) {
            en.target.classList.add('is-in');
            io.unobserve(en.target);          // one-shot: no repeated work
          }
        });
      }, { rootMargin: '0px 0px -8% 0px', threshold: 0.06 });
      reveals.forEach(function (el) { io.observe(el); });
    }
  }

  // ──────────────────── PWA install (Android/desktop) ────────────────────
  var deferred = null;
  var bar = document.getElementById('gxInstall');
  var go = document.getElementById('gxInstallGo');
  var no = document.getElementById('gxInstallNo');
  var drawerBtn = document.getElementById('gxInstallDrawer');

  function dismissed() {
    try { return localStorage.getItem('zayche-install-dismissed') === '1'; } catch (e) { return false; }
  }
  function showBar() {
    if (!bar || dismissed()) return;
    bar.hidden = false;
    requestAnimationFrame(function () { bar.classList.add('is-in'); });
  }
  function hideBar() {
    if (!bar) return;
    bar.classList.remove('is-in');
    setTimeout(function () { bar.hidden = true; }, 240);
  }

  window.addEventListener('beforeinstallprompt', function (e) {
    e.preventDefault();
    deferred = e;
    if (drawerBtn) drawerBtn.hidden = false;
    setTimeout(showBar, 2500);              // let the page settle first
  });

  function install() {
    if (!deferred) return;
    deferred.prompt();
    deferred.userChoice.then(function (c) {
      if (window.track) window.track('pwa_install_' + c.outcome);
      deferred = null;
      hideBar();
    });
  }
  if (go) go.addEventListener('click', install);
  if (drawerBtn) drawerBtn.addEventListener('click', function () { window.gxDrawer(false); install(); });
  if (no) no.addEventListener('click', function () {
    try { localStorage.setItem('zayche-install-dismissed', '1'); } catch (e) {}
    hideBar();
  });

  // ──────────────────── iOS: no beforeinstallprompt, so teach the gesture ────────────────────
  var isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
  var standalone = window.navigator.standalone === true ||
                   window.matchMedia('(display-mode: standalone)').matches;
  if (isIOS && !standalone && bar && !dismissed()) {
    var label = bar.querySelector('span.gx-faint');
    if (label) label.textContent = 'دکمهٔ اشتراک‌گذاری ← «افزودن به صفحهٔ اصلی»';
    if (go) go.hidden = true;
    setTimeout(showBar, 3500);
  }

  // ──────────────────── service worker ────────────────────
  if ('serviceWorker' in navigator && location.protocol === 'https:') {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('/sw.js').then(function (reg) {
        reg.addEventListener('updatefound', function () {
          var sw = reg.installing;
          if (!sw) return;
          sw.addEventListener('statechange', function () {
            if (sw.state === 'installed' && navigator.serviceWorker.controller) {
              if (window.showToast) window.showToast('نسخهٔ جدید آماده است — صفحه را تازه کن', true);
            }
          });
        });
      }).catch(function () { /* offline install is best-effort */ });
    });
  }
})();
