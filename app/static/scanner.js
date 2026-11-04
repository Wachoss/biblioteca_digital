// Escáner de ISBN con la cámara, en la página "Añadir libro".
//
// Es una mejora progresiva: sin JavaScript, o si nada de esto funciona, el botón no
// aparece y el ISBN se escribe a mano como siempre. Si funciona, el escáner solo
// rellena el campo y envía el mismo formulario de búsqueda, así que el servidor no
// sabe ni necesita saber si el ISBN se tecleó o se leyó con la cámara.
//
// Dos formas de leer el código, según lo que permita el navegador:
// - En directo: vídeo de la cámara (getUserMedia) y un fotograma analizado cada poco.
//   Solo existe en contexto seguro: HTTPS o localhost.
// - Con una foto: <input type="file" capture> abre la cámara del móvil, y la foto se
//   analiza aquí. No necesita HTTPS, así que sirve en http://192.168.x.x desde el móvil.
//
// Quien lee las barras es la API estándar BarcodeDetector si el navegador la trae
// (Chrome en Android y macOS) y, si no (Firefox, Safari/iOS, Chrome en Windows/Linux),
// la librería barcode-detector, que imita esa misma API con ZXing compilado a
// WebAssembly. Se descarga solo cuando hace falta, la primera vez que se escanea.

(() => {
  const script = document.currentScript;
  const form = document.querySelector("[data-isbn-lookup]");
  const dialog = document.getElementById("escaner");
  if (!form || !dialog) return;

  const input = form.querySelector("input[name=isbn]");
  const help = document.getElementById("lookup-help");
  const scanButton = form.querySelector("[data-scan]");
  const photoInput = form.querySelector("[data-scan-photo]");
  const video = dialog.querySelector("video");
  const message = dialog.querySelector("[data-scan-message]");

  const hasNativeDetector = "BarcodeDetector" in window;
  if (!hasNativeDetector && typeof WebAssembly !== "object") return; // no hay con qué leer
  // En http:// (salvo localhost) navigator.mediaDevices ni siquiera existe.
  const canStream = Boolean(navigator.mediaDevices?.getUserMedia);
  scanButton.hidden = false;

  // --- Leer el código ---------------------------------------------------------------

  let detectorPromise;

  function getDetector() {
    detectorPromise ??= createDetector().catch((error) => {
      detectorPromise = undefined; // que se pueda reintentar (p. ej. al volver la red)
      throw error;
    });
    return detectorPromise;
  }

  async function createDetector() {
    // Solo EAN-13: es el código de barras de los libros. Pedir menos formatos lo hace
    // más rápido y evita leer por error otro código de la contracubierta.
    const formats = ["ean_13"];
    if (hasNativeDetector) {
      try {
        const supported = await window.BarcodeDetector.getSupportedFormats();
        if (supported.includes("ean_13")) return new window.BarcodeDetector({ formats });
      } catch {
        // Algunos navegadores tienen la API pero no el servicio del sistema detrás.
      }
    }
    await loadScript(script.dataset.ponyfill);
    const api = window.BarcodeDetectionAPI;
    // Por defecto la librería descarga el .wasm de un CDN; aquí se sirve desde la
    // propia web, para no depender de terceros y que funcione sin salida a Internet.
    api.prepareZXingModule({
      overrides: {
        locateFile: (path, prefix) => (path.endsWith(".wasm") ? script.dataset.wasm : prefix + path),
      },
    });
    return new api.BarcodeDetector({ formats });
  }

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const tag = document.createElement("script");
      tag.src = src;
      tag.onload = resolve;
      tag.onerror = () => reject(new Error(`No se pudo cargar ${src}`));
      document.head.append(tag);
    });
  }

  // Un ISBN en código de barras es un EAN-13 que empieza por 978 o 979 (el "país"
  // Bookland). Se comprueba el dígito de control otra vez, como en app/isbn.py: un
  // EAN-13 de otra cosa (un precio, una revista) no debe colarse como ISBN.
  function isIsbn13(code) {
    if (!/^97[89]\d{10}$/.test(code)) return false;
    const sum = [...code.slice(0, 12)].reduce((acc, d, i) => acc + Number(d) * (i % 2 ? 3 : 1), 0);
    return (10 - (sum % 10)) % 10 === Number(code[12]);
  }

  function isbnFrom(barcodes) {
    return barcodes.map((barcode) => barcode.rawValue).find(isIsbn13);
  }

  function useIsbn(isbn) {
    input.value = isbn;
    navigator.vibrate?.(80); // un pequeño aviso en el móvil, como en las cajas
    // requestSubmit() y no submit(): lanza el evento "submit", que es el que escucha
    // HTMX, y pasa la validación del formulario.
    form.requestSubmit();
  }

  // --- En directo -------------------------------------------------------------------

  let stream = null;
  let session = 0; // cada apertura del escáner; un bucle de una apertura vieja se para

  async function startLive() {
    const current = ++session;
    setMessage("Abriendo la cámara…");
    dialog.showModal();
    getDetector().catch(() => {}); // que se vaya descargando mientras se abre la cámara
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        // La cámara trasera si la hay; algo de resolución ayuda con las barras finas.
        video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 } },
      });
    } catch (error) {
      if (current !== session) return;
      setMessage(cameraError(error), true);
      return;
    }
    if (current !== session) return stopCamera(); // se cerró mientras pedía permiso
    video.srcObject = stream;
    await video.play().catch(() => {});

    let detector;
    try {
      detector = await getDetector();
    } catch {
      setMessage("No se ha podido cargar el lector de códigos. Comprueba la conexión.", true);
      return;
    }
    setMessage("Apunta al código de barras de la contracubierta.");

    while (current === session) {
      if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
        try {
          const isbn = isbnFrom(await detector.detect(video));
          if (isbn && current === session) {
            dialog.close();
            useIsbn(isbn);
            return;
          }
        } catch (error) {
          console.warn("Error al analizar el fotograma:", error);
        }
      }
      // Unos 6 intentos por segundo: de sobra para un libro quieto, y no calienta el móvil.
      await new Promise((resolve) => setTimeout(resolve, 150));
    }
  }

  function cameraError(error) {
    switch (error.name) {
      case "NotAllowedError":
        return "No hay permiso para usar la cámara. Puedes darlo en los ajustes del navegador, hacer una foto o escribir el ISBN.";
      case "NotFoundError":
      case "OverconstrainedError":
        return "No se ha encontrado ninguna cámara. Puedes elegir una foto o escribir el ISBN.";
      case "NotReadableError":
        return "La cámara está ocupada por otra aplicación.";
      default:
        return "No se ha podido abrir la cámara.";
    }
  }

  function stopCamera() {
    session++;
    stream?.getTracks().forEach((track) => track.stop()); // apaga la luz de la cámara
    stream = null;
    video.srcObject = null;
  }

  function setMessage(text, isError = false) {
    message.textContent = text;
    message.classList.toggle("scan-error", isError);
  }

  // --- Con una foto -----------------------------------------------------------------

  async function scanPhoto(file) {
    setHelp("Buscando el código en la foto…");
    try {
      const detector = await getDetector();
      // createImageBitmap respeta la orientación EXIF de las fotos del móvil.
      const isbn = isbnFrom(await detector.detect(await createImageBitmap(file)));
      if (isbn) {
        setHelp(help.dataset.default);
        useIsbn(isbn);
      } else {
        setHelp("No se ve ningún ISBN en la foto. Prueba más cerca, recto y con buena luz, o escríbelo.", true);
      }
    } catch (error) {
      console.warn("No se pudo analizar la foto:", error);
      setHelp("No se ha podido analizar la foto. Escribe el ISBN a mano.", true);
    }
  }

  function setHelp(text, isError = false) {
    help.textContent = text;
    if (isError) input.setAttribute("aria-invalid", "true");
    else input.removeAttribute("aria-invalid");
  }

  // --- Eventos ----------------------------------------------------------------------

  scanButton.addEventListener("click", () => (canStream ? startLive() : photoInput.click()));
  dialog.querySelector("[data-scan-close]").addEventListener("click", () => dialog.close());
  dialog.querySelector("[data-scan-photo-button]").addEventListener("click", () => {
    dialog.close();
    photoInput.click();
  });
  // "close" llega con Cancelar, con la tecla Esc y con el gesto de atrás de Android.
  dialog.addEventListener("close", stopCamera);
  // Si se cambia de aplicación con la cámara abierta, se apaga.
  document.addEventListener("visibilitychange", () => {
    if (document.hidden && dialog.open) dialog.close();
  });
  photoInput.addEventListener("change", () => {
    const [file] = photoInput.files;
    photoInput.value = ""; // para que elegir la misma foto otra vez vuelva a funcionar
    if (file) scanPhoto(file);
  });
})();
