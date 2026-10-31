// Registro del service worker y aviso de "sin conexión".

// Solo en navegadores que lo admiten y en contexto seguro (HTTPS o localhost); en otro
// caso la web funciona igual, solo que sin modo sin conexión ni instalación.
if ("serviceWorker" in navigator) {
  // Tras la carga, para no competir con la propia página por la red.
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch((error) => {
      console.warn("No se pudo registrar el service worker:", error);
    });
  });
}

// La clase .sin-conexion en <html> muestra el aviso (ver style.css).
function setOffline(offline) {
  document.documentElement.classList.toggle("sin-conexion", offline);
}

setOffline(!navigator.onLine);
window.addEventListener("online", () => setOffline(false));
window.addEventListener("offline", () => setOffline(true));
// navigator.onLine puede decir "conectado" con una wifi sin salida a Internet; si una
// búsqueda de HTMX falla por la red, eso sí es una prueba de que no hay conexión.
document.addEventListener("htmx:sendError", () => setOffline(true));
document.addEventListener("htmx:afterRequest", (event) => {
  if (event.detail.successful) setOffline(false);
});
