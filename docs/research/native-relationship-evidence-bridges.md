# CI 108 — Puentes nativos de evidencia relacional

Investigación: 10/10/2026. Rama: `research/relationship-native-evidence-bridges`.
Dependencia de integración estricta: **PR #84 abierta**, revisar e integrar antes.
No merge, no llamadas a cuentas, no datos de producción.

## Problema

Los resultados nativos no acreditan automáticamente una confirmación estable.

## Alternativas

Se compararon eventsourcing, sqlite-utils, python-jsonschema y stdlib; ver tabla detallada al final.

## Licencias y procedencia

Fuente primaria: https://github.com/pyeventsourcing/eventsourcing
Fecha de consulta: 2026-10-10
Licencia SPDX: BSD-3-Clause
Referencia inmutable: https://github.com/pyeventsourcing/eventsourcing/tree/575d42c10a821828639b90178ed56703abe9c9f1

No se copió código de terceros. Se mantiene el almacén de #84.

## Decisión

Normalización mínima y conservadora, sin dependencias externas y sin modificar productores.

## Pruebas

Suite sintética y de integración contra #84; ejecuciones comprobadas por HEAD en GitHub Actions.

## Retirada

Eliminar el puente sin alterar ActionLedger, CSV ni la base secundaria de #84.

## Antes / después

**Antes:** el ledger #84 acepta eventos confirmados y snapshots de nueve
redes, pero los ejecutores producen `resultado` con semánticas heterogéneas.
Un `confirmado` sin ACK trazable se puede importar como éxito si el
consumidor no conserva su evidencia. Algunos snapshots son solo agregados.

**Después:** `tools/native_relationship_evidence_bridge.py` ofrece
`bridge_results`, `bridge_snapshot`, `Batch` y `availability`. Se
normalizan `handle/cuenta`, `url/permalink/post_url`, `kind`,
`resultado`, `_intent_id/record_id` y tiempos explícitos. Un registro
sin ID estable, identidad, resultado o tiempo no genera evento: incrementa
`unknown` con motivo sin incluir valores sensibles. Los éxitos necesitan
un ACK suministrado por el productor con ID y coincidencia de acción,
destino y base `ui_state/api_response/mobile_observed`. Sin él se crea
`unverified`, que no suma éxitos. `saltado_ya_*` es `observed`,
`pendiente_*` es `uncertain`, no ejecución confirmada. El consumidor
puede aportar `reservation_id` para trazar
`reserve:<id>|ack:<id>`. El `source_id` es un JSON estructurado
de exportación inmutable, fila y fase; un ACK posterior es hecho distinto,
no reescritura de un hecho previo. Replay y conflictos los protege
`RelationshipLedger.append_many` de #84.

### Matriz de procedencia contrastada en el repo privado

Inventario solo lectura: `davidpd89/rrss-davidporto-CODE`,
rama `integracion/crecimiento-2026-10`, árbol
[`5449513`](https://github.com/davidpd89/rrss-davidporto-CODE/commit/5449513d9b545d0a6a72abf066ab6a779bfdad71).

| Red | WEB | API | MOBILE | Evidencia de entrada / límite |
|---|---|---|---|---|
| X | `x_execute.run_plan` | desconocida | desconocida | `resultado`, `handle/url`; no asumir ACK remoto |
| Threads | `threads_execute.run_plan` | `threads_api.publish_reply` | desconocida | POST sin ID => incierto |
| Facebook | `facebook_execute.run_plan` | desconocida | desconocida | índices/permalinks, sin ID de ACK por defecto |
| Pinterest | `pinterest_growth.cmd_run` | `pinterest_loyalty_observations` | desconocida | API: conteos sin ID exportado, siempre `unknown` individual |
| Reddit | `reddit_execute.run_plan` | desconocida | desconocida | `url/subreddit`; subreddit NO prueba identidad autor |
| Bluesky | desconocida | `bluesky_execute.run_plan` | desconocida | ActionLedger reservado; ACK incierto separado |
| Mastodon | desconocida | `mastodon_execute.run_plan` | desconocida | idem; no convertir errores 5xx a éxito |
| TikTok | desconocida | desconocida | `tiktok_mobile_execute.run_plan` | `_intent_id` existente; ACK móvil se acredita aparte |
| Instagram | `instagram_execute.run_plan` | desconocida | `instagram_execute.run_plan` | móvil y web comparten plan pero no evidencia idéntica |

**Importante:** la matriz afirma que existe ese productor, NO que ya
exporte los campos `record_id`, `occurred_at` y `ack`. Los resultados
en bruto de estos ejecutores carecen a menudo de esas tres pruebas: el
bridge responde `unknown` o `unverified`, **no inventa datos**. Esta
PR no modifica los ejecutores privados ni los declara integrados. La
habilitación real posterior exige emitir un export inmutable con esos
campos. No hay paridad operativa 9x3: existe interfaz de ingestión común
y una fuente candidata examinada por red. No se escriben datos de usuarios
en el mirror.

## Contrato de captura (offline)

Ejemplo sintético:
```python
from tools.native_relationship_evidence_bridge import Batch, bridge_results
from tools.relationship_event_ledger import RelationshipLedger  # PR #84
ledger = RelationshipLedger("relaciones-secundarias.sqlite")
batch = Batch("bluesky", "API", "bluesky_execute.run_plan", "export-inmutable-1")
result = bridge_results(ledger, batch, [{
    "record_id": "fila-1", "reservation_id": "reserva-1",
    "kind": "follow", "handle": "@lectora",
    "occurred_at": "2026-10-10T09:00:00Z", "resultado": "confirmado",
    "ack": {"id": "ack-remoto-1", "kind": "follow",
            "target": "@lectora", "basis": "api_response"},
}])
```

Prohibido inventar un `ack` a partir del `resultado`. Debe proceder de
la confirmación real del productor y estar enlazado al target. Repetir el
mismo export y fila es idempotente; para ACK posterior, se registra fase
`ack`. Si un origen carece de reloj con zona horaria, no deducir DST:
se reporta `unknown` o falla validación de #84. Mismo `export_id`
significa export inmutable: si se reordena o muta debe versionarse.

Para snapshots: `tracked` y `followers` deben ser IDs explícitos;
`coverage.identity_stable=true` verifica la procedencia de identidades;
la ausencia requiere además `coverage.complete=true`,
`coverage.all_pages=true` y `account_scope` no vacío. Los parciales
solo generan presencias vistas y `unknown` para ausencias. Los conteos
de Pinterest no permiten inferir altas o bajas individuales.

## Reutilización pública actual (código no copiado)

| Alternativa, revisión inmutable | SPDX | Python 3.11/Windows | Decisión |
|---|---|---|---|
| [eventsourcing `575d42c`](https://github.com/pyeventsourcing/eventsourcing/tree/575d42c10a821828639b90178ed56703abe9c9f1) | BSD-3-Clause | >=3.11; Windows no validado aquí | No añadir un segundo event store |
| [sqlite-utils `6bc1d33`](https://github.com/simonw/sqlite-utils/tree/6bc1d33d583c54bd69fbdd2071117e2d38c354a1) | Apache-2.0 | >=3.10; CLI multiplataforma | #84 ya conserva WAL/SQLite nativo; no duplicar |
| [python-jsonschema `c497561`](https://github.com/python-jsonschema/jsonschema/tree/c497561ea0a95f5aac09cd63d15eb1420eb7bbec) | MIT | revisión actual exige >=3.12: incompatible con 3.11 | Evitar dependencia nueva |

Referencias verificadas mediante GitHub a fecha de ejecución. En los tres
repositorios se observan commits recientes en 2026; no se copiaron
funciones ni archivos de terceros. Se eligió normalización stdlib, compatible
con el almacén #84. Las licencias no sustituyen la evaluación de CI.

## Evidencia de pruebas y segunda revisión adversarial

- Pruebas: `python -m unittest discover -s tests -p test_native_relationship_evidence_bridge.py -v`.
- Contrato SQLite real con checkout inmóvil de #84:
  `LEDGER84_PY=ledger84/tools/relationship_event_ledger.py python -m unittest discover -s tests -p test_native_ledger84_contract.py -v`.
- CI: `.github/workflows/native-relationship-evidence.yml` sobre Ubuntu/Windows Python 3.11; no credenciales sociales.
- Revisión adversarial: se detectó el nombre de productor Pinterest
  `run` incorrecto y se corrigió a `cmd_run`; se retiró el falso alias
  `save -> repost`; se incorporó `like_external` y el ID de origen pasó
  a un array JSON sin colisiones por delimitadores.
- Limitación: el ACK suministrado es una **declaración del productor**,
  no una consulta remota del bridge. La cobertura real, el móvil Android,
  Edge/CDP y APIs necesitan canarios supervisados posteriores. Ni un test
  sintético ni `mergeable=true` demuestran operación end-to-end.

## Reversión

Solo retirar consumidor/puente y, si se creó en pruebas, cerrar y retirar
la DB secundaria del ledger #84. No se modifican reservas, CSV, SQLite
operativo, credenciales ni estados de ninguna red. Sin migración destructiva.
