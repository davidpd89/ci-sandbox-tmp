# PR #3 — Aprendizaje verificable entre redes

Fecha de revisión: 2026-10-09.

## Alcance y procedencia

La PR pública `davidpd89/ci-sandbox-tmp#3` parte de `ci/test-campaign-parent` y recuperó del repositorio oficial privado `davidpd89/rrss-davidporto-CODE` (rama `integracion/crecimiento-2026-10`) la implementación mínima necesaria para probar aprendizaje entre redes sin tocar cuentas.

Blobs oficiales consultados:
- `tools/cross_network_learning.py`: `673c74ab2c19831debc1827812eeb1b47a259f31`
- `tests/test_cross_network_learning.py`: `3c968a75690e52da90fb4d361105636dc5d46fab`
- `tools/discovery_attribution.py`: `43e8f307c2c12e307fbf43303ec4ce60a20d61c8`

En el snapshot de esta rama no existe `docs/open-source-scouting/PROTOCOL.md`, y el cuerpo actual de la PR no contiene una sección `## Encargo para GPT`. No se ha inventado ni reconstruido ese texto.

## Cambio aplicado en esta revisión

La versión recuperada verificaba capacidad y permiso solo a nivel de red. Eso era insuficiente para el contrato operativo real, que mantiene tres colas independientes: `WEB`, `API` y `MOBILE`.

Ahora:
- cada destino que pretenda pasar de `investigar_equivalencia` debe declarar una cola válida;
- capacidad, permiso e implementación no se interpretan si la cola falta o es desconocida;
- la cola queda incluida en el digest SHA-256 de evidencia;
- una verificación externa para `API` no puede reutilizarse para `WEB` o `MOBILE`;
- `denied`, `unsupported`, `implemented` y `verified` comparten el mismo TTL: un estado viejo vuelve a `investigar_equivalencia`;
- valores de cola malformados (listas, objetos u otros tipos) fallan cerrados sin excepción;
- el historial con cola `WEB/API/MOBILE` solo bloquea su cola; el historial anterior sin cola sigue siendo global para no reinterpretar rechazos antiguos;
- dos evidencias válidas de colas distintas se revisan por separado; dos de la misma cola siguen siendo un conflicto;
- observaciones sin controles o con `targets` estructuralmente inválidos no contaminan el detector de duplicados;
- las fechas implícitas usan `Europe/Madrid` (con `zoneinfo` y `tzdata` en CI), nunca el huso horario accidental del runner;
- el informe devuelve la cola explícita, sin ejecutar ni encolar ninguna acción.

Esto conserva una norma genérica entre redes sin compartir permisos ni capacidades entre superficies. Como la cola pasa a formar parte del digest, verificaciones calculadas con el contrato anterior dejan de promover propuestas y deben revisarse de nuevo; el fallo es deliberadamente seguro.

## Contrato estadístico actual

La PR exige:
- diseño declarado como aleatorizado;
- control real y población basal verificada;
- unidades de asignación únicas;
- snapshot completo a día 14;
- mínimo de 40 observaciones por brazo;
- observación madura y fresca;
- separación estricta entre el límite inferior Wilson 95 % del tratamiento y el límite superior Wilson 95 % del control;
- revisión humana;
- verificación externa ligada por digest antes de proponer un ensayo manual.

`MIN_N=40` es un suelo de política, no una afirmación de potencia estadística. La separación de intervalos Wilson es deliberadamente conservadora y tampoco se presenta como intervalo de confianza de la diferencia ni como corrección por comparaciones múltiples.

## Reutilización de software público

Se revisaron alternativas públicas a fecha 2026-10-09:

| Proyecto | Licencia | Estado / compatibilidad | Dependencias | Decisión |
| --- | --- | --- | --- | --- |
| statsmodels 0.15.0 | BSD-3-Clause | release 2026-08-27; Python 3.11 soportado; implementa tests, IC y potencia para dos proporciones | NumPy, SciPy, pandas, patsy, packaging, formulaic | No añadir: resuelve análisis más completo, pero amplía mucho el CI para un gate que no pretende emitir inferencia causal final |
| Spotify Confidence 4.1.0 | Apache-2.0 | activo en 2026; Python >=3.9 | NumPy, SciPy, pandas, statsmodels, Chartify, ipywidgets | No añadir: es una capa de experimentación completa y desproporcionada para este contrato offline |
| SciPy 1.17.x / main 2.0.dev | BSD-3-Clause | 1.17.x soporta Python 3.11; main ya exige Python >=3.12 | NumPy y binarios compilados | No añadir: útil para tests exactos, pero introduce dependencia compilada; además main ya no cumple el objetivo Python 3.11 |

Fuentes:
- https://github.com/statsmodels/statsmodels
- https://www.statsmodels.org/stable/generated/statsmodels.stats.proportion.test_proportions_2indep.html
- https://www.statsmodels.org/stable/generated/statsmodels.stats.proportion.power_proportions_2indep.html
- https://github.com/spotify/confidence
- https://github.com/scipy/scipy

Conclusión: gana la continuidad del código existente. No se copia código de terceros ni se añade licencia nueva. Si este gate pasara a tomar decisiones estadísticas automáticas, entonces sí debería migrarse el cálculo a una librería estadística mantenida y fijar un plan de potencia/MDE pre-registrado.

## Seguridad y límites

- Solo datos sintéticos/agregados.
- Sin credenciales, tokens ni handles en salida.
- Sin red, navegador, móvil, API social ni escritura de colas.
- `writes` permanece siempre en `False`.
- La CLI no acepta verificaciones externas; solo un llamador local confiable puede inyectar digests revisados.
- Un resultado `proponer_ensayo_manual` sigue requiriendo aprobación humana y no es un canario.
- Un canario supervisado real debe validarse aparte por Claude/controlador con entorno autorizado; esta PR no lo ejecuta.

## Pruebas

La suite específica cubre, entre otros:
- ocho redes instrumentadas sin convertir ausencia en cero;
- muestra mínima, madurez y frescura;
- conflicto de evidencias y orden de entrada;
- historial de decisiones;
- rechazo de JSON ambiguo/NaN/claves duplicadas;
- ausencia de escrituras;
- no filtración de datos no confiables;
- verificación externa ligada al agregado exacto;
- nueva regresión: digest y permisos ligados a `WEB/API/MOBILE`.

La validación final debe tomarse de GitHub Actions, que ejecuta Python 3.11 en `ubuntu-latest` y `windows-latest`. El entorno local de esta sesión no resuelve `github.com`, por lo que no se toma como evidencia de ejecución.

La tanda adicional prueba aislamiento de duplicados por cola, compatibilidad con historial legacy, rechazo de historial con tipos de cola malformados, protección frente a filas estadísticas inválidas y corte local de Madrid frente a la medianoche UTC. Las pruebas se ejecutan en el workflow del HEAD final, no se infiere su éxito desde un workflow anterior.

## Revisión adversarial

Se hizo una segunda pasada separada del desarrollo inicial. Hallazgos corregidos:
- los estados negativos/positivos de destino no caducaban de forma uniforme y podían bloquear o afirmar estado indefinidamente;
- la primera implementación de cola podía lanzar `TypeError` con JSON no escalar por una comprobación sobre `frozenset`;
- la verificación externa no estaba ligada a WEB/API/MOBILE y podía reutilizarse entre superficies.

Una nueva revisión adversarial del código completo detectó:
- error de arquitectura: el digest tenía cola, pero el historial y la deduplicación solo tenían red y táctica; corregido;
- observaciones estadísticamente inválidas contabilizadas como duplicados; corregido;
- fecha por defecto dependiente del huso horario del proceso, especialmente en CI UTC; corregido;
- error de sintaxis introducido en la fixture nueva, detectado por `compileall` real en Actions y corregido antes de concluir.

Límites deliberados:
- no hay cálculo formal de potencia ni corrección por múltiples tests;
- Instagram no se incorpora porque el contrato recuperado y `discovery_attribution.NETWORKS` instrumentan ocho redes;
- no se ejecutan Edge, móvil, navegador, API social ni canarios reales;
- la evidencia final de portabilidad es el workflow del HEAD, con Python 3.11 en Ubuntu y Windows.

## Comparación ampliada: generación de pruebas

Se comprobó el repositorio `HypothesisWorks/hypothesis`: proyecto activo (último push observado 2026-10-05), MPL-2.0, Python >=3.10 con soporte explícito de Windows, Linux y Python 3.11; su dependencia principal es `sortedcontainers`. Ofrece reducción automática de casos adversos mediante property-based testing. Se mantiene fuera del `requirements-ci.txt` de esta PR: los regresores concretos son deterministas y la PR abierta #30 ya se ocupa expresamente de incorporar fuzzing y contratos donde merezca la pena. Código: https://github.com/HypothesisWorks/hypothesis

## Hueco de trazabilidad que NO resuelve esta PR

`_evidence_digest` ata un agregado, su cola y los permisos a un hash determinista. No ata a una identidad independiente de ensayo / manifiesto de asignación: dos ensayos diferentes con exactamente los mismos campos agregados pueden obtener el mismo digest. Esto no autoriza acciones automáticas ni invalida los regresores offline, pero limita la afirmación de que una verificación solo puede emplearse una vez. Para resolverlo se requiere un identificador auditable de experimento, vinculación a fuente independiente y migración compatible de consumidores `schema=1`; no basta con añadir un UUID arbitrario autodeclarado. Es una integración específica para un trabajo posterior, sin duplicar la PR #23 (analítica/IC) ni la #85 (identidad entre usuarios/redes).

La PR #3 no se fusiona automáticamente ni ejecuta canarios reales. La aprobación de merge queda en manos del controlador tras comprobar el HEAD y sus workflows.


## Cuarta revisión adversarial — selección de ensayos y validez (09-10-2026)

**Defecto funcional nuevo y corregido:** el detector de duplicados aplicaba el filtro de `_positive()` al recuento de evidencias. Una réplica aleatorizada, madura, con grupo de control y trazabilidad declarada, pero cuyo efecto fuese desfavorable o inconcluso, desaparecía del recuento. La rama podía promover una hipótesis ganadora ignorando un ensayo independiente contradictorio de la misma red/táctica/cola: sesgo de selección de resultados.

Corrección: `_eligible_trial` valida metodología, fechas, población y ambos brazos **sin exigir un efecto positivo**; `_positive_effect` calcula después el resultado favorable. El detector de conflictos cuenta TODOS los ensayos elegibles y bloquea la promoción cuando dos ensayos de la misma red, táctica, destino y cola discrepan o se solapan. El resultado no favorable no genera propuesta y sí cuenta como `non_positive_trials`. Se conserva también el anterior contador `invalid_or_unproven` de `schema=1`, cuyo significado histórico incluía las evidencias no concluyentes, para no alterar consumidores previos.

**Segundo defecto corregido:** una fila con `targets` que mezclaba redes conocidas y otras no instrumentadas podía producir una propuesta para la parte conocida e ignorar silenciosamente una red errónea. La validación de destinos ahora rechaza las claves de red desconocidas, los conjuntos vacíos y las observaciones que solo apuntan a la red de origen; sí permite la clave de origen junto con un destino válido por compatibilidad con el contrato anterior. No se considera un resultado sobre Instagram, que conserva su trabajo independiente en #16.

Pruebas deterministas añadidas: réplica desfavorable que veta un resultado inicialmente verificable en ambos órdenes, independencia WEB frente a réplica API, rechazo de claves de red desconocidas sin bloquear un ensayo válido, conservación de contadores. Todo permanece offline y sin escritura.

### Repositorios públicos recontrastados

Metadatos consultados en GitHub el 09-10-2026:
- [statsmodels](https://github.com/statsmodels/statsmodels): BSD-3-Clause; último push observado 08-10-2026; soporte Python 3.11. Implementa comparaciones entre dos proporciones, potencia y ajustes de múltiples tests; útil para un informe causal formal, pero introduce NumPy/SciPy y otras dependencias no necesarias en este gate conservador.
- [GrowthBook Python](https://github.com/growthbook/growthbook-python): MIT; último push observado 05-10-2026; Python >=3.9 con 3.11 explícito; depende de `cryptography`, `typing_extensions`, `urllib3`, `aiohttp`. Implementa asignación determinista de variantes y tracking de exposición: candidato para el motor de experimentos de la PR #80, pero no reemplaza la auditoría independiente ni el filtro offline de PR #3.
- [Hypothesis](https://github.com/HypothesisWorks/hypothesis): MPL-2.0 confirmada en `LICENSE.txt`, último push 05-10-2026, Python >=3.10 con Windows y 3.11 explícitos; `sortedcontainers`. Apropiado para fuzzing/property-based testing de #30, sin necesidad de añadirlo a esta PR.
- [Zalando ExpAn](https://github.com/zalando/expan): MIT, último push observado 11-04-2023; el `setup.py` todavía referencia Python 2 y pytest 3.0.7. No es una opción mantenida/competitiva para Windows y Python 3.11 en 2026.

**Decisión de reutilización:** se mantiene el gate mínimo con las funciones existentes y Python estándar. No se copia código ni se agrega dependencia de terceros; el código público comparable aporta más valor a la implementación específica de las otras PR ya abiertas. No abrir trabajo duplicado.

### Limitación que permanece

Se exige una sola evidencia favorable no contradicha **dentro del lote disponible**, no se afirma haber inspeccionado la totalidad de experimentos externos. La integridad del historial de ensayos y la identidad auditada de cada ensayo deben verificarse en la PR #91. La ausencia de datos contradictorios en un JSON autodeclarado no es prueba de inexistencia real. Claude deberá revisar la integración con el repo privado y no confundir CI sintética con validación real.

El resultado exacto de la nueva ejecución Ubuntu/Windows se verificará contra el HEAD final de esta ronda; los éxitos de commits anteriores no se atribuyen a código posterior.
