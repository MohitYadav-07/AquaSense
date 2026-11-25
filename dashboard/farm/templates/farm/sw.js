{% load static %}const VERSION = "aquasense-v2";
const PRECACHE = ["/offline/", "{% static 'farm/theme.css' %}", "{% static 'farm/dashboard.js' %}", "{% static 'farm/icons/icon-192.png' %}"];
const CDN = ["cdn.jsdelivr.net", "fonts.googleapis.com", "fonts.gstatic.com"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(PRECACHE)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== VERSION).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("message", (e) => { if (e.data === "clear") caches.keys().then((ks) => ks.forEach((k) => caches.delete(k))); });

function staleWhileRevalidate(req) {
  return caches.open(VERSION).then((cache) => cache.match(req).then((hit) => {
    const net = fetch(req).then((res) => { if (res && (res.ok || res.type === "opaque")) cache.put(req, res.clone()); return res; }).catch(() => hit);
    return hit || net;
  }));
}

self.addEventListener("fetch", (e) => {
  const req = e.request, url = new URL(req.url);
  if (req.method !== "GET") return;
  if (req.mode === "navigate" && url.origin === location.origin) {         // pages: network first, then last copy
    e.respondWith(fetch(req).then((res) => {
      if (res.ok && !url.pathname.startsWith("/login")) { const copy = res.clone(); caches.open(VERSION).then((c) => c.put(req, copy)); }
      return res;
    }).catch(() => caches.match(req).then((hit) => hit || caches.match("/offline/"))));
    return;
  }
  if (url.origin === location.origin && url.pathname.startsWith("/static/")) { e.respondWith(staleWhileRevalidate(req)); return; }
  if (url.origin === location.origin && url.pathname.endsWith("series.json")) { e.respondWith(staleWhileRevalidate(req)); return; }
  if (CDN.includes(url.hostname)) { e.respondWith(staleWhileRevalidate(req)); }
});
