# Biblioteca Digital

Catálogo personal de libros: añadir libros por ISBN con datos de
[Open Library](https://openlibrary.org), ver el listado con portadas, buscar por título
o autor y llevar el estado de lectura. Funciona en el ordenador y en el móvil como
aplicación web instalable (PWA).

**Estado:** v1 terminada (hito 5 de 5). El catálogo se puede consultar sin cuenta: listado con portadas,
ficha de cada libro, búsqueda por título o autor (sin importar tildes ni mayúsculas) y
filtro por estado de lectura. También hay una API JSON de solo lectura en `/api/books`.
El dueño inicia sesión en `/entrar` y puede añadir libros por ISBN (los datos llegan de
Open Library y se revisan antes de guardar) o a mano, editarlos y borrarlos. Se puede
instalar en el móvil y en el ordenador como una app, y sin conexión enseña el catálogo y
las fichas que ya se hayan abierto antes.

## Tecnologías

- **Backend:** Python 3.12+, [FastAPI](https://fastapi.tiangolo.com),
  [SQLAlchemy 2](https://www.sqlalchemy.org) y [Alembic](https://alembic.sqlalchemy.org)
  para las migraciones.
- **Base de datos:** SQLite. Gracias a SQLAlchemy, pasar a PostgreSQL es cambiar la URL.
- **Interfaz:** plantillas [Jinja2](https://jinja.palletsprojects.com) generadas en el
  servidor y [HTMX](https://htmx.org) para las partes dinámicas.
- **Herramientas:** [uv](https://docs.astral.sh/uv/) para dependencias,
  [Ruff](https://docs.astral.sh/ruff/) para estilo, pytest y GitHub Actions.

## Puesta en marcha

Hace falta [uv](https://docs.astral.sh/uv/getting-started/installation/)
(en Fedora: `sudo dnf install uv`).

```bash
uv sync                          # crea .venv e instala las versiones exactas de uv.lock
cp .env.example .env             # ajustes locales
uv run python -m app.auth        # elige tu contraseña y pega en .env lo que imprime
uv run alembic upgrade head      # crea o actualiza la base de datos
uv run uvicorn app.main:app --reload   # http://127.0.0.1:8000
```

Para comprobar el código:

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

Para importar el catálogo antiguo desde Excel, ver [docs/importador.md](docs/importador.md).

## Instalarla como app (PWA)

Un service worker solo funciona en un contexto seguro: HTTPS, o `localhost` en el propio
ordenador. En `http://127.0.0.1:8000` Chrome y Edge ya ofrecen "Instalar" en la barra de
direcciones, y en las herramientas de desarrollo (Application → Service workers) se puede
marcar "Offline" para probar el modo sin conexión.

En el móvil, abrir `http://192.168.x.x:8000` desde la wifi de casa **no** sirve: no es
HTTPS y el navegador no registra el service worker. Para probarlo antes de desplegar:

- **Android:** conecta el móvil por USB con la depuración USB activada y ejecuta
  `adb reverse tcp:8000 tcp:8000` (adb se instala con `sudo dnf install android-tools`
  en Fedora o `winget install Google.PlatformTools` en Windows); en el móvil, `http://localhost:8000` cuenta como
  seguro. Luego, menú de Chrome → "Instalar aplicación".
- **iPhone:** hace falta HTTPS de verdad (desplegada, o con un túnel como
  `tailscale serve` o `cloudflared`). En Safari: Compartir → "Añadir a pantalla de inicio".

Los iconos se generan con `uv run --with pillow python scripts/generar_iconos.py`.

## Estructura

```text
app/
├── main.py          # crea la aplicación FastAPI y monta las rutas
├── config.py        # ajustes desde variables de entorno (.env)
├── auth.py          # contraseña del dueño, sesión y límite de intentos
├── db.py            # motor y sesión de SQLAlchemy
├── models.py        # Book, Author, ReadingStatus
├── text.py          # clean() y fold(): normalizar y quitar tildes
├── isbn.py          # validar ISBN (dígito de control) y pasar de 10 a 13 cifras
├── schemas.py       # qué devuelve la API JSON (Pydantic)
├── routers/
│   ├── pages.py     # páginas HTML (Jinja2 + HTMX)
│   ├── auth.py      # /entrar y /salir
│   ├── manage.py    # añadir, editar y borrar (solo el dueño)
│   ├── pwa.py       # manifest, service worker, página sin conexión y favicon
│   └── api.py       # API JSON
├── services/
│   ├── catalog.py   # búsqueda, filtro y recuentos: la lógica, sin HTTP
│   ├── books.py     # validar el formulario, crear, editar y borrar
│   └── openlibrary.py  # buscar un libro por ISBN en Open Library
├── templates/       # plantillas Jinja2 (las que empiezan por _ son trozos) y sw.js
├── static/          # CSS, app.js, iconos, HTMX y Pico.css
└── importer/        # importación del Excel antiguo (CLI)
migrations/          # migraciones de Alembic
scripts/             # generar_iconos.py: regenera los iconos de la PWA
tests/
```

Las rutas solo traducen HTTP; la lógica está en `app/services/` para que la usen igual
las páginas, la API JSON y los tests. La documentación interactiva de la API está en
`/docs`.

## Decisiones de diseño

| Decisión | Alternativa | Por qué |
| --- | --- | --- |
| Jinja2 + HTMX | API JSON + SPA (React, Vue, Svelte) | Un solo lenguaje y un solo despliegue; con un único usuario la SPA añade complejidad sin beneficio. Las rutas `/api` siguen devolviendo JSON. |
| uv con `uv.lock` | `pip` + `requirements.txt` | El fichero de bloqueo garantiza las mismas versiones en local y en CI. |
| Alembic desde el principio | `Base.metadata.create_all` | `create_all` no modifica tablas existentes; un test comprueba que las migraciones coinciden con los modelos. |
| Rutas y sesiones síncronas | `async` con `AsyncSession` | FastAPI ejecuta las rutas síncronas en un pool de hilos; con un usuario no hay diferencia y el código es más simple. |
| `id` entero, `isbn13` único y opcional | ISBN como clave primaria | Muchos libros (cómics, ediciones antiguas) no tienen ISBN localizable. |
| Autores en tabla aparte, relación N:M | Texto libre en el libro | Varios autores por libro, búsqueda y estadísticas por autor. |
| Columna `search_text` (sin tildes) + `LIKE` | `LIKE` sobre el título; SQLite FTS5 | `LIKE` no ignora tildes; FTS5 es una mejora posible, pero con cientos de libros no compensa. La columna se recalcula sola al guardar (evento `before_flush`). |
| Misma URL para la página entera y el trozo de HTMX | Rutas aparte para los fragmentos | La URL de cada búsqueda se puede compartir, el botón Atrás funciona y sin JavaScript todo sigue funcionando. |
| HTMX y Pico.css copiados en `static/vendor/` | Cargarlos desde un CDN | Sin dependencia de terceros en cada visita, y la PWA podrá guardarlos para funcionar sin conexión. |
| Sesión en cookie firmada (`SessionMiddleware`) | JWT; sesiones guardadas en la base de datos | Para una web con formularios la cookie es lo natural: el navegador la envía sola y `HttpOnly` la oculta a JavaScript. Un JWT sirve para APIs consumidas por otros clientes y no se puede revocar sin una lista negra. |
| Contraseña como hash Argon2 en `.env`, sin tabla de usuarios | Tabla `users`; contraseña en claro en `.env` | Solo hay un dueño. Argon2 es lento a propósito y resiste ataques con GPU; si alguien lee el `.env`, no obtiene la contraseña. |
| La cookie guarda una huella del hash | Guardar solo `owner=True` | Al cambiar la contraseña, todas las sesiones abiertas dejan de valer (útil si pierdes el móvil). |
| `SameSite=Lax` contra CSRF | Tokens CSRF en cada formulario | Con un solo usuario y navegadores actuales basta; otra web no puede enviar un POST con tu cookie. |
| Máximo 5 fallos por IP cada 15 minutos, en memoria | Sin límite; guardarlo en la base de datos | Frena la fuerza bruta sin tablas nuevas. Se reinicia con el servidor, aceptable con un solo proceso. |
| Buscar por ISBN rellena el formulario; guardar es otro paso | Guardar directamente lo que diga Open Library | Open Library a veces trae el título en otro idioma o mezcla traductores con autores; así se revisa antes. Si no conoce el ISBN o no responde, el mismo formulario sirve para darlo de alta a mano. |
| ISBN validado con su dígito de control y guardado siempre como ISBN-13 | Guardarlo tal cual se escribe | Detecta erratas sin gastar una petición, y el mismo libro no puede entrar dos veces con el ISBN-10 y el ISBN-13. |
| Escrituras con formularios HTML y POST, protegidas en el router entero | `PUT`/`DELETE` desde HTMX o una API JSON de escritura | Funciona sin JavaScript, SameSite=Lax ya protege los POST contra CSRF, y una ruta nueva no puede quedarse sin protección por olvido. |
| Confirmar el borrado con un `<details>` | `confirm()` de JavaScript o una página de confirmación | No necesita JavaScript ni una página más, y evita borrar de un toque sin querer en el móvil. |
| Service worker escrito a mano | Workbox u otra librería | Son unas 100 líneas que se pueden leer enteras; Workbox compensa cuando hay muchas rutas y estrategias distintas. |
| Páginas: primero la red y, sin conexión, la última copia guardada | Primero la caché (más rápido) | El catálogo cambia al añadir libros; así nunca se ve una copia vieja si hay conexión. |
| Sin conexión solo se ve lo ya visitado: catálogo y fichas | Descargar todo el catálogo al instalar | Con cientos de libros sería mucho tráfico para algo que se usa poco sin red. Los formularios del dueño y `/entrar` nunca se guardan. |
| Las portadas no pasan por el service worker | Guardarlas también | Vienen de otro dominio sin CORS: se guardarían como respuestas opacas, que cuentan varios MB cada una en la cuota. Sin red se ve el título, el plan B que ya había. |
| La versión del service worker es una huella de los estáticos y las plantillas | Subir un número a mano en cada cambio | No se puede olvidar: si cambia el CSS o una plantilla, cambia `sw.js` y se descartan las cachés viejas. |
| `display: standalone` | `minimal-ui` o `browser` | Se abre como una app, sin barra de direcciones; los enlaces "Volver" ya permiten moverse sin el botón Atrás. |

## Plan

1. **Esqueleto:** uv, Alembic, Ruff, CI e importador.
2. **Catálogo de solo lectura:** listado con portadas, ficha, búsqueda y filtro por estado.
3. **Login del dueño:** cookie de sesión y protección de las rutas de escritura.
4. **Gestión:** alta por ISBN, alta manual, edición y borrado.
5. **PWA:** manifest, iconos, service worker y modo sin conexión. ← v1 terminada

## Licencia

[MIT](LICENSE)
