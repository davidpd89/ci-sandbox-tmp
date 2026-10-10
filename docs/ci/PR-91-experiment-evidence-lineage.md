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
El gate de #3 está incorporado en estos archivos; antes de integrar en el oficial, contrastar su estado real y evitar duplicar el gate. El protocolo opcional
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
| [python-jsonschema 4.26.0](https://pypi.org/project/jsonschema/4.26.0/) (2026-01-07) | MIT | Sí, >=3.10, OS independiente | attrs, jsonschema-specifications, referencing, rpds-py; activo en 2026 | No incorporar: validación estructural acotada sin $refs; no autentica auditorías |
| [Pydantic 2.14.0](https://pypi.org/project/pydantic/2.14.0/) (2026-10-08) | MIT | Sí, >=3.10 | pydantic-core compilado, typing-extensions y annotated-types; activo en 2026 | No incorporar: validación más extensa con dependencia binaria para 9 campos |
| [Hypothesis 6.168.5](https://pypi.org/project/hypothesis/6.168.5/) | MPL-2.0 | Sí, wheel CPython 3.11 Windows/Linux publicado 2026-10-05 | sortedcontainers; activo, generador de tests | No incorporar: la PR #30 ya cubre fuzzing; regresiones actuales deterministas |
| [rfc8785.py 0.1.4](https://pypi.org/project/rfc8785/0.1.4/) ([fuente](https://github.com/trailofbits/rfc8785.py)) | Apache-2.0 | Puro Python >=3.8, compatible con 3.11 y sin componentes nativos Windows | Sin dependencias de ejecución; versión pública 2024, mantenimiento posterior no confirmado | Candidato si hay verificadores externos en otros lenguajes (JCS/RFC 8785); no añadir para un consumidor Python que ya fija su propia serialización v2 |

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
- Integración: #3 está cerrada sin merge en el mirror. Verificar su incorporación real al oficial, conservar los arreglos del gate y comprobar ambos workflows en HEAD final.

## Pruebas reproducibles para el controlador

```shell
python -m compileall -q tools tests
python -m pytest -q tests/test_cross_network_learning.py tests/test_experiment_evidence_lineage.py -p no:cacheprovider
```

El workflow `.github/workflows/validate-social-tools.yml` existente ejecuta
Python 3.11 en `ubuntu-latest` y `windows-latest` tras cada push;
su resultado debe comprobarse para el **HEAD final**, no para commits previos.
No se ejecutan Windows interactivo, móvil ni Edge. Fixture de auditoría
simulada = prueba de software; no equivale a auditoría humana real.

## Revisión adicional del controlador (09-10-2026)

Se refuerza la correspondencia de un `experiment_id` con **una única**
identidad auditada: diseño, asignaciones, recuento, origen y táctica deben
coincidir en todas las aprobaciones de ese ensayo (puede haber más de una
cola/destino, con digests independientes). Antes el registro solo prohibía
reutilizar un manifest entre IDs distintos, pero admitía el mismo ID para
manifests divergentes. También se impide sustituir o eliminar `_entries`
tras construir el snapshot; no se confunde esta inmutabilidad de API con
una defensa frente a `object.__setattr__` ejecutado por código privilegiado.

Regresiones nuevas: identidad incoherente con cambio de manifiesto, diseño,
recuento, red origen y táctica; reutilización legítima del mismo ensayo entre
colas con aprobaciones independientes; prohibición de reasignar/eliminar el
mapa del registro. En una tercera pasada se detectó eludir `approves()`
mediante una subclase inyectada al controlador; ahora la API solo acepta el tipo
exacto `TrustedRegistry` y hay una prueba con una subclase falsa.
La validación definitiva debe referirse a los checks
Windows/Ubuntu del **nuevo HEAD** tras estos commits. La integración exige contrastar con los últimos arreglos de #3, incluso después de su cierre sin merge.

## Segunda revisión adversarial, posterior a la primera CI

La primera tanda (HEAD `31f6b285`) ejecutó correctamente las regresiones
offline en Ubuntu, pero quedó cancelada en Windows por la llegada de un commit
posterior: no debe considerarse Windows validado por esa tanda.
Se detectó además que la clase inicialmente copiaba las entradas pero
conservaba su diccionario interno mutable. Se corrigió con
`MappingProxyType` anidado para congelar claves y valores, y una prueba
reproduce tanto mutación del origen tras la construcción como intento de
alterar el snapshot desde el llamador. El límite sigue siendo de confianza
entre procesos: no asegura la autenticidad del archivo externo.

## Revisión independiente adicional (10-10-2026)

- Se detectó un límite de escala en `TrustedRegistry`: 100 ensayos con
  siete destinos requieren 700 revisiones; el máximo anterior de 200
  impedía construir ese registro. El máximo pasa a 800, manteniendo
  las 100 observaciones por lote y una cota finita. Un test sintético
  valida las 700 aprobaciones y el rechazo de 801 entradas.
- Se corrigió el **adaptador de fixtures** procedente de #3: al
  recorrer varios destinos sobrescribía la identidad opaca del ensayo
  y dejaba los registros anteriores ligados a otra identidad.
  Ahora fija una identidad antes de proyectar cada destino; un test
  acredita dos destinos aprobados por separado. Este adaptador
  **solo existe en tests**, no permite autoverificación en producción.
- Alternativa pública para evolución: [in-toto](https://github.com/in-toto/in-toto)
  ofrece metadatos de procedencia firmados y verificación independiente,
  pero adoptarlo sin manifests reales ni un productor auditado añade
  complejidad. `rfc8785.py` solo aportaría valor al normalizar contratos
  entre lenguajes. No se introducen dependencias nuevas.
- Sigue pendiente verificar el estado efectivo de #3 en el oficial, conservar sus correcciones y repetir Windows/Ubuntu sobre el HEAD final. La capacidad demostrada
  es del registro offline, no prueba aprendizaje causal ni acciones reales.

## Actualización independiente — 10/10/2026 (control de integración)

- Se sincroniza esta rama con `ci/test-campaign-parent` en
  `c48480c979fdfc06fb4169a53da0b92c36601766` mediante commit de
  combinación con dos padres. La base aportaba 15 archivos distintos
  de los ocho modificados por #91; no se resolvieron colisiones descartando código.
- Se recupera la corrección de #3 para `_positive_effect`: un
  `wilson_interval_gap` estrictamente positivo no debe redondearse a
  `0.0`. Regresión determinista: dos muestras de un millón,
  500.990 frente a 499.010 éxitos, brecha positiva inferior a 0,00005.
- **Estado de dependencia corregido:** #3 figura **closed, merged=false**
  en el mirror. El último comentario sostiene que se integró en el oficial
  mediante `89469ebd`, pero ese commit modifica followback/hashtags, no
  `tools/cross_network_learning.py`. En la rama oficial el archivo sigue
  con blob `673c74ab2c19831debc1827812eeb1b47a259f31` y `schema=1`.
  Antes de incorporar #91, Claude debe confirmar en qué rama/commit está
  realmente integrado el gate por cola de #3. Esta PR transporta los cambios
  del gate y añade el contrato v2; no debe restaurarse el verificador legacy.
- La integración operativa exige repetir CI y comparar el gate del oficial
  con el de esta PR, además de la suite offline.

## Control adversarial final — 10/10/2026

- **Conflictos v2:** una fila sin `experiment` válido ya no puede contaminar el recuento de duplicados ni vetar un ensayo auditado. Las réplicas negativas con identidad sintácticamente válida siguen vetando; el comportamiento legacy de `schema=1` se conserva. Se añadió una regresión con los tres escenarios.
- **Cobertura CI:** `.github/workflows/experiment-evidence-lineage.yml` vuelve a ejecutar las regresiones en Ubuntu/Windows si cambia `tools/growth_attribution.py`, dependencia del intervalo de Wilson usada por este gate. Una prueba estática exige el disparador en `push` y `pull_request`.
- **Sin cambio operativo:** no se construyen registros desde JSON ni se incorporan aprobaciones al CLI. Falta un auditor real independiente para acreditar manifests; los fixtures solo prueban el contrato. Verificar los checks para el último SHA, no reutilizar ejecuciones anteriores.

## Sincronización con la base vigente y respuesta a revisiones — 10/10/2026

Revisión de **todas** las conversaciones principales, dos reviews formales e hilos
inline (ninguno), último HEAD de #91, #3, y oficial privado. Las incidencias
comunicadas por el controlador ya constaban corregidas en esta rama: conflicto de
identidad y design/assignment por ID, cierre del snapshot y subclases,
700 registros/800 como límite, fixtures multidestino, precisión Wilson y
colisiones v2 que ignoran identidad inválida pero incluyen réplica negativa.
Se mantienen las pruebas correspondientes.

**Actualización de base:** la PR apuntaba a `ci/test-campaign-parent` y
estaba un commit detrás del nuevo `3d0304c0704e31c8a1ecbd62944d22c330bd7ea5`.
Se incorporó mediante merge de dos padres, trasladando intactos los ocho
archivos de la PR #87 (Gitleaks fijado, escaneo de secretos y regresiones).
Para la única colisión, `tests/test_tiktok_safety.py`, la base vigente ya
había resuelto la caducidad de la fixture de cuota diaria con una fecha actual
obtenida durante el test: se usa la versión de la **base** y se elimina de #91
la modificación redundante de una prueba ajena a identidad de experimentos.
No se toca `tools/tiktok_*` ni se relaja la comprobación de cuotas.
Comparación esperada: cero commits detrás y diff de #91 de ocho archivos.

**Dependencia #3 y rama oficial:** #3 figura cerrada sin merge en este mirror;
el blob del evaluador oficial sigue siendo
`673c74ab2c19831debc1827812eeb1b47a259f31` (v1). Por eso #91 incluye
el gate por colas y todos los cambios auditados de #3 necesarios para v2.
No se debe volver a portar #3 a ciegas al integrar #91. La rama sincronizada
`research/public-reuse-parent` mencionada en los comentarios NO es la base
de esta PR; cambiar la base sin instrucción expresa transformaría su alcance.
Esta actualización mantiene la base solicitada `ci/test-campaign-parent`.

**Sin inventar evidencia:** las suites y el escáner de secretos deben pasar
sobre el nuevo HEAD exacto; esa validación no convierte manifiestos sintéticos
en auditorías reales y no representa un canario supervisado. Para portar al
oficial, el controlador contrastará los hashes del código receptor y ejecutará
sus pruebas aisladas; la procedencia auditada del registro debe verificarse
fuera del agregado, por un auditor independiente, antes de habilitar propuestas.
