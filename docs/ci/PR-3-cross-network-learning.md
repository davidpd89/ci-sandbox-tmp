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

La validación final debe tomarse de GitHub Actions, que ejecuta Python 3.11 en `ubuntu-latest` y `windows-latest`. El entorno local de esta sesión no pudo resolver `github.com`, por lo que no se usa como evidencia de ejecución.

## Revisión adversarial

Se hizo una segunda pasada separada del desarrollo inicial. Hallazgos corregidos:
- los estados negativos/positivos de destino no caducaban de forma uniforme y podían bloquear o afirmar estado indefinidamente;
- la primera implementación de cola podía lanzar `TypeError` con JSON no escalar por una comprobación sobre `frozenset`;
- la verificación externa no estaba ligada a WEB/API/MOBILE y podía reutilizarse entre superficies.

Tras las correcciones, no queda un hallazgo crítico conocido dentro del alcance de esta PR. Límites deliberados:
- no hay cálculo formal de potencia ni corrección por múltiples tests;
- Instagram no se incorpora porque el contrato recuperado y `discovery_attribution.NETWORKS` instrumentan ocho redes;
- no se ejecutan Edge, móvil, navegador, API social ni canarios reales;
- la evidencia final de portabilidad es el workflow del HEAD, con Python 3.11 en Ubuntu y Windows.

No se abre PR adicional en esta ronda: los huecos encontrados eran autocontenidos y se implementaron aquí, y la búsqueda de PRs abiertas no encontró un trabajo equivalente que hubiera que reutilizar o coordinar.
