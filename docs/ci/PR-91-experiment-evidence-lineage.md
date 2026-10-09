# PR #91 — identidad auditada de ensayos (contrato v2)

Fecha: 2026-10-09. Esta rama NO efectúa acciones reales ni migraciones.

## Dependencia y procedencia

Se consultó el repositorio oficial privado `davidpd89/rrss-davidporto-CODE`,
rama `integracion/crecimiento-2026-10`: `tools/cross_network_learning.py`
(blob `673c74ab2c19831debc1827812eeb1b47a259f31`) conserva el gate legacy,
sin separación por cola de la PR #3. Por ello se reutilizaron directamente desde
`ci/cross-network-learning` los blobs `tools/cross_network_learning.py`
(`94c04d13b45e6a3936e889a78766a271039e74bd`), `tests/test_cross_network_learning.py`
(`26512d32040ef3172e3c38a4ef5c5c7a6fad918b`) y `tools/discovery_attribution.py`
(`43e8f307c2c12e307fbf43303ec4ce60a20d61c8`). No se reescriben y su origen queda explícito.
Esto hace que #91 dependa de integrar primero #3; el controlador debe evitar
duplicar estos archivos al integrar ambas PR. El protocolo opcional
`docs/open-source-scouting/PROTOCOL.md` no existe en esta rama.

## Contrato reproducible

El agregado `schema=2` conserva `observations` y `history` del v1.
Cada observación añade, por ejemplo:

```json
"experiment": {
  "id": "trial-A001",
  "design_sha256": "SHA256_HEX_DE_64_CARACTERES",
  "assignment_sha256": "SHA256_HEX_DE_64_CARACTERES"
}
```

Los hashes de ejemplo se sustituyen por hashes hexadecimales válidos de
artefactos auditados; la asignación no contiene datos identificativos en el
agregado. Un registro revisado **fuera** del JSON de observaciones tiene
exactamente las claves `experiment_id`, `design_sha256`,
`assignment_sha256`, `assignment_count`, `origin`, `feature`,
`target`, `queue` y `evidence_sha256`.
Se construye `TrustedRegistry([registro_revisado])` exclusivamente en código
de controlador confiable; ningún argumento de CLI ni campo `verified` del
agregado incorpora registros. El auditor debe comprobar que el hash de
asignaciones proviene de un manifest de unidades asignadas independiente,
que la asignación y el diseño se corresponden con el identificador opaco,
el total de unidades, el origen y la cola, y que el compromiso
`evidence_sha256` se calculó tras revisar el resultado.

Ejemplo mínimo **sintético** reproducible en pruebas:
`tests/test_experiment_evidence_lineage.py::trial` genera el agregado,
`audit_projection(row, "mastodon")` forma la proyección contrastable con
la fuente externa y `evidence_digest(row, "mastodon")` liga la observación
al registro. `TrustedRegistry` solo acepta registros completos, rechaza
duplicados y no permite que un mismo manifest de asignaciones acredite
dos ensayos con diferentes IDs.

El digest v2 incluye dominio/versión literal, ID opaco, manifiestos de diseño
y asignaciones, recuento total, `origin/feature/target/queue`, datos
agregados, `capability/permission/implemented/checked_on`. Serialización
JSON determinista con claves ordenadas y longitud limitada, SHA-256,
comparación de digest en tiempo constante. No afirma autenticidad por sí solo.
La aprobación no puede transferirse entre WEB/API/MOBILE ni entre ensayos
numéricamente idénticos.

`schema=1` sigue siendo legible y reportable; aunque un código anterior
pase `trusted_verifications`, **nunca** devuelve
`proponer_ensayo_manual`. Para migrar se requiere completar y auditar
los manifests originales: no se elevan viejas pruebas por inferencia.
No hay estado persistente ni migración automática. CLI siempre solo lectura
y sin parámetro de registro; todo resultado conserva `writes: false`.

## Reutilización pública comprobada (09-10-2026)

| Proyecto | Licencia | Python 3.11 / Windows | Dependencias y mantenimiento | Decisión |
| --- | --- | --- | --- | --- |
| [python-jsonschema](https://github.com/python-jsonschema/jsonschema) | MIT | Sí, >=3.10, OS independiente | attrs, jsonschema-specifications, referencing, rpds-py; activo en 2026 | No incorporar: validación estructural acotada sin $refs; no autentica auditorías |
| [Pydantic](https://github.com/pydantic/pydantic) | MIT | Sí, >=3.10 | pydantic-core compilado, typing-extensions y annotated-types; activo en 2026 | No incorporar: validación más extensa con dependencia binaria para 9 campos |
| [Hypothesis 6.168.5](https://pypi.org/project/hypothesis/6.168.5/) | MPL-2.0 | Sí, wheel CPython 3.11 Windows/Linux publicado 2026-10-05 | sortedcontainers; activo, generador de tests | No incorporar: la PR #30 ya cubre fuzzing; regresiones actuales deterministas |

La continuidad gana por menor superficie, reutilizando el gate de #3,
`hashlib`, `json`, `hmac` y `re` de la biblioteca estándar; no se copia
código de terceros. Los componentes evaluados son alternativas, no promesas
de auditoría externa automática.

## Confianza, revisión adversarial y límites

- Primer límite: productor del agregado controla los counts e IDs. Nunca
  puede aprobarse con su propio JSON.
- Segundo límite: un proceso local de auditoría independiente, con acceso
  al manifest real de asignaciones, concede el registro `TrustedRegistry`.
  Esta API **no verifica firmas ni garantiza** que el manifest fue auditado.
  Una integración futura debe custodiar el registro o añadir verificación
  criptográfica; no crear el registro desde observaciones no confiables.
- Tercer límite: permiso y capacidad siguen ligados a destino, cola y TTL.
  Una aprobación auditada no suprime el control de frescura de PR #3.
- Revisión adversarial: intentar sustituir IDs con agregados idénticos,
  cambiar cola/permisos/hash, reciclar manifest entre IDs, duplicar filas,
  falsificar JSON, contaminar logs con PII y usar verificaciones v1.
  Todos tienen pruebas sintéticas específicas.
- Alcance de pruebas: CPU local / Actions, sin social APIs, Edge, Windows
  interactivo ni móvil. Una suite verde es simulación **offline**, nunca
  canario supervisado ni validación de un auditor real.
- Límite causal: no verifica aleatorización material, integridad temporal,
  integridad del registro, ni que el lote contenga todos los ensayos reales.
  Tampoco sustituye #23, #80, #85 o revisión humana de una propuesta.
- Integración: dado que #3 sigue abierta, resolver la dependencia al
  fusionar ambas; comprobar workflows Ubuntu y Windows en HEAD final.
