# Descubrimiento, escucha y ranking — informe aplicado (10-10-2026)

## Problema
El ranking heurístico de consultas no acredita seguidores incrementales ni permite evaluar fiablemente rankings con holdout.

## Alternativas
Evaluadas River (BSD-3-Clause), contextualbandits (BSD-2-Clause), feedparser (BSD-2-Clause), Mastodon.py (MIT), atproto (MIT) y LightFM (Apache-2.0) frente a la pieza canónica del repositorio oficial. La comparación detallada consta debajo.

## Licencias y procedencia
Fuente primaria: https://github.com/davidpd89/rrss-davidporto-CODE/blob/5449513d9b545d0a6a72abf066ab6a779bfdad71/tools/discovery_ranking.py
Fecha de consulta: 2026-10-10
Licencia SPDX: NOASSERTION
Referencia inmutable: https://github.com/davidpd89/rrss-davidporto-CODE/blob/5449513d9b545d0a6a72abf066ab6a779bfdad71/tools/discovery_ranking.py
El código incorporado procede del repositorio privado del mismo titular, con autorización expresa del encargo; NO se declara que esté licenciado MIT ni se atribuye una licencia abierta inexistente. No se ha copiado código de los proyectos públicos comparados.

## Decisión
Portar el evaluador oficial y añadir un comparador temporal offline; sin ML pesado ni acciones operativas.

## Pruebas
Dos módulos de unittest, suite pytest y CI Ubuntu/Windows Python 3.11. No se asumen verdes hasta comprobar el último SHA.

## Retirada
Revertir los módulos, suites y el informe; no hay migración ni escrituras de estado.


## Resultado y procedencia

Esta PR incorpora código Python 3.11 de solo lectura, sin paquetes adicionales, estado real ni acciones sociales.

- **Reutilización canónica:** se portó desde el repo oficial privado autorizado davidpd89/rrss-davidporto-CODE, commit 5449513d9b545d0a6a72abf066ab6a779bfdad71, el archivo tools/discovery_ranking.py (blob de origen 7b8ef59a6ce6dce8e17031115c2978bf17b7cd72) y tests/test_discovery_ranking.py (blob 4370d9b2d1e8030e6d83048870ab29095c87c2f7). Se añadieron Instagram como novena red no instrumentada y un test de cobertura; se renombró una constante para evitar un falso positivo del gate de secretos del mirror. Ninguna identidad, cookie, consulta privada ni estado se trasladó.
- **Código nuevo:** tools/discovery_replay.py y tests/test_discovery_replay.py. Compara la selección por tasa observada sin umbral con el límite inferior de Wilson al 95 % y mínimo de 40 casos, **contra un holdout cronológicamente posterior idéntico para ambas estrategias**. Ningún resultado de holdout interviene en el ranking de entrenamiento. Devuelve métricas desconocidas si falta una cohorte o hay ventanas solapadas.
- El ranking original del oficial ya existe y tiene QA propio: docs/PR_050_DISCOVERY_RANKING_QA.md. Esta PR del espejo NO pretende duplicar ni sustituir las PR privadas #49 (atribución), #50 (ranking), #72 (rotación), ni las públicas #4 y #8 (regresiones de ranking y antigüedad). Lo nuevo y no duplicado es la **comparación en sombra antes/después por holdout**.

## Hueco real

El mirror usa tools/growth_common.py:rank_keys para ordenar términos en función de contadores fetched, accepted y new_handles, además de exploración y antigüedad. Son indicadores de lectura/selección, no conversiones de seguidores. El oficial también tiene discovery_attribution.py, discovery_graph.py, cohort_metrics.py, cross_network_learning.py y source_rotation.py, ausentes del mirror. No rehacerlos sin necesidad.

La evaluación de seguidores actual es explícitamente parcial: lectores posibles de snapshots solo para **Bluesky y Mastodon**, con certificación posterior pendiente de completitud e identidad. X, Threads, Facebook, Pinterest, Reddit, TikTok e Instagram muestran estado de no instrumentado, **no** prohibición de explorar esos canales. Los nueve escáneres y las tres colas WEB/API/MOBILE siguen inalterados. No se modifica frecuencia, volumen ni acciones reales.

## Repositorios públicos contrastados a 10/10/2026

| Candidato, revisión fijada a commit | Licencia / actividad / compatibilidad | Evaluación |
| --- | --- | --- |
| [River](https://github.com/online-ml/river/tree/d32e2800df067f4e7419e69dfa6a273ad1eadb27) | BSD-3-Clause; 07/10/2026; Python 3.11+ y ruedas Windows/Linux | Aprendizaje online prometedor con etiquetas; innecesario hasta disponer de evidencia longitudinal verificable |
| [contextualbandits](https://github.com/david-cortes/contextualbandits/tree/fc49364bf7f98abb6171351521deeade7800f01e) | BSD-2-Clause; 28/06/2026; posible compilación C/Cython en Windows | Métodos off-policy requieren historial de decisiones y propensiones reales, ausentes; no integrar |
| [feedparser](https://github.com/kurtmckee/feedparser/tree/a22c5521cbb109871f1a2318948581901bd47e26) | BSD-2-Clause según PyPI 6.0.14; 30/07/2026; Python 3.10+ y wheel universal; GitHub no clasifica licencia SPDX | Opción adecuada para escucha RSS futura, pero no sustituye datos sociales de nueve redes ni hay feeds confirmados |
| [Mastodon.py](https://github.com/halcy/Mastodon.py/tree/336a62d850a28f6f066a26b83506ed70f0f4b906) | MIT; 07/10/2026; Python portátil | SDK de lectura viable, pero existen adaptadores de Mastodon en el oficial; no portarlo aquí |
| [atproto](https://github.com/MarshalX/atproto/tree/4c17895c97f6d42ecb9c41dc5c2fb450ab9c6) | MIT; 02/10/2026; SDK Python | Útil para Bluesky; coleccionistas y problemas Jetstream se tratan por separado |
| [LightFM](https://github.com/lyst/lightfm/tree/0c9c31e027b976beab2385e268b58010fff46096) | Apache-2.0; último push en 2024; extensión compilada, verificar wheel Windows | Exige matriz de interacciones consistente y suficiente; no aporta al problema pequeño actual |

El módulo portado usa solo biblioteca estándar y fórmula Wilson ya auditada, en lugar de añadir un entorno ML. La [API de statsmodels](https://www.statsmodels.org/stable/generated/statsmodels.stats.proportion.proportion_confint.html) aporta referencia independiente del intervalo; **no se ha copiado código de terceros**. La licencia y la compatibilidad de cada dependencia deberán reevaluarse si se integra en otra PR. RecBole (MIT declarado, último push febrero 2025) también se descartó por costes y escala de datos. Las fechas anteriores proceden de GitHub y PyPI y no acreditan ejecución de esos proyectos en este mirror.

## Contratos y medición

- rank_cohorts exige tokens opacos de fuente (24 hexadecimales), datos completos de seguimiento, identidad única y procedencia certificadas upstream, cohorte homogénea, madurez mínima de 3 días, snapshot reciente y muestra mínima de 40. Los flags son **atestaciones de un importador futuro**, no verificaciones criptográficas. Los resultados observados dicen follows_us_at_snapshot, no incremento causal.
- compare_rankings recibe entrenamiento, holdout, dos fechas de corte inyectables, top_k y min_sample. Primero valida separadamente las cohortes mediante rank_cohorts; rechaza filas sin red, periodos superpuestos y conjuntos incompletos. Solo entonces compara, por cada red, la media de tasas observadas **por fuente** en el holdout. Una fuente con seguidores solapados con otra no puede sumarse como personas únicas.
- Estados de incertidumbre: missing_holdout, invalid_or_incomplete_cohort, overlapping_or_nonchronological_holdout, no_mature_train_cohorts, no_train_cohorts, insufficient_candidates_for_k y snapshot_not_instrumented. Esos estados devuelven tasas None: ausencia de prueba no equivale a cero.
- No filtra handles, textos, URLs ni búsquedas; publica solo fuentes con pseudónimos opacos. La veracidad de marcas y la estabilidad HMAC deberán acreditarse fuera de este módulo. Sin plans, follows, publicaciones, escrituras de estado ni auto-like X.

**Resultado sintético reproducible:** entrenamiento A=2/2 frente a B=35/100. Baseline elige A por 100 % aparente; la regla Wilson con mínimo 40 elige B. En holdout posterior A=5/100, B=50/100: baseline=0,05; candidato=0,50; diferencia observacional=+0,45. **Un segundo test invierte el resultado y demuestra que no garantiza ganar.** No extrapolar a mejora real ni a causalidad. El baseline es tasa cruda, **no** el rank_keys operativo del oficial; comparar contra ese ranking requerirá un importador y resultados comparables.

### Reproducción

Ejecutar en checkout de la rama, Python 3.11:

    python -m unittest discover -s tests -p test_discovery_ranking.py -q
    python -m unittest discover -s tests -p test_discovery_replay.py -q
    python -m pytest tests/test_discovery_ranking.py tests/test_discovery_replay.py -q -p no:cacheprovider
    python -m compileall -q tools/discovery_ranking.py tools/discovery_replay.py tests/test_discovery_ranking.py tests/test_discovery_replay.py

El workflow existente .github/workflows/validate-social-tools.yml ejecuta la suite sin red en Windows/Ubuntu sobre push. El gate de la PR comprueba higiene y documentación. Consultar **ejecución del HEAD final**: un run verde anterior no demuestra éxito actual.

## Segunda revisión adversarial y alcance pendiente

1. El replay descartaba implícitamente filas sin red clasificable: ahora rechaza explícitamente el lote y tiene regresión sintética.
2. El verificador de privacidad del mirror consideró sospechoso un nombre de constante que terminaba en TOKEN; se renombró la constante, sin modificar el detector ni ocultar errores.
3. No hay fuga de orden temporal: los cortes están inyectados y cada cohorte futura empieza después del cierre observado de entrenamiento. No se mezclan redes ni se calculan supuestas ganancias si falta un solo holdout de fuente entrenada.
4. Se probaron conceptualmente muestras minúsculas, reversión de ventaja, duplicados, ventanas no disjuntas, snapshot incompleto, k excesivo, red desconocida y novena red sin lector. El dato de test es **siempre sintético**.

**Pendiente de Claude:** validar el merge preview y los checks del último SHA; ejecutar paridad Windows/Ubuntu y suite completa oficial, realizar canario supervisado si se autoriza una futura conexión de datos. No hay canario vivo, Android ni Edge real en esta PR. La PR es lista para integrarse **como biblioteca offline** tras checks verdes, no como mejora desplegada automáticamente.

**Rollback:** revertir únicamente los dos módulos nuevos, las dos suites y este informe. No hay migración de base de datos, cache, cola o estado operativo. Futuro enlace: importador que certifique actor estable, paginación de snapshot, procedencia y fecha original; mantener shadow ranking antes de sustituir el selector por red. Nunca deducir causalidad a partir de prevalencias o exposición sesgada.
