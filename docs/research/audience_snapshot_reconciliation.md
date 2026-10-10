# Reconciliación de snapshots completos de audiencias

## Problema

En recopilaciones de audiencias basadas en listas paginadas (como la API de likes/boosts de Bluesky `app.bsky.feed.getLikes`, Mastodon `statuses/:id/favourited_by`, o listas exportadas de X/Instagram), la desaparición de un usuario (un-like, un-repost, o eliminación de comentario) no genera un evento explícito de borrado (`unlike`).

Si el motor de audiencias sólo procesa eventos positivos acumulativamente, las personas que han retirado su interacción siguen figurando en las tablas activas y continúan influyendo en los rankings de afinidad indefinidamente.

Sin embargo, **una captura parcial, un timeout en la paginación o un cursor interrumpido NO debe interpretarse como la ausencia de los usuarios no devueltos en las páginas restantes**. Marcar bajas al terminar una sola página o ante una lectura incompleta destruye falsamente el historial activo de interacciones.

## Alternativas

| Baseline | Candidato OSS | Adaptar patrón | Mantener baseline |
|---|---|---|---|
| Ingesta acumulativa de eventos positivos sin detección de bajas por ausencia en snapshots (`AudienceStore` de #70). | **Apache Iceberg / Delta Lake Staging & Snapshot Isolation** (Apache License 2.0).
**Matrix State Resync Protocols** (Apache License 2.0).
**Debezium CDC Snapshot Staging & Checkpointing** (Apache License 2.0). | Adaptar el patrón de **Staging aislado por `(network, surface, seed, post_key, kind)` + Checkpointing y Commit Atómico de Reconciliación**. | Conservar sólo acumulación de eventos positivos.
*Riesgo:* Métricas de afinidad obsoletas y falsos positivos en ranking de engagement. |

### Justificación de adaptación de patrón (Opción C)
Las bibliotecas de Data Lake (Iceberg/Delta Lake) o CDC (Debezium) son pesadas y agregan dependencias complejas no aptas para una biblioteca ligera offline basada únicamente en `sqlite3` y la biblioteca estándar de Python 3.11. Reimplantar el **patrón de Isolation Staging + Atomic Swap/Reconciliation** directo en SQLite garantiza cero dependencias externas, total transparencia transaccional y compatibilidad 100% entre Windows y Linux.

## Licencias y procedencia

Fuente primaria: https://github.com/apache/iceberg (Apache License 2.0), https://github.com/debezium/debezium (Apache License 2.0), https://github.com/matrix-org/matrix-spec (Apache License 2.0).
Fecha de consulta: 2026-10-10
Licencia SPDX: Apache-2.0 (patrón de diseño adaptado)
Referencia inmutable: N/A (patrón conceptual re-implementado en Python sin copiar código fuente directo)

## Decisión

Adoptar la **Opción C: Patrón reimplementado con Staging y Commit Atómico de Reconciliación**:
1. **Fase de Staging:** Cada barrido paginado de un post/tipo asigna un `snapshot_id` único y guarda las observaciones en la tabla `audience_snapshot_staging`.
2. **Control de completitud (`coverage_complete`):** Un snapshot sólo se considera completo si la paginación llega al final (`next_cursor is None`) sin errores, sin bucles de cursor y sin interrupciones.
3. **Reconciliación Atómica:** Al completar la lectura de todas las páginas de un snapshot completo:
   - Los eventos presentes en el staging se consolidan en `audience_events` (marcando `active = 1`).
   - Los eventos previamente activos en el ámbito `(network, post_key, kind)` que NO figuren en el nuevo snapshot completo se marcan explícitamente como inactivos (`active = 0`).
   - El staging para esa sesión se limpia transaccionalmente.
4. **Preservación de Activos ante Fallo:** Si la captura se interrumpe (timeout, error de red, cursor repetido, reinicio del proceso, o si la fuente indica `coverage_complete = False`), el staging incompleto se descarta/cancela y los eventos anteriormente activos en `audience_events` se preservan intactos.
5. **Independencia de Eventos Únicos:** La reconciliación por snapshot aplica a listas enumerables (`like`, `repost`). Los eventos explícitos con tombstone (como Jetstream en #95) o comentarios/replies directos se gestionan independientemente.

## Pruebas

Se diseñaron e implementaron pruebas en `tests/test_audience_snapshot_reconciliation.py`:
- **Snapshot completo doble:** Verificación de que en la segunda captura completa los elementos ausentes pasan a `active = 0`.
- **Snapshot parcial e interrupción:** Verificación de que una interrupción por error de red o timeout preserva los datos activos anteriores sin aplicar bajas falsas.
- **Página intermedia vacía y bordes:** Verificación del comportamiento cuando una página devuelve 0 elementos pero `coverage_complete = True`.
- **Llegada tardía y replay:** Confirmación de que eventos fuera de orden no resucitan estados inactivos reconciliados.
- **Soporte multired aislado:** Verificación de que dos ejecuciones simultáneas sobre distintas redes no se interfieren en staging.
- **Rollback y limpieza de staging:** Prueba de descarte de snapshots abandonados o fallidos.

Comando de ejecución de tests:
```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p "test_*.py"
```

## Retirada / Rollback

En caso de requerir desactivar la reconciliación por snapshot:
1. La tabla `audience_events` mantiene la columna `active INTEGER`. Para revertir a un modelo puramente acumulativo, se puede ejecutar una actualización masiva `UPDATE audience_events SET active = 1`.
2. La función de ingesta puede ejecutarse en modo `reconcile=False` para ignorar las ausencias en el snapshot y funcionar de modo acumulativo estándar como en #70.
3. Las tablas `audience_snapshots` y `audience_snapshot_staging` pueden descartarse (`DROP TABLE IF EXISTS ...`) sin afectar a las tablas principales `audience_accounts` y `audience_events`.
