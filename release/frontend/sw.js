const CACHE="datakite-final-20260904";
const ASSETS=["./","./index.html","./style.css","./script.js","./manifest.json","./icon.svg"];
self.addEventListener("install",e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS)).then(()=>self.skipWaiting())));
self.addEventListener("activate",e=>e.waitUntil(self.clients.claim()));
self.addEventListener("fetch",e=>{if(e.request.method!=="GET")return; const u=new URL(e.request.url); if(u.pathname.includes("/api/")||u.pathname.endsWith("/upload")||u.pathname.endsWith("/ask"))return; e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request).then(x=>{const copy=x.clone(); caches.open(CACHE).then(c=>c.put(e.request,copy)); return x}).catch(()=>caches.match("./"))));});
