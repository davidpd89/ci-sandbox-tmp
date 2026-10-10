# PR #57 — ciclo de followback: estados, evidencia y paridad

Fecha de corte: **10/10/2026**. Rama: `research/47-followback-lifecycle-parity`.
Alcance: comportamiento offline común y propuestas de limpieza sin ejecutar acciones
en redes. La rama contiene código, pruebas y fixture ficticio, no datos personales.

## Problema

En el espejo `tools/unfollow_cleanup.py` disponía de cuatro adaptadores
(Bluesky, Mastodon, X, Threads); `tools/mechanical_round.py` los ejecuta en
`post`. `tools/follow_review.py` interpreta el CSV de operaciones y
`tools/relationship_policy.py` establece 7 días y 21 días entre reintentos.
TikTok tiene una auditoría distinta de reciprocidad
(`tools/tiktok_reciprocity_audit.py`) con instantáneas posiblemente parciales;
no está en `ADAPTERS`. Facebook, Instagram, Pinterest y Reddit tampoco
estaban conectados al limpiador común. No se supone que una ausencia en un
listado incompleto signifique ausencia de followback.

**Auditoría del repositorio oficial privado**, rama
`integracion/crecimiento-2026-10`: se consultaron
`tools/unfollow_cleanup.py`, `tests/test_pr157_requested_follow_state.py`,
`tests/test_pr39_unfollow_gate.py` y las herramientas equivalentes del espejo.
La versión privada incorpora `circuit_breaker.write_preflight` en la ruta
`run`; esta diferencia NO se ha eliminado ni copiado a la rama pública.
`pendiente_aprobacion` es un resultado real distinto de `confirmado`; el
ciclo offline nunca le atribuye un follow vigente hasta una confirmación.
La vía heredada de TikTok tiene una barrera específica, que no se modifica.
El código de esta PR debe portarse al oficial mediante revisión de Claude,
**sin reemplazar indiscriminadamente los módulos privados**.

## Cobertura real (antes y después)

La función `coverage()` calcula conexión al pipeline desde
`mechanical_round.PIPELINES` y `unfollow_cleanup.ADAPTERS`, usando las
capacidades efectivamente presentes. Se incluye Instagram, ausente del
inventario anterior `network_capabilities.NETWORKS`; no se modifica ese
inventario general por pertenecer al trabajo específico de paridad #43.

| Red | Cola predominante | Reciprocidad observada en espejo | Adaptador cleanup y paso automático | Replay offline nuevo |
| --- | --- | --- | --- | --- |
| Bluesky | API | followers + getProfile.viewer.followedBy | Sí / sí | Sí |
| Mastodon | API | followers + relationships.followed_by | Sí / sí | Sí |
| X | WEB | listado + indicador individual | Sí / sí | Sí |
| Threads | WEB | listado + profile_info individual | Sí / sí | Sí |
| Facebook | WEB | sin fuente de followback verificada aquí | No / no | Sí |
| Instagram | WEB | sin fuente verificada aquí | No / no | Sí |
| Pinterest | WEB | sin fuente verificada aquí | No / no | Sí |
| Reddit | WEB | sin fuente verificada aquí | No / no | Sí |
| TikTok | MOBILE | auditoría independiente, admite parciales | No / no | Sí |

**Métrica de conexión:** 4/9 con limpieza programada, sin cambio en este PR;
**métrica de contrato offline:** 0/9 -> 9/9 redes con el mismo replay y estados.
El replay nuevo NO equivale a nueve adaptadores de ejecución. Llamarlo
«paridad completa de unfollow» sería falso. Conservar el acceso vivo detrás
de cada adaptador es preferible a simular un detector negativo y borrar por error.

## Decisión e implementación

`tools/followback_lifecycle.py` separa tres hechos:

1. **Historial confirmado** de follow, unfollow, solicitud pendiente,
   conversación e instantáneas verificadas de reciprocidad. Cada nuevo ciclo
   de follow inicia un reloj propio; un fallo de follow no inicia el reloj.
2. **Observación actual**, con conjuntos de seguidores/seguidos y banderas
   explícitas de lectura completa. Un positivo en un listado parcial es útil;
   su ausencia NO demuestra el negativo.
3. **Decisión orientativa**, nunca ejecutora: `waiting`,
   `pending_approval`, `reciprocal`, `engaged_review`,
   `due_unverified`, `eligible`, `lost_followback`,
   `not_following`, `manual_unknown_age`. `eligible` exige follow
   actual confirmado por lista y falta de reciprocidad verificada. No concede
   permiso para saltarse `follows_me` en vivo, que sigue siendo obligatorio
   en `unfollow_cleanup.run`.

La identidad se compone de red + nombre completo; `ana@example.com` y
`ana@example.org` nunca se confunden en Mastodon. Dentro del limpiador,
los follows históricos que ya no figuran en el listado actual se excluyen;
la lista de protección se aplica también a la causa de falta de followback.
En `follow_review` un unfollow confirmado borra los gestos del ciclo
anterior, y solo cuentan las respuestas hechas mientras había follow activo.
Esto evita mantener indefinidamente el estado «interacción» después de
un segundo follow nuevo.

La decisión ante dato incompleto es **revisión pendiente**, no un falso
negativo. No se añade una espera arbitraria cuando el dato es completo.
Por defecto sigue vigente el período de 7 días del sistema real.

## Licencias y procedencia

Fuente primaria: https://github.com/fgmacedo/python-statemachine
Fecha de consulta: 2026-10-10
Licencia SPDX: MIT
Referencia inmutable: https://github.com/fgmacedo/python-statemachine/commit/525bcddcc5bb9793ce03d7b3e560f9c2ec0c5ee2

Se revisaron también los otros tres orígenes y commits fijados abajo.
No se incorporó código de terceros: se evaluaron sus APIs y patrones.
El proyecto propio conserva su licencia existente; sin vendoring ni
nuevas dependencias en esta PR.

## Alternativas (corte 10/10/2026)

| Candidato | Commit exacto / licencia | Mantenimiento y compatibilidad | Decisión |
| --- | --- | --- | --- |
| [pytransitions/transitions](https://github.com/pytransitions/transitions/commit/bd42b38f3627e6bca7274fb4d9af2e105f75da7c) | `bd42b38f`; MIT | último commit de rama consultado 09/09/2025; FSM general, Python 3.11 compatible; sin bloqueo de Windows identificado | No añadir dependencia: modela transiciones, no la procedencia ni completitud de listas |
| [fgmacedo/python-statemachine](https://github.com/fgmacedo/python-statemachine/commit/525bcddcc5bb9793ce03d7b3e560f9c2ec0c5ee2) | `525bcddc`; MIT | rama activa en octubre 2026; PyPI 3.2.1 de 01/08/2026; Python >=3.10 y wheel puro | No usar por coste de integrar un FSM declarativo para un único proyector determinista |
| [MarshalX/atproto](https://github.com/MarshalX/atproto/commit/4c17895c97f6d42ecb9c41dc5c2fb450ab9c6ac8) | `4c17895c`; MIT | commit 02/10/2026, Python 3.11 admitido; SDK con dependencias httpx/Pydantic/criptografía, evolución pre-1.0 | Candidato para el adaptador API Bluesky, no para el núcleo multired; mantener HTTP existente de momento |
| [halcy/Mastodon.py](https://github.com/halcy/Mastodon.py/commit/336a62d850a28f6f066a26b83506ed70f0f4b906) | `336a62d`; MIT | commit 07/10/2026; wrapper de API Mastodon, Python 3.11; compatibilidad Windows no verificada con hardware real | Candidato para adaptador Mastodon, pero no ofrece estados multired |
| Código existente `follow_review` + `unfollow_cleanup` | código propio del proyecto | cero dependencia externa añadida, integración ya probada en CI del espejo | **Elegido**: componente puro acotado y correcciones compatibles |

La investigación **no copia** código de terceros; conserva la procedencia y
sus licencias para una eventual integración con pruebas propias. No se asume
que actividad reciente implique garantía de estabilidad ni de compatibilidad
de Edge/ADB en Windows. La elección reduce coste de paquetes nuevos a cero,
mantiene las tres colas desacopladas y permite revertir el proyector sin
migrar datos.

## Pruebas y segunda revisión adversarial

Fixture reproducible: `tests/fixtures/followback_lifecycle_sample.json`
(solo handles de dominios reservados). Comandos:

```sh
python tools/followback_lifecycle.py --matrix
python tools/followback_lifecycle.py --fixture tests/fixtures/followback_lifecycle_sample.json
python -m pytest tests/test_followback_lifecycle.py tests/test_followback_cleanup_regressions.py tests/test_follow_review.py tests/test_unfollow_cleanup.py -q
```

La matriz es determinista, no se conecta a cuentas. Casos: D+3, D+7, follow
fallido, pendiente, positivo en lista parcial, ausencia no verificable,
pérdida posterior de reciprocidad, unfollow y nuevo follow, conversación,
identidades homónimas federadas, cuenta manual sin antigüedad, cuenta protegida
y registro antiguo ajeno al listado de seguidos. Métricas observables en CI:
número de tests ejecutados, cobertura por red del contrato 9/9 y número
de adaptadores realmente programados 4/9. No se declara porcentaje de
precisión en redes reales sin observaciones etiquetadas y verificadas.

**Revisión adversarial 2** (efectuada sobre la primera implementación):
- Al pasar `network="fake"` desde tests del adaptador sintético, fallaba
  `account_key`; se usa identidad compatible para pruebas de adaptadores
  sin modificar la lista de redes admitidas en el núcleo.
- La respuesta del ciclo anterior permanecía en `actions` después de un
  unfollow confirmado; se reinicia para no atribuirla a otro ciclo.
- Identidades de Mastodon con igual local-part se equiparaban mediante
  `growth_attribution._same`; se exige igualdad completa donde importa.
- La limpieza debe operar sobre seguidos actuales, no solo sobre eventos
  históricos; se aplica la intersección antes de proponer candidatos.
- Dominio de fixture: se usan dominios reservados `example.com`,
  `example.org`, `example.net` que admite el guardián de privacidad.

## Retirada, limitaciones y entrega para Claude

**Simulado:** replay y candidatos con CSV/JSON ficticios. **No probado:**
comprobación en vivo en Edge, ADB, Android o Windows físico; recolección
completa de 9 listas reales; costes de paginación, latencia y tasas de
reciprocidad reales. **Canario supervisado pendiente:** ejecutar primero
`--matrix` y `--fixture` localmente; posteriormente, verificar
manualmente un perfil de cada uno de los 4 adaptadores ya disponibles, sin
mutar redes, y contrastar el indicador de reciprocidad con el registro.

Integración en el privado: portar con diff a la versión actual
(incluido el guardia `circuit_breaker`) y ejecutar sus pruebas de PR #157
y #39; **no copiar `unfollow_cleanup.py` entero desde el mirror**.
Rollback: revertir los commits de esta PR (no hay migración ni estado
persistido nuevo). La actividad real de seguir/dejar de seguir permanece
fuera de las pruebas. El hueco de reconciliación tiene ya PR [#58](https://github.com/davidpd89/ci-sandbox-tmp/pull/58);
no abrir trabajo duplicado.

## Estado de validación

El criterio para dar por preparada la PR es pasar la validación de campaña
y la suite offline en Ubuntu/Windows, con cierre de regresiones encontradas.
Los resultados concretos y SHA final se anotan en el comentario de entrega
de la PR tras verificar las ejecuciones; no se presentan tests no ejecutados
como superados.
