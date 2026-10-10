# PR #110 — identidad remota estable y alias temporales (10/10/2026)

**Alcance:** solo análisis offline, sin acciones sociales ni modificación de estados reales. Rama base `research/public-reuse-parent`. Dependencia: [#85](https://github.com/davidpd89/ci-sandbox-tmp/pull/85), HEAD revisado `053de9b3f5d4dc6483d4198b980794c2cfdfdb85`.

## Brecha real y contraste con el repositorio oficial

La #85 contiene `tools/identity_profiles.py`, `tools/identity_graph.py`, `tools/cross_network_identity.py` y `tools/identity_crm_adapters.py`. Usa `network|handle` para operación, `stable_id` como atributo no indexado temporalmente y `entity_snapshot_id` calculado de los miembros. **El snapshot NO es un ID estable**. No hay un mapa histórico auditable para renombres y reciclaje de handles.

En el repositorio oficial privado `davidpd89/rrss-davidporto-CODE@integracion/crecimiento-2026-10`, consultado únicamente en lectura, el blob de `tools/candidate_identity.py` es `56e3ec1e7999cb972c5b9df89ee7a0f6ef3219f8`: admite Bluesky `handle` y Mastodon `acct`; `resolve_stable_account` conserva DID auxiliar o `account_id + instance`, pero **no aporta por sí mismo prueba DID bidireccional ni URI persistente de actor Mastodon**. `tools/relationship_policy.py`, blob `ca294952069ebab608de677c93a87101b4033b95`, registra relaciones por handle. `action_ledger.py` reserva por objetivos operativos. Ninguno se modifica, ni se transportan datos privados.

## Software público examinado y decisión de reutilización

| Proyecto / commit inmutable | SPDX y mantenimiento actual | Encaje Python 3.11/Windows | Decisión |
| --- | --- | --- | --- |
| [MarshalX/atproto@4c17895c](https://github.com/MarshalX/atproto/commit/4c17895c97f6d42ecb9c41dc5c2fb450ab9c6ac8) | MIT, `LICENSE` comprobada; commit 02/10/2026, PyPI 0.0.72 (10/09/2026) | Python >=3.9,<3.15; OS independent | Resolver externo DID/handle para futuros productores; **no** cargar SDK para hacer replay |
| [halcy/Mastodon.py@336a62d](https://github.com/halcy/Mastodon.py/commit/336a62d850a28f6f066a26b83506ed70f0f4b906) | MIT, `LICENSE` comprobada; commit 07/10/2026 | SDK Python multiplataforma; obtención URI de actor se validará con fuente | Útil en adaptador nativo, no aporta historia de propiedad |
| [bluesky-social/atproto @atproto/identity@647cb41](https://github.com/bluesky-social/atproto/commit/647cb412576f1ba92c63aa00c71743cb400bdf8d) | MIT OR Apache-2.0; actividad 2026 | **TypeScript**, añade entorno Node | Se adopta el patrón bidireccional handle→DID y DID document→handle; no se copia código |
| [PR #85](https://github.com/davidpd89/ci-sandbox-tmp/pull/85) | Código del proyecto | Python stdlib, Windows/Linux | Reutilizar claves y grafo existente, no duplicar CRM ni clustering |

Elección: `tools/stable_account_aliases.py`, implementación original con Python estándar, sin dependencia nueva ni copia de código ajeno. Las fuentes públicas anteriores ofrecen verificación/obtención, no reconciliación histórica de evidencias; atribución y commits quedan fijados. Complejidad actual de `resolve`: O(N) en evidencias almacenadas; optimizable si crece el histórico.

## Contrato de datos / interoperabilidad

`AliasTimeline.observe(...)` recibe `network` (nueve redes), `handle`, `stable_id`, `observed_at` ISO con zona, `queue` WEB/API/MOBILE, `source`, `proof`, `verification`, `evidence_id`. Valida formato, ámbitos, procedencia e idempotencia; no convierte nombre, web, URL de post ni `entity_snapshot_id` a identidad persistente.

- Bluesky: DID (`did:plc` o `did:web`) marcado por fuente como `did_bidirectional`. **El módulo no consulta DNS/DID**: la fuente debe acreditar las dos direcciones antes de marcarlo.
- Mastodon: URI HTTPS de actor previamente confirmada (`actor_uri_confirmed`), no ID de cuenta local de una instancia.
- Otras siete redes: `provider_account_id` solo si un adaptador ha verificado ID remoto persistente; sin evidencia, resultado `unknown`. La presencia del nombre o handle **nunca equivale** a verificación.

`resolve(network,handle,as_of)` distingue `verified_at_observation`, `inferred_interval` (inferencia, no prueba), `superseded_alias`, `unknown`, `conflict_handle_recycled_same_time` y `conflict_stable_multiple_handles`. Otro usuario puede recibir un handle previamente abandonado sin asumir interacciones del antiguo dueño. `link` compara dos pruebas activas del mismo ID estable; si cambió el ID, no une, y si dos handles simultáneos pretenden el mismo ID tampoco selecciona uno arbitrariamente.

`revoke(evidence_id,reason)` desactiva un vínculo sin borrar su evidencia; `restore` permite revertir, ambos registrados en `actions`; `history` muestra también evidencia revocada. `to_document/from_document` reproduce JSON v1 offline. No proporciona garantía de integridad criptográfica contra alteración de todos los documentos por un tercero.

`project_events` genera `linked` y `unresolved`, sin editar ni trasladar registros de origen. Solo atribuye un evento si contiene `evidence_id` verificable para ese mismo handle y el ID sigue siendo consistente a la fecha del evento. Dedupe de WEB/API/MOBILE por `(network,kind,event_id)`; versiones contradictorias se ponen en `unresolved`. Una ausencia de identidad no se convierte en fracaso ni en cero acciones. No se reescriben `action_ledger`, `relationship_policy` ni registros CRM.

## Ejemplo reproducible

```python
from stable_account_aliases import AliasTimeline
timeline = AliasTimeline()
timeline.observe(
    evidence_id="synthetic-1", network="bluesky", handle="writer.bsky.social",
    stable_id="did:plc:abcdefghijklmnopqrstuvwx",
    observed_at="2026-10-01T09:00:00Z", queue="API",
    source="fixture", proof="did_document_two_way_match",
    verification="did_bidirectional",
)
assert timeline.resolve("bluesky", "writer.bsky.social",
                        "2026-10-01T09:00:00Z")["status"] == "verified_at_observation"
```

## Pruebas, adversarial y rollback

Pruebas locales de diseño en Linux/Python: **24 casos** (incluidos casos adicionales previos a subir una selección equivalente). Suite publicada: `python -m unittest discover -s tests -p test_stable_account_aliases.py -v`; CI `validate-stable-aliases.yml` en Windows/Ubuntu 3.11. Todos usan solo datos sintéticos y librería estándar.

**Segunda revisión adversarial y correcciones**: (1) cambiar dedupe de `network,event_id` a `network,kind,event_id` para no unir tipos de eventos con el mismo ID; (2) no vincular identidades simultáneas por sort lexicográfico; (3) no atribuir eventos sin prueba ni anteriores a ella; (4) no tratar `account_id` de Mastodon como actor URI; (5) conservar conflictos y pruebas revocadas; (6) evitar `stable_id` de #85 si la fuente no lo ha confirmado bidireccionalmente. Limitaciones: intervalos entre snapshots no prueban posesión continua, atribución estricta requiere observaciones nativas, y `proof` es una afirmación del productor, no validación remota del módulo.

**Integración**: después de aprobar #85, usar `AliasTimeline(key_builder=identity_profiles.account_key)` y conectar solo fuentes con pruebas de ID verificadas; en históricos sin fecha/ID remoto, mantener `unresolved`. PR #109 investiga enlaces de perfil, #108 evidencias de relaciones, no se duplican aquí. Windows vivo, Edge, Android y canario supervisado **pendientes para Claude**; ningún resultado simulado se presenta como canario real.

**Rollback**: desactivar el consumidor de `AliasTimeline`, retirar módulo/pruebas/workflow aditivos y conservar, si se desea, JSON v1 para auditoría. Para vínculo equivocado, `revoke`, recalcular vistas desde eventos originales, revisar `unresolved`; `restore` deshace. No migrar ni sobreescribir cuentas/CSV/acciones históricas.
