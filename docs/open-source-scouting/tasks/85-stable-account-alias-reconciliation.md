# Reconciliación de alias y cambios de handle sobre identidades persistentes

Origen: [PR #85](https://github.com/davidpd89/ci-sandbox-tmp/pull/85) usa claves locales `network|handle`, guarda `stable_id` como atributo y protege cambios de ID; falta transición reversible cuando una misma cuenta real cambia de handle.

## Encargo para GPT

Implementar (no investigación aislada) un resolver temporal y auditable para identificadores estables confirmados: Bluesky DID, actor URI de Mastodon, y otros IDs remotos por red solo cuando el adaptador los suministre como verificados. Tomar el HEAD de #85 como interfaz objetivo y analizar `tools/candidate_identity.py`, políticas de reciprocidad, `action_ledger.py` y lectores de CRM, sin duplicar su funcionalidad.

El nuevo mapa debe mantener claves operativas por red y referencias históricas, conservar la procedencia del ID, resolver renombres y alias, dejar una ruta reversible de migración y poder revertir vínculos equivocados sin mezclar estados, comentarios o acciones de dos cuentas. No usar `entity_snapshot_id` de #85 como identificador persistente. Conflictos estables, reciclaje de nombres, DID inconsistente y redes sin ID verificable deben quedar diagnosticados, no asumidos.

Investigar bibliotecas/repos públicos actuales (AT Protocol, WebFinger, temporal graph/identity resolution), licencia y actividad/compatibilidad Windows/Python 3.11, adaptar la mínima solución; documentación con commits fijos, pruebas offline de múltiples renombres, reutilización de handle por tercero, link/split, replay e idempotencia en WEB/API/MOBILE, sin acciones reales. CI Windows/Ubuntu, segunda revisión adversarial, guía de rollback, no merge; Claude valida.
