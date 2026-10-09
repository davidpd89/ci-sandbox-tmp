# Jetstream v2: recuperación de lagunas de replay y cambio de instancia

## Encargo para GPT

Implementa una recuperación demostrable de Bluesky Jetstream v2 cuando la escucha
quede fuera de la ventana de replay (`CursorTooOld`, HTTP 400) o cuando la instancia
detrás de un hostname deje de admitir el cursor persistido. No confundir
reconexión inclusiva normal con una brecha real. Trabajo derivado de la segunda
auditoría de la [PR #11](https://github.com/davidpd89/ci-sandbox-tmp/pull/11).

## Situación actual

La PR #11 hace idempotente el consumidor de commit v2, persiste checkpoint
transaccional e impide el cambio explícito de host con seq ajeno. Un 400 conserva
correctamente el checkpoint y falla, pero NO restaura una brecha de >36 horas.
El `prepare --deep` necesita saber si los datos son completos, parciales o si
una recuperación está pendiente. No debe declarar un scan íntegro tras perder
un tramo de eventos. La implementación oficial privada no recibe cambios aquí.

## Alcance exigido

1. Leer HEAD, diff y estudio de #11; comprobar la rama privada
   `integracion/crecimiento-2026-10`, PROTOCOL y PR abiertas para evitar colisiones.
2. Comparar SDK Python `MarshalX/atproto`, cliente Go oficial Jetstream,
   `@bsky/jetstream` y continuidad local: licencias, mantenimiento, dependencias,
   Python 3.11/Windows, perfil de recursos y adaptabilidad. No copiar sin licencia.
3. Diseñar `planSnapshot` paginado + descarga de segmentos o una alternativa
   técnicamente equivalente, con transición exacta al live (cursor inclusivo,
   deduplicación y detección de rebobinado), SIN omitir deletes/updates.
4. Estado SQLite explícito para `last_seq`, origen del stream, rango verificado,
   `gap_detected`, `recovery_pending` y `complete_through`. Persistencia
   monotónica y rollback ante excepción o corte. Mantenimiento de interfaz de
   `read_recent_matches` y `read_active_authors`.
5. Dejar una ruta reversible de migración de caches pre-#11 sin origen, sin
   inferir que un seq v1, time_us y v2 son intercambiables.
6. Simular HTTP 400 `CursorTooOld`, salto de servidor detrás del mismo host,
   particiones vacías, snapshot paginado, cambio de cursor a mitad de página,
   delete tras create y caída entre snapshot y live. Pruebas con red bloqueada,
   sin cuenta real, Windows y Ubuntu, Python 3.11. Fixtures sintéticos.
7. Medir registros recuperados, latencia y coste sobre fixtures locales,
   declarando límites reales y métricas de completitud; no inventar cifras.
8. Documentar fuentes/commits estables, decisión, límites, rollback, evidencia
   de CI y segunda revisión adversarial. Ningún publish/follow/reply real.
9. Coordinar con #26 (SQLite/ledger), #41 (cursores/parser) y #11
   (collector live). No expandir cambios a sus ramas ni hacer merge.

## Referencias verificadas 2026-10-09

- Spec y semántica archive+live:
  https://github.com/bluesky-social/jetstream/blob/f42df08ba0ca9e4287020139aefbcfe24506d1ef/docs/README.md
- Cliente Go (licencia MIT OR Apache-2.0):
  https://github.com/bluesky-social/jetstream/blob/f42df08ba0ca9e4287020139aefbcfe24506d1ef/client.go
- Cliente TS `@bsky/jetstream` (incompatible directamente con runtime Python):
  https://github.com/bluesky-social/bsky/blob/bc6737a4b52dd2458c7aecbc296ec660e068af89/packages/jetstream/README.md
- SDK Python MIT:
  https://github.com/MarshalX/atproto/tree/4c17895c97f6d42ecb9c41dc5c2fb450ab9c6ac8

## Aceptación

Entregar código funcional, tests, documento `docs/research/` y segundo informe
de revisión **en esta misma PR**; no declarar éxito si un tramo queda sin
verificar o el canario supervisado no se ha ejecutado. No credenciales ni
acciones sociales; si hace falta servidor vivo, indicar a Claude el test manual
exacto y qué no se pudo ejecutar. No fusionar.

## Independencia

#11 mantiene el stream live y debe ser integrable sin archive/backfill. Esta PR
implementa el módulo de recuperación de lagunas y la reconciliación de estado,
capacidad distinta que no se puede completar con una simple reconexión.
