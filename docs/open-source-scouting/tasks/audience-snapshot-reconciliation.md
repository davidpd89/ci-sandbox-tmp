# Reconciliación de snapshots completos de audiencias (PR derivada de #70)

## Origen y evidencia
Revisión adversarial de [#70](https://github.com/davidpd89/ci-sandbox-tmp/pull/70): el motor `audience_discovery.AudienceStore` conserva eventos positivos y tombstones si el colector los emite. Sin embargo, APIs de rostros de likes/boosts (p. ej. `app.bsky.feed.getLikes`, `statuses/:id/favourited_by`) proporcionan un *snapshot* paginado, no siempre una notificación de `unlike`. Una persona desaparecida de una lista completa podría seguir figurando indefinidamente en ranking. Esto produce afinidad obsoleta y métricas falsas. **No se debe marcar borrada al terminar una sola página**.

## Encargo de implementación
1. Leer #70, `tools/audience_discovery.py` (o estado integrado en rama real), el informe `docs/research/likers_commenters_audience.md`, y `docs/open-source-scouting/PROTOCOL.md`. Consultar el oficial privado en lectura si es necesario.
2. Investigar implementaciones públicas actuales con commits/licencias/soporte Windows 3.11, compararlas con el núcleo de #70 y conservar su contrato salvo motivo demostrado.
3. Añadir generaciones/snapshot_id y staging aislado por (red, superficie, semilla, post, tipo). Confirmar bajas solo tras paginar **todas** las páginas y validar completitud; ante timeout, cursor cíclico, fallo de página, cambio de snapshot en origen o reinicio, preservar activos anteriores.
4. Mantener idempotencia, concurrencia de WEB/API/MOBILE, actor estable vs handle provisional, timestamp de evento vs observación y replay de páginas duplicadas. Nunca interpretar contador agregado como lista de likers. Separar reconciliación de snapshots de los `delete` explícitos Jetstream (#95).
5. Probar offline en SQLite real con dos snapshots completos, uno parcial interrumpido, pagina vacía intermedia, late/replay, cambios de handle, 2 redes simultáneas, fallback de fuente sin snapshot completo y rollback. Medir antes/después y revisar adversarialmente.
6. Entregar código + tests Windows y Ubuntu Python 3.11 + `docs/research` con campos exigidos por validador + resultados verificables GitHub Actions. Sin credenciales, cuentas, operaciones en redes ni merge.

## Independencia
#70 normaliza **eventos positivos** y snapshots leídos y mantiene los cursores; esta PR cubre exclusivamente **reconciliación de ausencias** demostradas después de un barrido completo. #95 trata el listener de eventos Jetstream, no listas enumeradas. No cambiar ni fusionar otras ramas. Integrar tras #70 para evitar copiar el núcleo. Base `research/public-reuse-parent`.
