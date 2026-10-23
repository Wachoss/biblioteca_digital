# Importador del Excel de libros

Importa el catálogo antiguo (`Biblioteca Digital.xlsx`) a la base de datos de la
biblioteca. Es una herramienta de línea de comandos dentro del paquete `app/` que usa los
mismos modelos que la aplicación.

## Uso

```bash
# Fases 1 y 2: normaliza el Excel y busca cada libro en Open Library (~2 min, 1 petición/s)
uv run python -m app.importer prepare "Biblioteca Digital.xlsx"

# Fase 3: abre review.csv en LibreOffice (UTF-8, separado por comas) y revísalo
# Fase 4: aplica las migraciones y carga en la base de datos. Se puede repetir: actualiza, no duplica
uv run python -m app.importer load review.csv
```

## Cómo revisar `review.csv`

Las filas vienen ordenadas de peor a mejor puntuación, así que las dudosas están arriba.
Solo se cargan las columnas en MAYÚSCULAS; las de minúsculas (`puntuacion`, `excel_*`,
`ol_*`) son referencia para decidir.

- `ACEPTAR`: `si` usa el ISBN, la portada, el año y la clave de Open Library; `no` los
  ignora. Se pone `si` solo cuando la puntuación es 85 o más.
- `TITULO` y `AUTORES`: edítalos libremente (varios autores separados por ` / `). El
  título siempre sale del Excel porque Open Library suele dar el título original
  ("Nineteen Eighty-Four"). Si se acepta la coincidencia, cada autor del Excel toma la
  grafía de Open Library ("Aldoux Husley" pasa a "Aldous Huxley"), pero no se añaden
  traductores ni ilustradores, porque Open Library no los distingue de los autores.
- `ISBN13`: solo se rellena con ediciones españolas (978-84, 979-13). Open Library
  mezcla los ISBN de todas las ediciones, y uno chino o alemán es peor que ninguno.
- `ESTADO`: `pendiente`, `leyendo`, `leido`, `abandonado` o `consulta`.
- Si cambias una fila a `si` a mano, copia también los autores de `ol_autores`.

## Decisiones de diseño

| Decisión | Alternativa | Por qué |
| --- | --- | --- |
| `id` entero como clave, `isbn13` único y opcional | ISBN como clave primaria | Muchos libros (cómics, ediciones antiguas) no tienen ISBN localizable. |
| Autores en tabla aparte, relación N:M | Texto libre en el libro | Varios autores por libro, búsqueda y estadísticas por autor. |
| Cinco estados (`consulta`, `abandonado`) | Tres estados y un booleano `is_reference` | "Para consultar" y "No terminado" ya existían en tus datos. |
| Fases separadas con CSV intermedio | Volcado directo con `pandas.to_sql` | Revisión manual, reejecutable y testeable; sin pandas. |
| Carga idempotente por `import_ref` | Borrar e insertar | Reimportar no duplica ni pierde cambios de ids. |
| Caché en disco de Open Library | Pedir siempre | Repetir `prepare` es instantáneo y no carga la API. |
| Puntuación `rapidfuzz` (70 % título, 30 % autor) | Coincidencia exacta | Tolera erratas; mezcla `token_set` y `token_sort` para que "1984" no case al 100 % con "1984 (adaptation)". |

`load` aplica las migraciones de Alembic antes de cargar, así que funciona tanto con una
base de datos nueva como con una existente.
