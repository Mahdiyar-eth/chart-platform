// PWA registration (plan §13.9) — served at root scope so it controls the whole site.
if ("serviceWorker" in navigator && location.protocol.startsWith("https")) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  });
}
