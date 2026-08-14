/* Chart-platform service worker (PWA — plan §13.9): offline app shell + last chart.
   Cache-first for static assets, network-first for pages. */
const CACHE = "chart-v2";
const SHELL = ["/", "/birth-form", "/learn", "/static/tailwind_inline.css", "/static/sw-register.js"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  // API: network-only (never serve stale chart data)
  if (url.pathname.startsWith("/api/")) return;

  if (url.pathname.startsWith("/static/")) {
    e.respondWith(
      caches.match(e.request).then((hit) => hit || fetch(e.request).then((r) => {
        const copy = r.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy));
        return r;
      }))
    );
    return;
  }
  // pages: network-first with offline fallback to cache
  e.respondWith(
    fetch(e.request)
      .then((r) => {
        if (r.ok) {
          const copy = r.clone();
          caches.open(CACHE).then((c) => c.put(e.request, copy));
        }
        return r;
      })
      .catch(() => caches.match(e.request).then((hit) => hit || caches.match("/")))
  );
});

/* ── Web Push (D1) ─────────────────────────────────────────────────────────── */
self.addEventListener("push", (e) => {
  let data = { title: "زایچه", body: "", url: "/" };
  try {
    if (e.data) data = Object.assign(data, e.data.json());
  } catch (_) { /* non-JSON payloads → defaults */ }
  e.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: "/static/app-icon.png",
      badge: "/static/app-icon.png",
      data: { url: data.url },
      dir: "rtl",
      lang: "fa",
    })
  );
});

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || "/";
  e.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
      for (const c of list) {
        if ("focus" in c) { c.focus(); c.navigate(url); return; }
      }
      return clients.openWindow(url);
    })
  );
});
