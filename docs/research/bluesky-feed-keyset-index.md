# Índice de paginación Jetstream / Bluesky

## Encargo para GPT

Revisar la consulta keyset `ORDER BY time_us DESC, uri DESC` incorporada en la PR #127. El recolector ya crea `idx_posts_time` e `idx_posts_match`, pero SQLite debe ordenar temporalmente los empates con el índice de fecha simple. Mantener ambas protecciones e índices existentes.

### Cambio implementado para revisión

- Añadido exclusivamente `idx_posts_feed ON posts(time_us DESC, uri DESC)` en `bluesky_jetstream_collect.init_db` con `CREATE INDEX IF NOT EXISTS`. No se modifica Jetstream, TLS, WAL, checkpoints, borrados, contratos de acciones ni retención.
- Dos pruebas offline: índices previos conservados e idempotencia al reabrir; contrato de `EXPLAIN QUERY PLAN` y orden exacto sobre 2.000 posts sintéticos con empates.
- Benchmark sintético previo en SQLite 3.46.1: `idx_posts_time` producía `USE TEMP B-TREE FOR LAST TERM OF ORDER BY`; con índice compuesto la consulta usa `COVERING INDEX idx_posts_feed`. Es una mejora del plan, **no se afirma aumento de rendimiento medido en producción**.
- Sin dependencia nueva ni código copiado externo. Se reutiliza el inicializador y el contrato de cursor existentes. La inspiración de cursor keyset está atribuida en la PR #127 al upstream MIT `MarshalX/bluesky-feed-generator@be500ba5be2c2006f0649c8ce8862943ac7966c3`.
- No duplicar #146 (visibilidad AppView), #94/#161 (brechas Jetstream), #136 (importación JSONL) ni las PR transversales de observación/candidatos.

### Pendiente del controlador

Ejecutar `python -m pytest -q tests/test_bluesky_feed_keyset_index.py tests/test_bluesky_jetstream_collect.py tests/test_bluesky_feed_preview.py` **cuando #127 esté integrado**. Probar Windows/Python 3.11 y migración del índice en una copia anonimizada de SQLite de tamaño real, con recolector detenido. Si los costes de indexación superan la mejora de lectura, no integrar. No activar redes ni secreto alguno.

### Norma global

Solo generalizar el **contrato** `(timestamp, identidad remota estable)` y la validación del orden, no el índice físico de Bluesky: cada adaptador de las nueve redes conserva su esquema y base actuales. Esta PR no altera las demás redes.
