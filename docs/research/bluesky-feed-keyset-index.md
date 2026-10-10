# Índice keyset para Jetstream / Bluesky

## Encargo para GPT

Revisar este cambio independiente como complemento de #127. Base `research/public-reuse-parent`, sin merge ni acciones en redes.

## Problema

`bluesky_jetstream_collect.init_db` dispone de `idx_posts_time(time_us DESC)` y `idx_posts_match(match_count DESC, time_us DESC)`, pero el preview de #127 pagina con `ORDER BY time_us DESC, uri DESC`. En SQLite 3.46.1 el plan usando `idx_posts_time` incluye `USE TEMP B-TREE FOR LAST TERM OF ORDER BY`; los empates requieren ordenar. Se trata del plan sintético, no una medición de latencia en producción.

## Alternativas

- Conservar índices: cero coste de escritura adicional, pero se mantiene el paso de ordenación por URI.
- Añadir `(time_us DESC, uri DESC)`: permite recorrer el cursor compuesto con un índice cubriente, a costa de almacenamiento y escrituras extra.
- Materializar un feed o sustituir el recolector: duplicaría caché y lógica, innecesario para esta mejora.

## Licencias y procedencia

Fuente primaria: https://www.sqlite.org/queryplanner.html
Fecha de consulta: 2026-10-10
Licencia SPDX: NOASSERTION
Referencia inmutable: N/A (sin codigo incorporado)

No se incorpora código de terceros; se adapta el `CREATE INDEX IF NOT EXISTS` ya presente en el repositorio oficial. El patrón de cursor está atribuido en #127 a `MarshalX/bluesky-feed-generator@be500ba5be2c2006f0649c8ce8862943ac7966c3` (MIT, Ilya Siamionau), pero no se copia ninguna implementación adicional aquí.

## Decisión

Añadir `idx_posts_feed ON posts(time_us DESC, uri DESC)` junto a los índices existentes. No modificar WAL, conexión TLS, checkpoints, borrados, retención, identidad, ledger ni contratos de acción. El cambio es específico de SQLite/Bluesky: en las otras ocho redes se comparte la norma lógica `(fecha, identificador remoto)`, no una migración física uniforme.

## Pruebas

`tests/test_bluesky_feed_keyset_index.py`: dos tests offline, idempotencia y conservación de índices anteriores, columnas ordenadas `DESC`, `EXPLAIN QUERY PLAN` con 2.000 filas sintéticas y salida ordenada. Se verificó de forma aislada en SQLite 3.46.1 que `idx_posts_feed` evita `TEMP B-TREE`. En un workflow inicial, Linux y Windows Python 3.11 aprobaron el paso `Unit tests without network`; el único fallo fue documental en `Diff privacy gate`, que motivó añadir los encabezados y metadatos presentes. Confirmar el nuevo workflow antes de aprobar.

Claude debe ejecutar los tests del recolector y del preview de #127, así como Windows/Python 3.11 y migración en una copia de SQLite de volumen real. No probar sobre caché activa.

## Retirada

Si la indexación inicial bloquea demasiado tiempo o el tamaño/escrituras empeoran sin ganancia medible, revertir exclusivamente `CREATE INDEX idx_posts_feed` en el inicializador; la eliminación física del índice se decidirá separadamente y siempre con copia de seguridad. Ninguna operación remota depende de esta optimización.
