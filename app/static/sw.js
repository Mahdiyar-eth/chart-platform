/* Chart-platform service worker (PWA — plan §13.9): offline app shell + last chart.
   Cache-first for static assets, network-first for pages. */
const CACHE = "chart-v3";
const SHELL = ["/", "/birth-form", "/learn", "/static/sw-register.js"];

/* Routes that render per-user content. A shared Cache Storage bucket is shared
   across everyone who uses the device, so caching these would hand one user's
   account, chart or chat to the next. Network-only, never stored. */
const PRIVATE = ["/account", "/settings", "/dashboard", "/admin", "/chat",
                 "/chats", "/reports", "/credits", "/orders"];

const isPrivate = (path) =>
  PRIVATE.some((p) => path === p || path.startsWith(p + "/"));

/* Precache each entry independently: cache.addAll() is atomic, so a single
   404 rejects install and the worker never activates at all. One missing
   asset should cost that asset, not the entire PWA. */
self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE)
      .then((c) => Promise.allSettled(SHELL.map((u) => c.add(u))))
      .then(() => self.skipWaiting())
  );
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
  // Private pages: network-only. Never stored, never served from cache.
  if (isPrivate(url.pathname)) return;

  // Public pages: network-first with offline fallback to cache
  e.respondWith(
    fetch(e.request)
      .then((r) => {
        if (r.ok && r.type === "basic") {
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
      icon: "/static/icon-192.png",
      badge: "/static/icon-192.png",
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
