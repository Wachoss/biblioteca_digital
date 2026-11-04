# Librerías de terceros

Copiadas tal cual desde npm, con la versión en el nombre del fichero para que el
navegador no use una copia vieja de la caché al actualizarlas.

| Fichero | Origen | Licencia |
| --- | --- | --- |
| `htmx-2.0.11.min.js` | [htmx.org 2.0.11](https://www.npmjs.com/package/htmx.org/v/2.0.11), `dist/htmx.min.js` | 0BSD |
| `pico-2.1.1.min.css` | [@picocss/pico 2.1.1](https://www.npmjs.com/package/@picocss/pico/v/2.1.1), `css/pico.min.css` | MIT |
| `barcode-detector-3.2.3-ponyfill.js` | [barcode-detector 3.2.3](https://www.npmjs.com/package/barcode-detector/v/3.2.3), `dist/iife/ponyfill.js` | MIT |
| `zxing-reader-3.1.6.wasm` | [zxing-wasm 3.1.6](https://www.npmjs.com/package/zxing-wasm/v/3.1.6), `dist/reader/zxing_reader.wasm` | MIT (ZXing-C++: Apache-2.0) |

Para actualizar una: descarga la versión nueva, cambia el nombre del fichero y la
referencia en `app/templates/base.html` (o en `book_form.html`, las del escáner).

barcode-detector y zxing-wasm van juntas: cada versión de barcode-detector espera una
versión concreta del `.wasm` (la que dice su `package.json`), y
`tests/test_scanner.py` comprueba que la huella del `.wasm` coincide.
