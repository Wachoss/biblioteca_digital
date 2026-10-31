// Service worker de la Biblioteca Digital. Lo genera app/routers/pwa.py a partir de esta
// plantilla: VERSION cambia sola cuando cambia cualquier fichero estático o plantilla.
//
// Estrategia de caché, según lo que se pida:
// - Páginas (navegación): primero la red y, si no hay, la última copia guardada. Así
//   con conexión siempre se ve el catálogo al día y sin ella, lo último que se visitó.
//   Si de esa página no hay copia, se enseña /sin-conexion.
// - CSS, JS e iconos (/static/): se sirven de la caché al instante y se actualizan por
//   detrás para la próxima vez (stale-while-revalidate).
// - Todo lo demás (API, trozos de HTMX, portadas de Open Library): directo a la red.

const VERSION = {{ version | tojson }};
const STATIC_CACHE = `estaticos-${VERSION}`;
const PAGES_CACHE = `paginas-${VERSION}`;
const OFFLINE_URL = {{ offline_url | tojson }};
const PRECACHE = {{ (precache + [offline_url]) | tojson }};

// Solo se guardan páginas públicas de consulta: el catálogo y las fichas. Nunca los
// formularios del dueño ni la página de entrar.
const CACHEABLE_PAGE = /^\/(libros\/\d+)?$/;

self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(STATIC_CACHE);
      // cache: "reload" salta la caché HTTP del navegador: que no guarde una copia vieja.
      await cache.addAll(PRECACHE.map((url) => new Request(url, { cache: "reload" })));
      // Activarse ya, sin esperar a que se cierren todas las pestañas abiertas. Es seguro
      // porque las páginas siempre se piden primero a la red.
      await self.skipWaiting();
    })(),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const keep = [STATIC_CACHE, PAGES_CACHE];
      for (const name of await caches.keys()) {
        if (!keep.includes(name)) await caches.delete(name);
      }
      await self.clients.claim();
    })(),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return; // portadas y demás: el navegador

  if (request.mode === "navigate") {
    event.respondWith(navigate(event));
  } else if (request.method === "GET" && url.pathname.startsWith("/static/")) {
    event.respondWith(staleWhileRevalidate(event));
  }
  // Sin respondWith, la petición sigue su camino normal a la red.
});

async function navigate(event) {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== "GET") {
    // Entrar o salir cambia lo que se ve en cada página (botones del dueño): las copias
    // guardadas con la sesión anterior ya no valen.
    if (url.pathname === "/entrar" || url.pathname === "/salir") {
      await caches.delete(PAGES_CACHE);
    }
    // Un formulario enviado sin conexión: mejor la página propia que el error del navegador.
    return fetch(request).catch(() => caches.match(OFFLINE_URL));
  }
  try {
    const response = await fetch(request);
    if (response.ok && CACHEABLE_PAGE.test(url.pathname)) {
      const copy = response.clone();
      event.waitUntil(caches.open(PAGES_CACHE).then((cache) => cache.put(request, copy)));
    }
    return response;
  } catch {
    // Sin red. Una búsqueda (/?q=...) que no se guardó cae en el catálogo completo.
    const cache = await caches.open(PAGES_CACHE);
    return (
      (await cache.match(request)) ||
      (await cache.match(url.pathname)) ||
      (await caches.match(OFFLINE_URL))
    );
  }
}

async function staleWhileRevalidate(event) {
  const cache = await caches.open(STATIC_CACHE);
  const cached = await cache.match(event.request);
  const update = fetch(event.request).then((response) => {
    if (response.ok) cache.put(event.request, response.clone());
    return response;
  });
  if (cached) {
    event.waitUntil(update.catch(() => {})); // sin red no pasa nada: ya hay copia
    return cached;
  }
  return update;
}
