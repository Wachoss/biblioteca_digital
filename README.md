# Biblioteca Digital

Catálogo personal de libros: añadir libros por ISBN con datos de
[Open Library](https://openlibrary.org), ver el listado con portadas, buscar por título
o autor y llevar el estado de lectura. Funciona en el ordenador y en el móvil como
aplicación web instalable (PWA).

**Estado:** hito 2 de 5. El catálogo se puede consultar: listado con portadas, ficha de
cada libro, búsqueda por título o autor (sin importar tildes ni mayúsculas) y filtro por
estado de lectura. También hay una API JSON de solo lectura en `/api/books`.

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
uv run alembic upgrade head      # crea o actualiza la base de datos
uv run fastapi dev app/main.py   # http://127.0.0.1:8000
```

Para comprobar el código:

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

Para importar el catálogo antiguo desde Excel, ver [docs/importador.md](docs/importador.md).

## Estructura

```text
app/
├── main.py          # crea la aplicación FastAPI y monta las rutas
├── config.py        # ajustes desde variables de entorno (.env)
├── db.py            # motor y sesión de SQLAlchemy
├── models.py        # Book, Author, ReadingStatus
├── text.py          # clean() y fold(): normalizar y quitar tildes
├── schemas.py       # qué devuelve la API JSON (Pydantic)
├── routers/
│   ├── pages.py     # páginas HTML (Jinja2 + HTMX)
│   └── api.py       # API JSON
├── services/
│   └── catalog.py   # búsqueda, filtro y recuentos: la lógica, sin HTTP
├── templates/       # plantillas Jinja2 (las que empiezan por _ son trozos)
├── static/          # CSS, HTMX y Pico.css; más adelante, el manifest de la PWA
└── importer/        # importación del Excel antiguo (CLI)
migrations/          # migraciones de Alembic
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

## Plan

1. **Esqueleto:** uv, Alembic, Ruff, CI e importador.
2. **Catálogo de solo lectura:** listado con portadas, ficha, búsqueda y filtro por estado. ← aquí
3. **Login del dueño:** cookie de sesión y protección de las rutas de escritura.
4. **Gestión:** alta por ISBN, alta manual, edición y borrado.
5. **PWA:** diseño para móvil, manifest y service worker.

## Licencia

[MIT](LICENSE)
