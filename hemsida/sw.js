// Märkesbörsen som app på hemskärmen. Sidorna hämtas alltid färska när det finns nät,
// och den senaste versionen sparas så att börsen öppnas även utan nät. Siffrorna (från låset) sparas inte här.
const CACHE = "markesborsen-v1";
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", e => {
  const r = e.request, u = new URL(r.url);
  if (r.method !== "GET" || u.origin !== location.origin || !u.pathname.startsWith("/borsen/")) return;
  e.respondWith(fetch(r).then(svar => {
    if (svar.ok && svar.type === "basic") { const kopia = svar.clone(); caches.open(CACHE).then(c => c.put(r, kopia)); }
    return svar;
  }).catch(() => caches.match(r, {ignoreSearch: true}).then(s => s || Response.error())));
});
